import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import {
  CalendarClock,
  Newspaper,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react';
import Layout from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../components/ui/card';
import { Input } from '../components/ui/input';
import { cn } from '../lib/utils';
import type { ApiArticleSummary as ArticleSummary, ApiArticlesResponse as ArticlesResponse } from '../src/types/api';

type SentimentFilter = '' | 'positive' | 'neutral' | 'negative';
type SortOption = 'date' | 'relevance' | 'sentiment';
type LimitOption = 10 | 20 | 50;

const SENTIMENT_OPTIONS: Array<SentimentFilter> = ['positive', 'neutral', 'negative'];

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: 'date', label: 'Date' },
  { value: 'relevance', label: 'Relevance' },
  { value: 'sentiment', label: 'Sentiment' },
];

const LIMIT_OPTIONS: LimitOption[] = [10, 20, 50];

const SENTIMENT_STYLES: Record<string, { badge: string; border: string; label: string }> = {
  positive: {
    badge:
      'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    border: 'border-l-emerald-500/70',
    label: 'Positive',
  },
  negative: {
    badge: 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300',
    border: 'border-l-rose-500/70',
    label: 'Negative',
  },
  neutral: {
    badge:
      'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    border: 'border-l-amber-500/70',
    label: 'Neutral',
  },
};

const formatPublishedDate = (value: string): string => {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
};

const selectClassName =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';

const getSentimentStyle = (
  sentiment?: string
): { badge: string; border: string; label: string } => {
  return (
    SENTIMENT_STYLES[sentiment ?? ''] ?? {
      badge: 'border-border/80 bg-muted text-muted-foreground',
      border: 'border-l-border',
      label: 'Unknown',
    }
  );
};

