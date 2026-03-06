import { useCallback, useEffect, useRef, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Newspaper,
  PlayCircle,
  RefreshCw,
  Server,
  Zap,
} from 'lucide-react';
import axios from 'axios';
import Layout from '@/components/Layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

type ConnectorInfo = {
  enabled: boolean;
  status?: string;
  last_fetch_at?: string;
  last_articles_fetched?: number;
  last_articles_stored?: number;
  error?: string;
};

type ContinuousStatus = {
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
  cycle_count: number;
  last_cycle_at: string | null;
  next_cycle_at: string | null;
  last_cycle_articles: number;
  total_articles_ingested: number;
  connectors: {
    gdelt: ConnectorInfo;
    sec_edgar: ConnectorInfo;
    newsdata: ConnectorInfo;
  };
  recent_errors: Array<{ time: string; error: string; type: string }>;
};

type IngestStatus = {
  run_id?: string;
  status?: string;
  items_seen?: number;
  items_stored?: number;
  stored_article_count?: number;
  scheduled_refresh_seconds?: number;
  continuous_runner?: ContinuousStatus;
};

const connectorDisplayNames: Record<string, string> = {
  gdelt: 'GDELT Project',
  sec_edgar: 'SEC EDGAR',
  newsdata: 'Newsdata.io',
};

const getStatusColor = (status?: string): string => {
  switch (status) {
    case 'ok':
      return 'border-emerald-500/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300';
    case 'empty':
      return 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300';
    case 'error':
      return 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300';
    default:
      return 'border-zinc-500/40 bg-zinc-500/10 text-zinc-600 dark:text-zinc-400';
  }
};

const getStatusIcon = (status?: string) => {
  switch (status) {
    case 'ok':
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case 'error':
      return <AlertCircle className="h-4 w-4 text-rose-500" />;
    default:
      return <Clock className="h-4 w-4 text-zinc-400" />;
  }
};

