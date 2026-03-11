export type SourceType = 'rss' | 'scrape' | 'api';
export type SourceCategory =
  | 'finance'
  | 'economics'
  | 'markets'
  | 'technology'
  | 'general'
  | 'news';

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
  lastCrawled?: Date | string | null;
  isActive: boolean;
  useProxy: boolean;
  respectRobotsTxt: boolean;
  waitTime?: number;
  userAgent?: string;
}

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
