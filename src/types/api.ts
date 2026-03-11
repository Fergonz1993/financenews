export interface ApiArticleSummary {
  id?: string;
  title: string;
  source: string;
  published_at: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  topics?: string[];
  key_entities?: string[];
  url?: string;
  is_saved?: boolean;
}

export interface ApiArticle extends ApiArticleSummary {
  url: string;
  content?: string;
}

export interface ApiArticlesResponse {
  articles: ApiArticleSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiTopicOption {
  id: string;
  name: string;
}

export interface ApiSourceRecord {
  id: string;
  source_id?: number;
  source_key?: string;
  name: string;
  url: string;
  source_type?: string;
  source_category?: string | null;
  connector_type?: string | null;
  terms_url?: string | null;
  legal_basis?: string | null;
  provider_domain?: string | null;
  rate_profile?: string | null;
  requires_api_key?: boolean;
  requires_user_agent?: boolean;
  user_agent?: string | null;
  enabled?: boolean;
  crawl_interval_minutes?: number;
  rate_limit_per_minute?: number;
}

export interface ApiAnalyticsResponse {
  sentiment_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  top_entities: Array<{ name: string; count: number }>;
  top_topics: Array<{ name: string; count: number }>;
  processing_stats: Record<string, number>;
}

export interface ApiContinuousRunnerStatus {
  enabled?: boolean;
  running?: boolean;
  interval_seconds?: number;
  cycle_count?: number;
  last_cycle_at?: string | null;
  next_cycle_at?: string | null;
  last_cycle_articles?: number;
  total_articles_ingested?: number;
  connectors?: Record<string, unknown>;
  recent_errors?: Array<{ time: string; error: string; type: string }>;
}

export interface ApiIngestStatusResponse {
  run_id?: string;
  status?: string;
  items_seen?: number;
  items_stored?: number;
  stored_article_count?: number;
  scheduled_refresh_seconds?: number;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  freshness_lag_seconds?: number | null;
  freshness_threshold_seconds?: number | null;
  freshness_state?: 'fresh' | 'stale' | 'unknown';
  data_mode?: 'backend' | 'fallback_read_only' | 'degraded' | string;
  source_of_truth?: string;
  continuous_runner?: ApiContinuousRunnerStatus;
}
