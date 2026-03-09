import { SourceType, SourceCategory } from '../../src/types';

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

export type { SourceType, SourceCategory };
