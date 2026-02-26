import { useCallback, useEffect, useRef, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, Plus, RefreshCw } from 'lucide-react';
import axios from 'axios';
import Layout from '@/components/Layout';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { NewsSource } from '../../lib/models/NewsSource';

type SchedulerState = {
  enabled: boolean;
  intervalSeconds: number;
};

type CrawlerStats = {
  totalSources: number;
  activeSources: number;
  sourcesDueCrawling: number;
  scheduler?: SchedulerState;
};

type CrawlRunStatus = {
  severity: 'success' | 'info' | 'warning' | 'error';
  message: string;
  runId?: string | null;
  details?: string[];
};

const getAlertVariant = (
  severity: CrawlRunStatus['severity']
): 'success' | 'info' | 'warning' | 'destructive' => {
  if (severity === 'error') {
    return 'destructive';
  }

  return severity;
};

const clampInteger = (value: string, fallback: number, min?: number, max?: number): number => {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }

  let next = parsed;
  if (typeof min === 'number') {
    next = Math.max(min, next);
  }
  if (typeof max === 'number') {
    next = Math.min(max, next);
  }

  return next;
};

const extractAxiosErrorDetail = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const statusText =
      typeof error.response?.status === 'number'
        ? `${error.response.status}${error.response?.statusText ? ` ${error.response.statusText}` : ''}`
        : null;
    const responseData = error.response?.data as { detail?: unknown; error?: unknown } | undefined;
    if (typeof responseData?.detail === 'string' && responseData.detail.trim()) {
      const detail = responseData.detail.trim();
      if (detail.toLowerCase() !== 'fetch failed') {
        return detail;
      }
    }
    if (typeof responseData?.error === 'string' && responseData.error.trim()) {
      const detail = responseData.error.trim();
      if (detail.toLowerCase() !== 'fetch failed') {
        return detail;
      }
    }

    if (statusText) {
      return `Request failed (${statusText})`;
    }

    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected error';
};

