import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { RefreshCw } from 'lucide-react';
import Layout from '../../components/Layout';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';

// Article type definition
type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
};

type SentimentFilter = '' | 'positive' | 'neutral' | 'negative';
type SortOption = 'date' | 'relevance' | 'sentiment';
type NamedOption = { id: string; name: string };

const selectClassName =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const isNamedOption = (value: unknown): value is NamedOption =>
  isRecord(value) && typeof value.id === 'string' && typeof value.name === 'string';

const normalizeNamedOptions = (payload: unknown): NamedOption[] =>
  Array.isArray(payload) ? payload.filter(isNamedOption) : [];

const isArticle = (value: unknown): value is Article =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  typeof value.title === 'string' &&
  typeof value.url === 'string' &&
  typeof value.source === 'string' &&
  typeof value.published_at === 'string';

const normalizeArticlesPayload = (payload: unknown): Article[] | null => {
  if (Array.isArray(payload)) {
    return payload.filter(isArticle);
  }

  if (isRecord(payload) && Array.isArray(payload.articles)) {
    return payload.articles.filter(isArticle);
  }

  return null;
};

const getResponseErrorMessage = async (
  response: Response,
  fallback: string
): Promise<string> => {
  const statusText = `${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
  try {
    const payload = (await response.clone().json()) as {
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const detail =
      typeof payload.detail === 'string'
        ? payload.detail
        : typeof payload.error === 'string'
          ? payload.error
          : typeof payload.message === 'string'
            ? payload.message
            : '';
    const normalizedDetail = detail.trim().toLowerCase();
    if (normalizedDetail && normalizedDetail !== 'fetch failed') {
      return `${detail} (${statusText})`;
    }
  } catch {
    // Ignore JSON parse failures and fallback to generic message below.
  }

  return `${fallback} (${statusText})`;
};

export default function ArticlesPage() {
  const router = useRouter();
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [articlesError, setArticlesError] = useState<string | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [sources, setSources] = useState<NamedOption[]>([]);
  const [topics, setTopics] = useState<NamedOption[]>([]);

  // Filter states
  const [source, setSource] = useState('');
  const [topic, setTopic] = useState('');
  const [sentiment, setSentiment] = useState<SentimentFilter>('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('date');

  useEffect(() => {
    // Fetch filter options
    const fetchOptions = async () => {
      try {
        setFiltersError(null);
        const [sourcesRes, topicsRes] = await Promise.all([
          fetch('/api/sources'),
          fetch('/api/topics'),
        ]);

        const errors: string[] = [];

        if (sourcesRes.ok) {
          const sourcesData = await sourcesRes.json();
          setSources(normalizeNamedOptions(sourcesData));
        } else {
          setSources([]);
          errors.push(await getResponseErrorMessage(sourcesRes, 'Failed to load sources'));
        }

        if (topicsRes.ok) {
          const topicsData = await topicsRes.json();
          setTopics(normalizeNamedOptions(topicsData));
        } else {
          setTopics([]);
          errors.push(await getResponseErrorMessage(topicsRes, 'Failed to load topics'));
        }

        const deduplicatedErrors = Array.from(new Set(errors));
        setFiltersError(deduplicatedErrors.length > 0 ? deduplicatedErrors.join(' | ') : null);
      } catch (error) {
        setFiltersError('Unable to load filter options right now.');
        if (process.env.NODE_ENV === 'development') {
          console.warn('Failed to fetch article filter options', error);
        }
      }
    };
    
    fetchOptions();
  }, []);

  // Effect to fetch articles with filters
  useEffect(() => {
    const fetchArticles = async () => {
      setLoading(true);
      setArticlesError(null);
      
      // Build query string
      const params = new URLSearchParams();
      if (source) params.append('source', source);
      if (topic) params.append('topic', topic);
      if (sentiment) params.append('sentiment', sentiment);
      if (search) params.append('search', search);
      params.append('sort_by', sortBy);
      params.append('sort_order', 'desc');
      params.append('limit', '20');
      
      try {
        const response = await fetch(`/api/articles?${params.toString()}`);
        if (!response.ok) {
          setArticles([]);
          setArticlesError(await getResponseErrorMessage(response, 'Failed to fetch articles'));
          return;
        }
        const data: unknown = await response.json();
        const nextArticles = normalizeArticlesPayload(data);
        if (!nextArticles) {
          setArticles([]);
          setArticlesError('Unexpected response format while loading articles.');
          return;
        }
        setArticles(nextArticles);
      } catch (error) {
        setArticlesError('Network error while loading articles.');
        setArticles([]);
        if (process.env.NODE_ENV === 'development') {
          console.warn('Failed to fetch articles', error);
        }
      } finally {
        setLoading(false);
        setRetrying(false);
      }
    };

    fetchArticles();
  }, [source, topic, sentiment, search, sortBy, retryTick]);

  // Handle article click
  const handleArticleClick = (id: string) => {
    router.push(`/articles/${id}`);
  };

  const handleRetry = () => {
    setRetrying(true);
    setRetryTick((prev) => prev + 1);
  };

  const getSentimentStyle = (
    value?: string
  ): { badgeClassName: string; borderClassName: string; label: string } => {
    if (!value) {
      return {
        badgeClassName: 'border-border/80 bg-muted text-muted-foreground',
        borderClassName: 'border-l-border',
        label: 'unknown',
      };
    }

    const normalizedValue = value.toLowerCase();

    switch (normalizedValue) {
      case 'positive':
        return {
          badgeClassName:
            'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
          borderClassName: 'border-l-emerald-500/70',
          label: 'positive',
        };
      case 'negative':
        return {
          badgeClassName: 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300',
          borderClassName: 'border-l-rose-500/70',
          label: 'negative',
        };
      case 'neutral':
        return {
          badgeClassName:
            'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
          borderClassName: 'border-l-amber-500/70',
          label: 'neutral',
        };
      default:
        return {
          badgeClassName: 'border-border/80 bg-muted text-muted-foreground',
          borderClassName: 'border-l-border',
          label: value,
        };
    }
  };

  const formatDate = (value: string): string => {
    const parsedDate = new Date(value);

    if (Number.isNaN(parsedDate.getTime())) {
      return value;
    }

    return parsedDate.toLocaleDateString();
  };

  const getSentimentLabel = (value?: string): string => {
    if (!value) {
      return '';
    }

    switch (value.toLowerCase()) {
      case 'positive':
        return 'Positive';
      case 'negative':
        return 'Negative';
      case 'neutral':
        return 'Neutral';
      default:
        return value;
    }
  };

  return (
    <Layout title="Financial News Articles" description="Browse and search financial news articles">
      <section className="space-y-2">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Financial News Articles
        </h1>
        <p className="text-sm text-muted-foreground sm:text-base">
          Browse and filter the latest headlines with sentiment context.
        </p>
      </section>

      {/* Filters */}
      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardContent className="p-6">
          <div className="grid gap-3 md:grid-cols-10">
            <div className="md:col-span-3">
              <label
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                htmlFor="article-search"
              >
                Search
              </label>
              <Input
                id="article-search"
                placeholder="Search article title or summary"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="md:col-span-2">
              <label
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                htmlFor="source-filter"
              >
                Source
              </label>
              <select
                id="source-filter"
                value={source}
                className={selectClassName}
                onChange={(e) => setSource(e.target.value)}
              >
                <option value="">All Sources</option>
                {sources.map((sourceOption) => (
                  <option key={sourceOption.id} value={sourceOption.id}>
                    {sourceOption.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-2">
              <label
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                htmlFor="topic-filter"
              >
                Topic
              </label>
              <select
                id="topic-filter"
                value={topic}
                className={selectClassName}
                onChange={(e) => setTopic(e.target.value)}
              >
                <option value="">All Topics</option>
                {topics.map((topicOption) => (
                  <option key={topicOption.id} value={topicOption.id}>
                    {topicOption.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-1">
              <label
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                htmlFor="sentiment-filter"
              >
                Sentiment
              </label>
              <select
                id="sentiment-filter"
                value={sentiment}
                className={selectClassName}
                onChange={(e) => setSentiment(e.target.value as SentimentFilter)}
              >
                <option value="">All</option>
                <option value="positive">Positive</option>
                <option value="neutral">Neutral</option>
                <option value="negative">Negative</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                htmlFor="sort-filter"
              >
                Sort By
              </label>
              <select
                id="sort-filter"
                value={sortBy}
                className={selectClassName}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
              >
                <option value="date">Date</option>
                <option value="relevance">Relevance</option>
                <option value="sentiment">Sentiment</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {filtersError && (
        <Card className="mt-4 border-amber-500/40 bg-amber-500/10" role="alert" aria-live="assertive">
          <CardContent className="p-4">
            <p className="text-sm text-amber-800 dark:text-amber-200">{filtersError}</p>
          </CardContent>
        </Card>
      )}

      {articlesError && !loading && (
        <Card
          className="mt-4 border-destructive/50 bg-destructive/5"
          role="alert"
          aria-live="assertive"
        >
          <CardContent className="p-4">
            <p className="text-sm text-destructive">{articlesError}</p>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="mt-3 gap-1.5"
              disabled={retrying}
              onClick={handleRetry}
            >
              <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
              {retrying ? 'Retrying...' : 'Retry'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Articles */}
      {loading ? (
        <div className="flex justify-center py-10" role="status" aria-live="polite" aria-label="Loading articles">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
        </div>
      ) : (
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {articles.length > 0 ? (
            articles.map((article) => (
              <Card
                key={article.id}
                className={`h-full border-l-4 ${getSentimentStyle(article.sentiment).borderClassName}`}
              >
                <button
                  type="button"
                  onClick={() => handleArticleClick(article.id)}
                  className="flex h-full w-full text-left transition-colors hover:bg-accent/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <CardContent className="flex h-full w-full flex-col p-4">
                    <div className="mb-2 flex items-start justify-between gap-2 text-xs text-muted-foreground">
                      <p className="line-clamp-1">{article.source}</p>
                      <time dateTime={article.published_at}>{formatDate(article.published_at)}</time>
                    </div>

                    <h2 className="line-clamp-3 min-w-0 font-display text-lg font-semibold leading-snug">
                      {article.title}
                    </h2>

                    {article.summarized_headline && (
                      <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
                        {article.summarized_headline}
                      </p>
                    )}

                    <div className="mt-auto flex flex-wrap gap-2 pt-4">
                      {article.topics?.slice(0, 3).map((topicItem) => (
                        <Badge
                          key={topicItem}
                          variant="outline"
                          className="border-primary/40 bg-primary/5 text-primary"
                        >
                          {topicItem}
                        </Badge>
                      ))}

                      {article.sentiment && (
                        <Badge
                          variant="outline"
                          className={getSentimentStyle(article.sentiment).badgeClassName}
                        >
                          {getSentimentLabel(article.sentiment)}
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </button>
              </Card>
            ))
          ) : (
            <Card className="sm:col-span-2 lg:col-span-3">
              <CardContent className="py-10 text-center">
                <p className="text-sm text-muted-foreground">
                  {articlesError ? 'Unable to load articles right now.' : 'No articles found matching your criteria.'}
                </p>
              </CardContent>
            </Card>
          )}
        </section>
      )}
    </Layout>
  );
}