export default function HomePage(): React.JSX.Element {
  const router = useRouter();
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [limit, setLimit] = useState<LimitOption>(10);
  const [sentiment, setSentiment] = useState<SentimentFilter>('');
  const [sortBy, setSortBy] = useState<SortOption>('date');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput]);

  const queryParams = useMemo(() => {
    const params = new URLSearchParams();

    if (search) {
      params.set('search', search);
    }

    if (sentiment) {
      params.set('sentiment', sentiment);
    }

    params.set('sort_by', sortBy);
    params.set('sort_order', 'desc');
    params.set('limit', String(limit));

    return params.toString();
  }, [search, sentiment, sortBy, limit]);

  const fetchArticles = useCallback(
    async (isRetry = false) => {
      setLoading(true);
      setError(null);
      setRetrying(isRetry);

      try {
        const response = await fetch(`/api/articles?${queryParams}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch articles (${response.status})`);
        }

        const data: ArticlesResponse = await response.json();
        setArticles(data.articles ?? []);
        setLastError(null);
      } catch (fetchError) {
        const message =
          fetchError instanceof Error
            ? fetchError.message
            : 'Unable to load articles right now. Please try again.';

        setError(message);
        setLastError(message);
        setArticles([]);
      } finally {
        setLoading(false);
        setRetrying(false);
      }
    },
    [queryParams]
  );

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  // Auto-refresh polling
  useEffect(() => {
    if (autoRefreshRef.current) {
      clearInterval(autoRefreshRef.current);
      autoRefreshRef.current = null;
    }
    if (autoRefresh) {
      autoRefreshRef.current = setInterval(() => void fetchArticles(), 30_000);
    }
    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
    };
  }, [autoRefresh, fetchArticles]);

  const handleRetry = () => {
    fetchArticles(true);
  };

  const handleResetFilters = () => {
    setSearchInput('');
    setSearch('');
    setSentiment('');
    setSortBy('date');
    setLimit(10);
  };

  const handleArticleClick = (article: ArticleSummary) => {
    const articleId = article.id;
    if (articleId) {
      router.push(`/articles/${articleId}`);
    }
  };

  const isEmpty = !loading && !error && articles.length === 0;
  const canRenderContent = !loading && !error && articles.length > 0;
  const activeFilterCount =
    Number(Boolean(search)) + Number(Boolean(sentiment)) + Number(sortBy !== 'date') +
    Number(limit !== 10);

  return (
    <Layout
      title="Financial News Dashboard"
      description="Real-time financial news analysis and insights"
    >
      <section className="relative overflow-hidden rounded-2xl border border-border/70 bg-card/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-sm sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-primary/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-8 h-56 w-56 rounded-full bg-secondary/20 blur-3xl" />

        <div className="relative space-y-4">
          <div className="flex items-center gap-3">
            <Badge
              variant="secondary"
              className="w-fit border-0 bg-secondary/80 text-secondary-foreground"
            >
              <Sparkles className="mr-1 h-3.5 w-3.5" />
              Live intelligence
            </Badge>
            <Button
              variant={autoRefresh ? 'default' : 'outline'}
              size="sm"
              onClick={() => setAutoRefresh((prev) => !prev)}
              className="gap-1.5 text-xs"
            >
              <RefreshCw className={cn('h-3 w-3', autoRefresh && 'animate-spin')} />
              {autoRefresh ? 'Auto-refresh on' : 'Auto-refresh'}
            </Button>
          </div>

          <div className="space-y-2">
            <h1 className="text-balance font-display text-3xl font-semibold leading-tight sm:text-4xl">
              Financial News Dashboard
            </h1>
            <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
              Monitor market-moving headlines with sentiment context and distilled takeaways.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="bg-background/70">
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Fetched now</p>
                <p className="mt-1 text-2xl font-semibold">{articles.length}</p>
              </CardContent>
            </Card>
            <Card className="bg-background/70">
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Filters active</p>
                <p className="mt-1 text-2xl font-semibold">{activeFilterCount}</p>
              </CardContent>
            </Card>
            <Card className="bg-background/70">
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Sort mode</p>
                <p className="mt-1 text-2xl font-semibold capitalize">{sortBy}</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <SlidersHorizontal className="h-4 w-4" />
            Refine Feed
          </CardTitle>
          <CardDescription>Search, filter sentiment, and tune ranking behavior.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Search
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Search headline or source"
                  className="pl-9"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Sentiment
              </label>
              <select
                value={sentiment}
                className={selectClassName}
                onChange={(event) => setSentiment(event.target.value as SentimentFilter)}
              >
                <option value="">All</option>
                {SENTIMENT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Sort by
              </label>
              <select
                value={sortBy}
                className={selectClassName}
                onChange={(event) => setSortBy(event.target.value as SortOption)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Results
              </label>
              <select
                value={String(limit)}
                className={selectClassName}
                onChange={(event) => setLimit(Number(event.target.value) as LimitOption)}
              >
                {LIMIT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-3 flex justify-end">
            <Button
              variant="outline"
              onClick={handleResetFilters}
              disabled={loading}
              className="gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Reset filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="mt-6 grid gap-4">
          {[0, 1, 2].map((item) => (
            <Card key={item} className="overflow-hidden border-border/70 bg-card/90">
              <CardContent className="p-6">
                <div className="h-5 w-2/3 rounded bg-muted" />
                <div className="mt-3 h-4 w-full rounded bg-muted" />
                <div className="mt-2 h-4 w-5/6 rounded bg-muted" />
                <div className="mt-4 h-16 rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && !loading && (
        <Card className="mt-6 border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive">Unable to load articles</CardTitle>
            <CardDescription className="text-foreground/80">{error}</CardDescription>
          </CardHeader>
          <CardContent>
            {lastError && (
              <p className="mb-3 text-sm text-muted-foreground">Last error detail: {lastError}</p>
            )}
            <Button variant="destructive" onClick={handleRetry} disabled={retrying}>
              {retrying ? 'Retrying...' : 'Retry'}
            </Button>
          </CardContent>
        </Card>
      )}

      {isEmpty && (
        <Card className="mt-6 border-dashed border-border/80 bg-card/85">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Newspaper className="h-5 w-5 text-muted-foreground" />
              No articles match these filters
            </CardTitle>
            <CardDescription>Try broadening your query or clearing filters.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={handleResetFilters}>
              Clear filters
            </Button>
          </CardContent>
        </Card>
      )}

      {canRenderContent && (
        <section className="mt-6 grid gap-4">
          {articles.map((article, index) => {
            const sentimentStyle = getSentimentStyle(article.sentiment);
            const clickable = Boolean(article.id);

            return (
              <Card
                key={article.id ?? `${article.title}-${index}`}
                className={cn(
                  'border-l-4 border-border/70 bg-card/90 transition-all',
                  sentimentStyle.border,
                  clickable && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/10'
                )}
                onClick={clickable ? () => handleArticleClick(article) : undefined}
                onKeyDown={
                  clickable
                    ? (event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        handleArticleClick(article);
                      }
                    }
                    : undefined
                }
                role={clickable ? 'button' : undefined}
                tabIndex={clickable ? 0 : -1}
              >
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <CardTitle className="text-xl leading-tight">{article.title}</CardTitle>
                    <Badge className={cn('shrink-0', sentimentStyle.badge)}>
                      {sentimentStyle.label}
                    </Badge>
                  </div>

                  <CardDescription className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide">
                    <span className="inline-flex items-center gap-1">
                      <Newspaper className="h-3.5 w-3.5" />
                      {article.source}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <CalendarClock className="h-3.5 w-3.5" />
                      {formatPublishedDate(article.published_at)}
                    </span>
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-3">
                  <p className="text-sm leading-relaxed text-foreground/90">
                    {article.summarized_headline || 'No summary available'}
                  </p>

                  {!!article.summary_bullets?.length && (
                    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                      {article.summary_bullets.slice(0, 3).map((bullet, bulletIndex) => (
                        <li key={`${bullet}-${bulletIndex}`}>{bullet}</li>
                      ))}
                    </ul>
                  )}

                  {!!article.topics?.length && (
                    <div className="flex flex-wrap gap-1.5">
                      {article.topics.map((topic) => (
                        <Badge
                          key={topic}
                          variant="outline"
                          className="border-primary/30 bg-primary/5 text-primary"
                        >
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </section>
      )}
    </Layout>
  );
}
