import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import Layout from '../../components/Layout';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';

type AnalyticsData = {
  sentiment_distribution: { [key: string]: number };
  source_distribution: { [key: string]: number };
  top_entities: { name: string; count: number }[];
  top_topics: { name: string; count: number }[];
  processing_stats: {
    avg_processing_time: number;
    articles_processed: number;
    last_update: number;
  };
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const isNumberRecord = (value: unknown): value is Record<string, number> =>
  isRecord(value) &&
  Object.values(value).every(
    (entry) => typeof entry === 'number' && Number.isFinite(entry)
  );

const isNamedCountArray = (
  value: unknown
): value is Array<{ name: string; count: number }> =>
  Array.isArray(value) &&
  value.every(
    (entry) =>
      isRecord(entry) &&
      typeof entry.name === 'string' &&
      typeof entry.count === 'number' &&
      Number.isFinite(entry.count)
  );

const isAnalyticsData = (value: unknown): value is AnalyticsData => {
  if (!isRecord(value)) {
    return false;
  }

  const stats = value.processing_stats;
  return (
    isNumberRecord(value.sentiment_distribution) &&
    isNumberRecord(value.source_distribution) &&
    isNamedCountArray(value.top_entities) &&
    isNamedCountArray(value.top_topics) &&
    isRecord(stats) &&
    typeof stats.avg_processing_time === 'number' &&
    Number.isFinite(stats.avg_processing_time) &&
    typeof stats.articles_processed === 'number' &&
    Number.isFinite(stats.articles_processed) &&
    typeof stats.last_update === 'number' &&
    Number.isFinite(stats.last_update)
  );
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
    // Ignore parse failures and use fallback.
  }

  return `${fallback} (${statusText})`;
};

const getSentimentTone = (
  value: string
): { circleClassName: string; badgeClassName: string } => {
  const normalized = value.toLowerCase();
  if (normalized === 'positive') {
    return {
      circleClassName:
        'bg-emerald-500/15 text-emerald-700 ring-1 ring-emerald-500/40 dark:text-emerald-300',
      badgeClassName: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    };
  }
  if (normalized === 'negative') {
    return {
      circleClassName: 'bg-rose-500/15 text-rose-700 ring-1 ring-rose-500/40 dark:text-rose-300',
      badgeClassName: 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300',
    };
  }
  if (normalized === 'neutral') {
    return {
      circleClassName:
        'bg-amber-500/15 text-amber-700 ring-1 ring-amber-500/40 dark:text-amber-300',
      badgeClassName: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    };
  }
  return {
    circleClassName: 'bg-muted text-foreground ring-1 ring-border',
    badgeClassName: 'border-border/80 bg-muted/80 text-muted-foreground',
  };
};

