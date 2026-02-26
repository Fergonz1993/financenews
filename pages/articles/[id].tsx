import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { ArrowLeft, Bookmark, BookmarkCheck, ExternalLink, Share2 } from 'lucide-react';
import Layout from '../../components/Layout';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';

// Article type definition
type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  content: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
  is_saved?: boolean;
};

export default function ArticlePage() {
  const router = useRouter();
  const { id } = router.query;
  const userId =
    (Array.isArray(router.query.user_id) ? router.query.user_id[0] : router.query.user_id) ||
    'user1';
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!id) return;

    const fetchArticle = async () => {
      setLoading(true);
      try {
        const articleId = Array.isArray(id) ? id[0] : String(id);
        const response = await fetch(`/api/articles/${encodeURIComponent(articleId)}?user_id=${encodeURIComponent(userId)}`);
        if (!response.ok) throw new Error('Failed to fetch article');
        const data = await response.json();
        setArticle(data);
        setSaved(data.is_saved || false);
      } catch (error) {
        console.error('Error fetching article:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [id, userId]);

  const toggleSaved = async () => {
    if (!article) return;
    
    try {
      const endpoint = `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(article.id)}`;
      const method = saved ? 'DELETE' : 'POST';
      
      const response = await fetch(endpoint, { method });
      if (!response.ok) throw new Error('Failed to update saved status');
      
      setSaved(!saved);
    } catch (error) {
      console.error('Error updating saved status:', error);
    }
  };

  const sentimentStyle = useMemo(() => {
    if (!article?.sentiment) {
      return {
        className: 'border-border/80 bg-muted text-muted-foreground',
        label: '',
      };
    }

    switch (article.sentiment.toLowerCase()) {
      case 'positive':
        return {
          className:
            'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
          label: 'Positive',
        };
      case 'negative':
        return {
          className: 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300',
          label: 'Negative',
        };
      case 'neutral':
        return {
          className:
            'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
          label: 'Neutral',
        };
      default:
        return {
          className: 'border-border/80 bg-muted text-muted-foreground',
          label: article.sentiment,
        };
    }
  }, [article?.sentiment]);

  const marketImpact = article?.market_impact_score;
  const marketImpactPercent = Math.max(
    0,
    Math.min(100, Number(((marketImpact ?? 0) * 100).toFixed(2)))
  );

  const getMarketImpactClassName = (value: number): string => {
    if (value > 70) return 'bg-rose-500';
    if (value > 40) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  const formatPublishedAt = (value: string): string => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return parsed.toLocaleString();
  };

  if (loading) {
    return (
      <Layout title="Loading Article" description="Loading article...">
        <div className="flex min-h-[50vh] items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
        </div>
      </Layout>
    );
  }

  if (!article) {
    return (
      <Layout title="Article Not Found" description="The requested article could not be found">
        <div className="py-10 text-center">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Article Not Found</h1>
          <Button
            className="mt-4 gap-2"
            onClick={() => router.push('/articles')}
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Articles
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={article.title} description={article.summarized_headline || article.title}>
      <Button
        variant="outline"
        className="mb-4 gap-2"
        onClick={() => router.push('/articles')}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Articles
      </Button>

      <Card className="border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-xs text-muted-foreground">
              {article.source} • {formatPublishedAt(article.published_at)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant={saved ? 'default' : 'outline'}
                size="sm"
                className="gap-1.5"
                onClick={toggleSaved}
              >
                {saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
                {saved ? 'Saved' : 'Save'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={async () => {
                  try {
                    if (!navigator.clipboard?.writeText) {
                      throw new Error('Clipboard API unavailable');
                    }
                    await navigator.clipboard.writeText(window.location.href);
                    alert('Link copied to clipboard!');
                  } catch (error) {
                    console.error('Error copying link:', error);
                    alert('Unable to copy link. Please copy the URL from your browser.');
                  }
                }}
              >
                <Share2 className="h-4 w-4" />
                Share
              </Button>
            </div>
          </div>

          <CardTitle className="text-balance text-2xl sm:text-3xl">{article.title}</CardTitle>
        </CardHeader>

        <CardContent className="space-y-6">
        {article.sentiment && (
          <Badge variant="outline" className={sentimentStyle.className}>
            {sentimentStyle.label} sentiment ({(article.sentiment_score ?? 0).toFixed(2)})
          </Badge>
        )}

        {/* AI Summary */}
          <Card className="border-border/70 bg-background/70">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">AI Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {article.summarized_headline ? (
                <p className="text-sm text-foreground sm:text-base">{article.summarized_headline}</p>
              ) : (
                <p className="text-sm text-muted-foreground">No summary available for this article.</p>
              )}

              {article.summary_bullets && article.summary_bullets.length > 0 && (
                <>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Key Points
                  </h2>
                  <ul className="list-disc space-y-2 pl-5 text-sm text-foreground">
                    {article.summary_bullets.map((bullet, index) => (
                      <li key={`${bullet}-${index}`}>{bullet}</li>
                    ))}
                  </ul>
                </>
              )}
            </CardContent>
          </Card>

        {/* Full Article Content */}
          <section className="space-y-2">
            <h2 className="text-xl font-semibold">Full Article</h2>
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground sm:text-base">
              {article.content}
            </p>
          </section>

          <div>
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              Read original article at {article.source}
            </a>
          </div>

          <div className="h-px w-full bg-border/70" />

          {/* Related Information */}
          <section className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Key Entities
              </h2>
              <div className="flex flex-wrap gap-2">
                {article.key_entities && article.key_entities.length > 0 ? (
                  article.key_entities.map((entity) => (
                    <Badge key={entity} variant="outline" className="border-border/80">
                      {entity}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No entities available.</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Topics
              </h2>
              <div className="flex flex-wrap gap-2">
                {article.topics && article.topics.length > 0 ? (
                  article.topics.map((topic) => (
                    <Badge
                      key={topic}
                      variant="outline"
                      className="border-primary/40 bg-primary/5 text-primary"
                    >
                      {topic}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No topics available.</p>
                )}
              </div>
            </div>
          </section>

          {marketImpact !== undefined && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Market Impact Score
              </h2>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full ${getMarketImpactClassName(marketImpactPercent)}`}
                  style={{ width: `${marketImpactPercent}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {marketImpact < 0.3 ? 'Low impact' : marketImpact < 0.7 ? 'Moderate impact' : 'High impact'} -
                {' '}
                {marketImpactPercent.toFixed(0)}%
              </p>
            </section>
          )}
        </CardContent>
      </Card>
    </Layout>
  );
}
