import { Article as SharedArticle } from '../../src/types';

export type Article = SharedArticle;

export interface ArticleFilters {
  source?: string;
  sentiment?: string;
  topic?: string;
  search?: string;
  sortBy?: 'date' | 'relevance' | 'sentiment';
  sortOrder?: 'asc' | 'desc';
  startDate?: string;
  endDate?: string;
  limit?: number;
  offset?: number;
}