export default function AnalyticsPage() {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setLoading(true);
      setAnalyticsError(null);
      try {
        const response = await fetch('/api/analytics');
        if (!response.ok) {
          setAnalyticsData(null);
          setAnalyticsError(
            await getResponseErrorMessage(response, 'Failed to fetch analytics data')
          );
          return;
        }
        const data: unknown = await response.json();
        if (!isAnalyticsData(data)) {
          setAnalyticsData(null);
          setAnalyticsError('Unexpected analytics response format.');
          return;
        }
        setAnalyticsData(data);
      } catch (error) {
        setAnalyticsData(null);
        setAnalyticsError('Network error while loading analytics data.');
        if (process.env.NODE_ENV === 'development') {
          console.warn('Failed to fetch analytics data', error);
        }
      } finally {
        setLoading(false);
        setRetrying(false);
      }
    };

    void fetchAnalytics();
  }, [retryTick]);

  const handleRetry = () => {
    setRetrying(true);
    setRetryTick((previous) => previous + 1);
  };

  if (loading) {
    return (
      <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
        <div
          className="flex min-h-[50vh] items-center justify-center"
          role="status"
          aria-live="polite"
          aria-label="Loading analytics"
        >
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
        </div>
      </Layout>
    );
  }

  if (!analyticsData) {
    return (
      <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
        <section className="mx-auto max-w-2xl py-10">
          <Card className="border-destructive/50 bg-destructive/5" role="alert" aria-live="assertive">
            <CardContent className="space-y-4 p-6 text-center">
              <p className="text-base font-medium text-destructive">
                {analyticsError || 'Failed to load analytics data. Please try again later.'}
              </p>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className="gap-1.5"
                disabled={retrying}
                onClick={handleRetry}
              >
                <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
                {retrying ? 'Retrying...' : 'Retry'}
              </Button>
            </CardContent>
          </Card>
        </section>
      </Layout>
    );
  }

  // Helper function to create simple bar charts
  const renderBarChart = (
    data: { [key: string]: number } | Array<{ name: string; count: number }>,
    maxBars = 5
  ): React.JSX.Element => {
    let chartData: { label: string; value: number }[] = [];

    if (Array.isArray(data)) {
      chartData = data.slice(0, maxBars).map((item) => ({
        label: item.name,
        value: item.count,
      }));
    } else {
      chartData = Object.entries(data)
        .map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value)
        .slice(0, maxBars);
    }

    if (chartData.length === 0) {
      return (
        <p className="text-sm text-muted-foreground">
          No data available yet.
        </p>
      );
    }

    const maxValue = Math.max(...chartData.map((item) => item.value));

    return (
      <div className="mt-4 space-y-3">
        {chartData.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="truncate text-sm">{item.label}</p>
              <p className="text-sm font-semibold">{item.value}</p>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{
                  width: `${maxValue > 0 ? (item.value / maxValue) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  };

  const sentimentData = Object.entries(analyticsData.sentiment_distribution).map(
    ([key, value]) => ({
      label: key,
      value,
      tone: getSentimentTone(key),
    })
  );

  // Calculate sentiment totals for percentage
  const totalSentiment = sentimentData.reduce((sum, item) => sum + item.value, 0);
  const totalSentimentForPercent = totalSentiment > 0 ? totalSentiment : 1;

  return (
    <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
      <section className="space-y-2">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Analytics Dashboard
        </h1>
        <p className="text-sm text-muted-foreground sm:text-base">
          Last updated:{' '}
          {new Date(analyticsData.processing_stats.last_update).toLocaleString()}
        </p>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-12">
        {/* Summary Cards */}
        <Card className="lg:col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Articles Processed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-semibold">
              {analyticsData.processing_stats.articles_processed}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Avg. processing time:{' '}
              {analyticsData.processing_stats.avg_processing_time.toFixed(2)}s
            </p>
          </CardContent>
        </Card>

        {/* Sentiment Distribution */}
        <Card className="lg:col-span-8">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Sentiment Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {sentimentData.map((item) => (
                <div
                  key={item.label}
                  className="rounded-lg border border-border/70 bg-background/70 p-4 text-center"
                >
                  <div
                    className={`mx-auto mb-2 flex h-16 w-16 items-center justify-center rounded-full text-lg font-semibold tabular-nums ${item.tone.circleClassName}`}
                  >
                    {item.value}
                  </div>
                  <p className="text-sm font-medium capitalize">{item.label}</p>
                  <Badge variant="outline" className={`mt-2 text-xs ${item.tone.badgeClassName}`}>
                    {((item.value / totalSentimentForPercent) * 100).toFixed(1)}%
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Source Distribution */}
        <Card className="lg:col-span-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Top News Sources</CardTitle>
          </CardHeader>
          <CardContent>{renderBarChart(analyticsData.source_distribution)}</CardContent>
        </Card>

        {/* Top Entities */}
        <Card className="lg:col-span-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Top Entities Mentioned</CardTitle>
          </CardHeader>
          <CardContent>{renderBarChart(analyticsData.top_entities)}</CardContent>
        </Card>

        {/* Top Topics */}
        <Card className="lg:col-span-12">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Top Topics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {analyticsData.top_topics.map((topic, index) => (
                <article
                  key={`${topic.name}-${index}`}
                  className="flex h-full flex-col items-center justify-center rounded-lg border border-primary/30 bg-primary/10 p-3 text-center"
                >
                  <p className="text-2xl font-semibold tabular-nums text-primary">{topic.count}</p>
                  <p className="mt-1 text-sm text-primary/90">{topic.name}</p>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </Layout>
  );
}
