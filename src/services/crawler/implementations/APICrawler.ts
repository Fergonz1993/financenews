import { BaseCrawler } from './BaseCrawler';
import { NewsSource, Article } from '../../../types';
import { generateArticleHash, logCrawlerActivity } from '../utils/crawler-utils';
import { format } from 'date-fns';

/**
 * Specialized crawler for API-based news sources
 */
export class APICrawler extends BaseCrawler {
  constructor(source: NewsSource) {
    super(source);
  }
  
  async fetchArticles(): Promise<Article[]> {
    if (!this.source.apiEndpoint) {
      logCrawlerActivity(`Missing API endpoint for source ${this.source.name}`, 'error');
      return [];
    }
    
    try {
      const url = new URL(this.source.apiEndpoint);
      
      // Add API key if available
      if (this.source.apiKey) {
        url.searchParams.append('apiKey', this.source.apiKey);
      }
      
      logCrawlerActivity(`Fetching data from API: ${url.toString()}`);
      const response = await fetch(url.toString(), {
        headers: {
          'User-Agent': this.source.userAgent || 'FinanceNewsBot/1.0'
        }
      });
      
      if (!response.ok) {
        throw new Error(`API responded with status: ${response.status}`);
      }
      
      const data = await response.json();
      const articles: Article[] = [];
      
      // Handle different API response structures
      // This is a generic implementation - customize based on actual API responses
      const items = data.articles || data.items || data.results || data.data || [];
      
      for (const item of items) {
        const article: Article = {
          title: item.title || 'Untitled',
          url: item.url || item.link || '',
          source: item.source?.name || this.source.name,
          sourceId: this.source.id,
          published_at: item.publishedAt || item.published_date || format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
          content: item.content || item.description || '',
          author: item.author || undefined,
          image_url: item.urlToImage || item.image || undefined,
          crawled_at: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
          hash: generateArticleHash(item.title || '', item.content || item.description || '')
        };
        
        articles.push(article);
      }
      
      logCrawlerActivity(`API Crawler: Successfully fetched ${articles.length} articles from ${this.source.name}`);
      return articles;
    } catch (error) {
      logCrawlerActivity(`Failed to fetch from API ${this.source.apiEndpoint}: ${error}`, 'error');
      return [];
    }
  }
}