export default function IngestDashboard(): React.JSX.Element {
  const [status, setStatus] = useState<IngestStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await axios.get('/api/ingest/status');
      setStatus(resp.data as IngestStatus);
    } catch (err) {
      console.warn('Failed to fetch ingest status', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    // Auto-refresh every 15 seconds
    pollRef.current = setInterval(() => void fetchStatus(), 15_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchStatus]);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const resp = await axios.post('/api/ingest/continuous/trigger');
      const data = resp.data as { result?: { articles_stored?: number; cycle?: number } };
      const stored = data.result?.articles_stored ?? 0;
      setTriggerResult(`Cycle completed — ${stored} new article${stored !== 1 ? 's' : ''} stored`);
      await fetchStatus();
    } catch {
      setTriggerResult('Ingest cycle failed. Check server logs.');
    } finally {
      setTriggering(false);
    }
  };

  const runner = status?.continuous_runner;
  const connectors = runner?.connectors;

  return (
    <Layout
      title="Ingest Dashboard"
      description="Monitor continuous news ingestion from GDELT, SEC EDGAR, Newsdata.io, and RSS feeds."
    >
      <main className="mx-auto max-w-7xl px-4 py-1 sm:px-0">
        <div className="space-y-8">
          {/* Header */}
          <div className="space-y-1">
            <h1 className="font-display text-3xl font-semibold tracking-tight">
              Ingest Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Monitor and control continuous news ingestion from public sources.
            </p>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading ingest status...
            </div>
          ) : (
            <>
              {/* Overview Cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className="rounded-xl bg-emerald-500/10 p-3">
                      <Activity className="h-5 w-5 text-emerald-500" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">
                        {runner?.running ? 'Active' : 'Stopped'}
                      </p>
                      <p className="text-xs text-muted-foreground">Runner Status</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className="rounded-xl bg-blue-500/10 p-3">
                      <Newspaper className="h-5 w-5 text-blue-500" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">
                        {status?.stored_article_count?.toLocaleString() ?? '—'}
                      </p>
                      <p className="text-xs text-muted-foreground">Total Articles</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className="rounded-xl bg-violet-500/10 p-3">
                      <Zap className="h-5 w-5 text-violet-500" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">
                        {runner?.total_articles_ingested?.toLocaleString() ?? '0'}
                      </p>
                      <p className="text-xs text-muted-foreground">Ingested This Session</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className="rounded-xl bg-amber-500/10 p-3">
                      <RefreshCw className="h-5 w-5 text-amber-500" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{runner?.cycle_count ?? 0}</p>
                      <p className="text-xs text-muted-foreground">Cycles Completed</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Runner Details + Trigger */}
              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Server className="h-5 w-5" />
                      Continuous Runner
                    </CardTitle>
                    <CardDescription>
                      Background loop fetching from all connectors every{' '}
                      {runner?.interval_seconds ?? '—'}s
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 text-sm sm:grid-cols-2">
                      <div>
                        <span className="text-muted-foreground">Last Cycle:</span>{' '}
                        <span className="font-medium">
                          {runner?.last_cycle_at
                            ? formatDistanceToNow(new Date(runner.last_cycle_at), {
                                addSuffix: true,
                              })
                            : 'Never'}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Next Cycle:</span>{' '}
                        <span className="font-medium">
                          {runner?.next_cycle_at
                            ? formatDistanceToNow(new Date(runner.next_cycle_at), {
                                addSuffix: true,
                              })
                            : '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Last Cycle Articles:</span>{' '}
                        <span className="font-medium">
                          {runner?.last_cycle_articles ?? 0}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Interval:</span>{' '}
                        <span className="font-medium">
                          {runner?.interval_seconds
                            ? `${Math.round(runner.interval_seconds / 60)} min`
                            : '—'}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        type="button"
                        onClick={() => void handleTrigger()}
                        disabled={triggering}
                      >
                        {triggering ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Running...
                          </>
                        ) : (
                          <>
                            <PlayCircle className="mr-2 h-4 w-4" />
                            Ingest Now
                          </>
                        )}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void fetchStatus()}
                      >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Refresh
                      </Button>
                    </div>

                    {triggerResult && (
                      <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                        {triggerResult}
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* Quick Stats */}
                <Card>
                  <CardHeader>
                    <CardTitle>RSS Feed Ingest</CardTitle>
                    <CardDescription>Last periodic ingest run</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Status:</span>{' '}
                      <Badge variant="outline">{status?.status ?? '—'}</Badge>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Articles Seen:</span>{' '}
                      <span className="font-medium">{status?.items_seen ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Articles Stored:</span>{' '}
                      <span className="font-medium">{status?.items_stored ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Scheduled Refresh:</span>{' '}
                      <span className="font-medium">
                        {status?.scheduled_refresh_seconds
                          ? `${status.scheduled_refresh_seconds}s`
                          : 'Disabled'}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Connector Status Cards */}
              <div>
                <h2 className="mb-4 font-display text-2xl font-semibold tracking-tight">
                  Connector Status
                </h2>
                <div className="grid gap-4 sm:grid-cols-3">
                  {connectors &&
                    Object.entries(connectors).map(([key, info]) => (
                      <Card key={key}>
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-base">
                              {connectorDisplayNames[key] || key}
                            </CardTitle>
                            {getStatusIcon(info.status)}
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-2 text-sm">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant="outline"
                              className={
                                info.enabled
                                  ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                  : ''
                              }
                            >
                              {info.enabled ? 'Enabled' : 'Disabled'}
                            </Badge>
                            {info.status && (
                              <Badge variant="outline" className={getStatusColor(info.status)}>
                                {info.status}
                              </Badge>
                            )}
                          </div>
                          {info.last_fetch_at && (
                            <div>
                              <span className="text-muted-foreground">Last Fetch:</span>{' '}
                              <span className="font-medium">
                                {formatDistanceToNow(new Date(info.last_fetch_at), {
                                  addSuffix: true,
                                })}
                              </span>
                            </div>
                          )}
                          {typeof info.last_articles_fetched === 'number' && (
                            <div>
                              <span className="text-muted-foreground">Fetched:</span>{' '}
                              <span className="font-medium">{info.last_articles_fetched}</span>
                              {typeof info.last_articles_stored === 'number' && (
                                <>
                                  {' → '}
                                  <span className="font-medium text-emerald-600 dark:text-emerald-400">
                                    {info.last_articles_stored} stored
                                  </span>
                                </>
                              )}
                            </div>
                          )}
                          {info.error && (
                            <p className="text-xs text-rose-500">{info.error}</p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                </div>
              </div>

              {/* Recent Errors */}
              {runner?.recent_errors && runner.recent_errors.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-rose-500">
                      <AlertCircle className="h-5 w-5" />
                      Recent Errors
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {runner.recent_errors.map((err, idx) => (
                        <div
                          key={idx}
                          className="rounded-lg border border-rose-500/20 bg-rose-500/5 px-3 py-2 text-sm"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <Badge
                              variant="outline"
                              className="border-rose-500/40 text-rose-600 dark:text-rose-400"
                            >
                              {err.type}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {formatDistanceToNow(new Date(err.time), { addSuffix: true })}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">
                            {err.error}
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </main>
    </Layout>
  );
}
