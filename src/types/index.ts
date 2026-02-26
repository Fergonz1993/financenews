/**
 * Central type definitions for the Finance News application
 */

// Article related types
export interface Article {
  id?: string;
  title: string;
  url: string;
  source: string;
  sourceId: string;
  published_at: string;
  content: string;
  author?: string;
  image_url?: string;
  summarized_headline?: string;
  summary?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
  crawled_at: string;
  hash: string;
  is_saved?: boolean;
}

export interface ArticleSummary {
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
  url?: string;
}

export interface ArticlesResponse {
  articles: ArticleSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ArticleFilters {
  source?: string;
  sentiment?: string;
  topic?: string;
  startDate?: string;
  endDate?: string;
  search?: string;
  sortBy?: 'date' | 'relevance' | 'sentiment';
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// News source related types
export type SourceType = 'rss' | 'scrape' | 'api';
export type SourceCategory = 'finance' | 'economics' | 'markets' | 'technology' | 'general';

export interface NewsSource {
  id: string;
  name: string;
  url: string;
  type: SourceType;
  category: SourceCategory;
  selector?: {
    title?: string;
    content?: string;
    date?: string;
    author?: string;
    image?: string;
  };
  rssUrl?: string;
  apiEndpoint?: string;
  apiKey?: string;
  crawlFrequency: number;
  lastCrawled?: Date;
  isActive: boolean;
  useProxy: boolean;
  respectRobotsTxt: boolean;
  waitTime?: number;
  userAgent?: string;
}

// Analytics related types
export interface AnalyticsData {
  sentimentDistribution: {
    positive: number;
    neutral: number;
    negative: number;
  };
  topSources: Array<{
    name: string;
    count: number;
  }>;
  topTopics: Array<{
    name: string;
    count: number;
  }>;
  articlesByDate: Array<{
    date: string;
    count: number;
  }>;
}

// User related types
export interface User {
  id: string;
  name: string;
  email: string;
  preferences?: UserPreferences;
}

export interface UserPreferences {
  darkMode?: boolean;
  sources?: string[];
  topics?: string[];
  notificationsEnabled?: boolean;
}