// Admin page for managing crawlers and news sources
export default function CrawlerAdmin(): React.JSX.Element {
  const sourcesRequestIdRef = useRef(0);
  const statsRequestIdRef = useRef(0);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [stats, setStats] = useState<CrawlerStats | null>(null);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [currentSource, setCurrentSource] = useState<NewsSource | null>(null);
  const [isSavingSource, setIsSavingSource] = useState(false);
  const [pendingSourceActionId, setPendingSourceActionId] = useState<string | null>(null);
  const [isRunningCrawl, setIsRunningCrawl] = useState(false);
  const [isTogglingScheduler, setIsTogglingScheduler] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState<CrawlRunStatus | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<'running' | 'stopped'>('stopped');

  const fetchSources = useCallback(async (): Promise<boolean> => {
    const requestId = ++sourcesRequestIdRef.current;
    setSourcesLoading(true);
    setSourcesError(null);
    try {
      const response = await axios.get('/api/crawler/sources');
      const nextSources = Array.isArray(response.data)
        ? (response.data as NewsSource[])
        : [];
      if (requestId !== sourcesRequestIdRef.current) {
        return false;
      }
      setSources(nextSources);
      return true;
    } catch (error) {
      const detail = extractAxiosErrorDetail(error);
      if (requestId !== sourcesRequestIdRef.current) {
        return false;
      }
      setSources([]);
      setSourcesError(`Unable to load sources. ${detail}`);
      if (process.env.NODE_ENV === 'development') {
        console.warn('Failed to fetch crawler sources', detail);
      }
      return false;
    } finally {
      if (requestId === sourcesRequestIdRef.current) {
        setSourcesLoading(false);
      }
    }
  }, []);

  const fetchStats = useCallback(async (): Promise<boolean> => {
    const requestId = ++statsRequestIdRef.current;
    setStatsLoading(true);
    setStatsError(null);
    try {
      const response = await axios.get('/api/crawler');
      const crawlerStats = response.data as CrawlerStats;
      if (requestId !== statsRequestIdRef.current) {
        return false;
      }
      setStats(crawlerStats);
      setSchedulerStatus(crawlerStats.scheduler?.enabled ? 'running' : 'stopped');
      return true;
    } catch (error) {
      const detail = extractAxiosErrorDetail(error);
      if (requestId !== statsRequestIdRef.current) {
        return false;
      }
      setStats(null);
      setSchedulerStatus('stopped');
      setStatsError(`Unable to load crawler status. ${detail}`);
      if (process.env.NODE_ENV === 'development') {
        console.warn('Failed to fetch crawler stats', detail);
      }
      return false;
    } finally {
      if (requestId === statsRequestIdRef.current) {
        setStatsLoading(false);
      }
    }
  }, []);

  // Load sources and stats on initial load
  useEffect(() => {
    void Promise.all([fetchSources(), fetchStats()]);
  }, [fetchSources, fetchStats]);

  const handleOpenDialog = (source: NewsSource | null = null) => {
    if (source) {
      setCurrentSource(source);
    } else {
      setCurrentSource({
        id: '',
        name: '',
        url: '',
        type: 'rss',
        category: 'finance',
        crawlFrequency: 30,
        isActive: true,
        useProxy: false,
        respectRobotsTxt: true,
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setCurrentSource(null);
  };

  const handleSourceChange = <K extends keyof NewsSource>(field: K, value: NewsSource[K]) => {
    if (!currentSource) return;

    if (field === 'selector') {
      setCurrentSource({
        ...currentSource,
        selector: {
          ...currentSource.selector,
          ...(value as Record<string, string>),
        },
      });
    } else {
      setCurrentSource({
        ...currentSource,
        [field]: value,
      });
    }
  };

  const handleSaveSource = async () => {
    if (!currentSource || isSavingSource) return;

    setIsSavingSource(true);
    try {
      await axios.post('/api/crawler/sources', currentSource);
      handleCloseDialog();
      const [sourcesLoaded, statsLoaded] = await Promise.all([fetchSources(), fetchStats()]);
      const refreshed = sourcesLoaded && statsLoaded;
      setCrawlStatus({
        severity: refreshed ? 'success' : 'warning',
        message: refreshed
          ? 'Source saved successfully.'
          : 'Source saved, but latest status failed to refresh.',
      });
    } catch (error) {
      setCrawlStatus({
        severity: 'error',
        message: 'Error saving source.',
        details: [extractAxiosErrorDetail(error)],
      });
    } finally {
      setIsSavingSource(false);
    }
  };

  const handleDeleteSource = async (id: string) => {
    if (!confirm('Are you sure you want to delete this source?')) return;
    if (pendingSourceActionId) return;

    setPendingSourceActionId(id);
    try {
      await axios.delete(`/api/crawler/sources?id=${id}`);
      const [sourcesLoaded, statsLoaded] = await Promise.all([fetchSources(), fetchStats()]);
      const refreshed = sourcesLoaded && statsLoaded;
      setCrawlStatus({
        severity: refreshed ? 'info' : 'warning',
        message: refreshed
          ? 'Source deleted.'
          : 'Source deleted, but latest status failed to refresh.',
      });
    } catch (error) {
      setCrawlStatus({
        severity: 'error',
        message: 'Error deleting source.',
        details: [extractAxiosErrorDetail(error)],
      });
    } finally {
      setPendingSourceActionId(null);
    }
  };

  const handleToggleSourceStatus = async (source: NewsSource) => {
    if (pendingSourceActionId) return;

    setPendingSourceActionId(source.id);
    try {
      await axios.post('/api/crawler/sources', {
        ...source,
        isActive: !source.isActive,
      });
      const [sourcesLoaded, statsLoaded] = await Promise.all([fetchSources(), fetchStats()]);
      const refreshed = sourcesLoaded && statsLoaded;
      setCrawlStatus({
        severity: refreshed ? 'info' : 'warning',
        message: refreshed
          ? source.isActive
            ? 'Source disabled.'
            : 'Source enabled.'
          : source.isActive
            ? 'Source disabled, but latest status failed to refresh.'
            : 'Source enabled, but latest status failed to refresh.',
      });
    } catch (error) {
      setCrawlStatus({
        severity: 'error',
        message: 'Error updating source status.',
        details: [extractAxiosErrorDetail(error)],
      });
    } finally {
      setPendingSourceActionId(null);
    }
  };

  const handleRunCrawlers = async () => {
    try {
      setIsRunningCrawl(true);
      setCrawlStatus(null);

      const response = await axios.post('/api/crawler', { action: 'run_now' });
      const data = response.data as {
        status?: unknown;
        newArticles?: unknown;
        runId?: unknown;
        errors?: unknown;
        alreadyRunning?: unknown;
        error?: unknown;
      };
      const statusText =
        typeof data.status === 'string' && data.status.trim() ? data.status : 'Crawl queued';
      const runId = typeof data.runId === 'string' ? data.runId : null;
      const details = Array.isArray(data.errors) ? data.errors.map((entry) => String(entry)) : [];
      const alreadyRunning = Boolean(data.alreadyRunning);
      const runFailed = Boolean(data.error);
      if (alreadyRunning) {
        setCrawlStatus({
          severity: 'info',
          message: statusText,
          runId,
        });
      } else if (runFailed) {
        setCrawlStatus({
          severity: 'error',
          message: statusText,
          runId,
          details,
        });
      } else {
        const newArticles = Number(data.newArticles || 0);
        const message =
          newArticles > 0 ? `${statusText}. Found ${newArticles} new articles.` : `${statusText}.`;
        setCrawlStatus({
          severity: details.length > 0 ? 'warning' : 'success',
          message,
          runId,
          details,
        });
      }

      const [sourcesLoaded, statsLoaded] = await Promise.all([fetchSources(), fetchStats()]);
      if (!(sourcesLoaded && statsLoaded)) {
        setCrawlStatus((current) => {
          if (!current || current.severity === 'error') {
            return current;
          }

          return {
            ...current,
            severity: current.severity === 'success' ? 'warning' : current.severity,
            details: Array.from(
              new Set([...(current.details || []), 'Latest source/status refresh failed.'])
            ),
          };
        });
      }
    } catch (error) {
      setCrawlStatus({
        severity: 'error',
        message: 'Error running crawlers.',
        details: [extractAxiosErrorDetail(error)],
      });
    } finally {
      setIsRunningCrawl(false);
    }
  };

  const handleToggleScheduler = async () => {
    if (isTogglingScheduler) {
      return;
    }

    setIsTogglingScheduler(true);
    try {
      const action = schedulerStatus === 'running' ? 'stop_scheduler' : 'start_scheduler';
      const response = await axios.post('/api/crawler', { action });
      const statusText =
        typeof response.data?.status === 'string' && response.data.status.trim()
          ? response.data.status
          : 'Scheduler setting updated.';
      const statsLoaded = await fetchStats();
      setCrawlStatus({
        severity: statsLoaded ? 'info' : 'warning',
        message: statsLoaded
          ? statusText
          : `${statusText} (latest status refresh failed).`,
      });
    } catch (error) {
      setCrawlStatus({
        severity: 'error',
        message: 'Error updating scheduler setting.',
        details: [extractAxiosErrorDetail(error)],
      });
    } finally {
      setIsTogglingScheduler(false);
    }
  };

  return (
    <Layout
      title="News Crawler Admin"
      description="Manage crawler sources, run crawlers, and monitor scheduler status."
    >
      <main className="mx-auto max-w-7xl px-4 py-1 sm:px-0">
        <div className="space-y-8">
          <div className="space-y-1">
            <h1 className="font-display text-3xl font-semibold tracking-tight">News Crawler Admin</h1>
            <p className="text-sm text-muted-foreground">
              Manage crawler sources, launch manual runs, and control scheduler state.
            </p>
          </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Crawler System Status</CardTitle>
              <CardDescription>Current source and scheduler metrics.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {statsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading system status...
                </div>
              ) : stats ? (
                <>
                  <div className="grid gap-2 text-sm sm:grid-cols-2">
                    <p>
                      Total Sources: <span className="font-semibold">{stats.totalSources}</span>
                    </p>
                    <p>
                      Active Sources: <span className="font-semibold">{stats.activeSources}</span>
                    </p>
                    <p>
                      Sources Due for Crawling:{' '}
                      <span className="font-semibold">{stats.sourcesDueCrawling}</span>
                    </p>
                    <p>
                      Scheduler:{' '}
                      <span className="font-semibold">
                        {stats.scheduler?.enabled
                          ? `Active every ${Math.max(1, Math.round((stats.scheduler.intervalSeconds || 0) / 60))} minute(s)`
                          : 'Disabled (set NEWS_INGEST_INTERVAL_SECONDS > 0 and restart backend)'}
                      </span>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      onClick={() => void handleRunCrawlers()}
                      disabled={isRunningCrawl || statsLoading}
                    >
                      {isRunningCrawl ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Running...
                        </>
                      ) : (
                        'Run Crawlers Now'
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant={schedulerStatus === 'running' ? 'destructive' : 'outline'}
                      disabled={isTogglingScheduler || statsLoading}
                      onClick={() => void handleToggleScheduler()}
                    >
                      {isTogglingScheduler
                        ? 'Updating...'
                        : schedulerStatus === 'running'
                          ? 'Stop Scheduler'
                          : 'Start Scheduler'}
                    </Button>
                  </div>
                </>
              ) : (
                <Alert variant="destructive">
                  <AlertTitle>Unable to load crawler status</AlertTitle>
                  <AlertDescription className="space-y-3">
                    <p>{statsError || 'The backend is currently unavailable.'}</p>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      className="gap-1.5"
                      disabled={statsLoading}
                      onClick={() => void fetchStats()}
                    >
                      <RefreshCw className="h-4 w-4" />
                      Retry status fetch
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              {crawlStatus && (
                <Alert variant={getAlertVariant(crawlStatus.severity)}>
                  <AlertTitle>Status Update</AlertTitle>
                  <AlertDescription>
                    <p>{crawlStatus.message}</p>
                    {crawlStatus.runId && (
                      <p className="mt-1 text-xs text-muted-foreground">Run ID: {crawlStatus.runId}</p>
                    )}
                    {(crawlStatus.details || []).length > 0 && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {(crawlStatus.details || []).join(' | ')}
                      </p>
                    )}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Add a News Source</CardTitle>
              <CardDescription>Create a crawler source definition.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                type="button"
                className="w-full"
                variant="secondary"
                disabled={isSavingSource || pendingSourceActionId !== null}
                onClick={() => handleOpenDialog()}
              >
                <Plus className="mr-2 h-4 w-4" />
                Add New Source
              </Button>
            </CardContent>
          </Card>
        </div>

        <section className="space-y-3">
          <h2 className="font-display text-2xl font-semibold tracking-tight">News Sources</h2>

          {sourcesLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading sources...
            </div>
          ) : sourcesError ? (
            <Card
              className="border-destructive/50 bg-destructive/5"
              role="alert"
              aria-live="assertive"
            >
              <CardContent className="space-y-3 p-4">
                <p className="text-sm text-destructive">{sourcesError}</p>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  className="gap-1.5"
                  disabled={sourcesLoading}
                  onClick={() => void fetchSources()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry sources fetch
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table className="min-w-[900px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>URL</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Frequency</TableHead>
                        <TableHead>Last Crawled</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sources.map((source) => (
                        <TableRow key={source.id}>
                          <TableCell className="font-medium">{source.name}</TableCell>
                          <TableCell>
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block max-w-[18rem] truncate text-primary hover:underline"
                              title={source.url}
                            >
                              {source.url}
                            </a>
                          </TableCell>
                          <TableCell className="uppercase tracking-wide text-muted-foreground">
                            {source.type}
                          </TableCell>
                          <TableCell className="capitalize">{source.category}</TableCell>
                          <TableCell>{source.crawlFrequency} minutes</TableCell>
                          <TableCell>
                            {source.lastCrawled
                              ? formatDistanceToNow(new Date(source.lastCrawled), { addSuffix: true })
                              : 'Never'}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={source.isActive ? 'default' : 'outline'}
                              className={
                                source.isActive
                                  ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                  : ''
                              }
                            >
                              {source.isActive ? 'Active' : 'Inactive'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={pendingSourceActionId !== null || isSavingSource}
                                onClick={() => handleOpenDialog(source)}
                              >
                                Edit
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant={source.isActive ? 'destructive' : 'secondary'}
                                disabled={pendingSourceActionId !== null || isSavingSource}
                                onClick={() => void handleToggleSourceStatus(source)}
                              >
                                {pendingSourceActionId === source.id
                                  ? 'Working...'
                                  : source.isActive
                                    ? 'Disable'
                                    : 'Enable'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="destructive"
                                disabled={pendingSourceActionId !== null || isSavingSource}
                                onClick={() => void handleDeleteSource(source.id)}
                              >
                                {pendingSourceActionId === source.id ? 'Working...' : 'Delete'}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}

                      {sources.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                            No sources found
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </section>
        </div>

        <Dialog
          open={openDialog}
          onOpenChange={(open) => {
            if (!open) {
              handleCloseDialog();
            }
          }}
        >
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>
                {currentSource?.id ? `Edit Source: ${currentSource.name}` : 'Add New Source'}
              </DialogTitle>
              <DialogDescription>
                Configure crawling behavior and source parsing settings.
              </DialogDescription>
            </DialogHeader>

          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (isSavingSource) {
                return;
              }
              void handleSaveSource();
            }}
          >
            <div className="space-y-2">
              <label htmlFor="source-name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="source-name"
                value={currentSource?.name || ''}
                onChange={(event) => handleSourceChange('name', event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="source-url" className="text-sm font-medium">
                URL
              </label>
              <Input
                id="source-url"
                value={currentSource?.url || ''}
                onChange={(event) => handleSourceChange('url', event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="source-type" className="text-sm font-medium">
                Type
              </label>
              <Select
                value={currentSource?.type || 'rss'}
                onValueChange={(value) => handleSourceChange('type', value as NewsSource['type'])}
              >
                <SelectTrigger id="source-type" aria-label="Source type">
                  <SelectValue placeholder="Select source type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rss">RSS Feed</SelectItem>
                  <SelectItem value="scrape">Web Scraping</SelectItem>
                  <SelectItem value="api">API</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label htmlFor="source-category" className="text-sm font-medium">
                Category
              </label>
              <Select
                value={currentSource?.category || 'finance'}
                onValueChange={(value) =>
                  handleSourceChange('category', value as NewsSource['category'])
                }
              >
                <SelectTrigger id="source-category" aria-label="Source category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="finance">Finance</SelectItem>
                  <SelectItem value="economics">Economics</SelectItem>
                  <SelectItem value="markets">Markets</SelectItem>
                  <SelectItem value="technology">Technology</SelectItem>
                  <SelectItem value="general">General</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label htmlFor="crawl-frequency" className="text-sm font-medium">
                Crawl Frequency (minutes)
              </label>
              <Input
                id="crawl-frequency"
                type="number"
                min={5}
                value={currentSource?.crawlFrequency || 30}
                onChange={(event) =>
                  handleSourceChange(
                    'crawlFrequency',
                    clampInteger(event.target.value, currentSource?.crawlFrequency || 30, 5)
                  )
                }
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="user-agent" className="text-sm font-medium">
                User Agent
              </label>
              <Input
                id="user-agent"
                value={currentSource?.userAgent || 'FinanceNewsBot/1.0'}
                onChange={(event) => handleSourceChange('userAgent', event.target.value)}
              />
            </div>

            {currentSource?.type === 'rss' && (
              <div className="space-y-2 sm:col-span-2">
                <label htmlFor="rss-url" className="text-sm font-medium">
                  RSS URL
                </label>
                <Input
                  id="rss-url"
                  value={currentSource?.rssUrl || ''}
                  onChange={(event) => handleSourceChange('rssUrl', event.target.value)}
                />
              </div>
            )}

            {currentSource?.type === 'api' && (
              <>
                <div className="space-y-2 sm:col-span-2 md:col-span-1">
                  <label htmlFor="api-endpoint" className="text-sm font-medium">
                    API Endpoint
                  </label>
                  <Input
                    id="api-endpoint"
                    value={currentSource?.apiEndpoint || ''}
                    onChange={(event) => handleSourceChange('apiEndpoint', event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="api-key" className="text-sm font-medium">
                    API Key
                  </label>
                  <Input
                    id="api-key"
                    value={currentSource?.apiKey || ''}
                    onChange={(event) => handleSourceChange('apiKey', event.target.value)}
                  />
                </div>
              </>
            )}

            {currentSource?.type === 'scrape' && (
              <>
                <div className="sm:col-span-2">
                  <p className="text-sm font-semibold">Selectors for HTML parsing</p>
                </div>
                <div className="space-y-2">
                  <label htmlFor="selector-title" className="text-sm font-medium">
                    Title Selector
                  </label>
                  <Input
                    id="selector-title"
                    value={currentSource?.selector?.title || 'h1'}
                    onChange={(event) =>
                      handleSourceChange('selector', { title: event.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="selector-content" className="text-sm font-medium">
                    Content Selector
                  </label>
                  <Input
                    id="selector-content"
                    value={currentSource?.selector?.content || 'article, .article-body'}
                    onChange={(event) =>
                      handleSourceChange('selector', { content: event.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="selector-date" className="text-sm font-medium">
                    Date Selector
                  </label>
                  <Input
                    id="selector-date"
                    value={currentSource?.selector?.date || 'time, .date'}
                    onChange={(event) => handleSourceChange('selector', { date: event.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="selector-author" className="text-sm font-medium">
                    Author Selector
                  </label>
                  <Input
                    id="selector-author"
                    value={currentSource?.selector?.author || '.author, .byline'}
                    onChange={(event) =>
                      handleSourceChange('selector', { author: event.target.value })
                    }
                  />
                </div>
              </>
            )}

            <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
              <label className="flex items-center gap-3 text-sm font-medium">
                <Switch
                  checked={currentSource?.isActive || false}
                  onCheckedChange={(checked) => handleSourceChange('isActive', checked)}
                />
                Active
              </label>
            </div>

            <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
              <label className="flex items-center gap-3 text-sm font-medium">
                <Switch
                  checked={currentSource?.useProxy || false}
                  onCheckedChange={(checked) => handleSourceChange('useProxy', checked)}
                />
                Use Proxy
              </label>
            </div>

            <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
              <label className="flex items-center gap-3 text-sm font-medium">
                <Switch
                  checked={currentSource?.respectRobotsTxt ?? true}
                  onCheckedChange={(checked) => handleSourceChange('respectRobotsTxt', checked)}
                />
                Respect robots.txt
              </label>
            </div>

            {currentSource?.type === 'scrape' && (
              <div className="space-y-2 sm:col-span-2 md:col-span-1">
                <label htmlFor="wait-time" className="text-sm font-medium">
                  Wait Time (ms)
                </label>
                <Input
                  id="wait-time"
                  type="number"
                  min={0}
                  max={10000}
                  value={currentSource?.waitTime || 2000}
                  onChange={(event) =>
                    handleSourceChange(
                      'waitTime',
                      clampInteger(event.target.value, currentSource?.waitTime || 2000, 0, 10000)
                    )
                  }
                />
              </div>
            )}
          </form>

            <DialogFooter>
              <Button type="button" variant="outline" disabled={isSavingSource} onClick={handleCloseDialog}>
                Cancel
              </Button>
              <Button type="button" disabled={isSavingSource} onClick={() => void handleSaveSource()}>
                {isSavingSource ? 'Saving...' : 'Save'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </Layout>
  );
}
