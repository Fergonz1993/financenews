import { NewsSource } from '../../../types';
import { Article } from '../../../types';
import { checkRobotsTxt, delay, logCrawlerActivity } from '../utils/crawler-utils';

/**
 * Base abstract class for all crawler implementations
 */
export abstract class BaseCrawler {
  protected source: NewsSource;
  
  constructor(source: NewsSource) {
    this.source = source;
  }
  
  /**
   * Abstract method to fetch articles that must be implemented by all crawler types
   */
  abstract fetchArticles(): Promise<Article[]>;
  
  /**
   * Check if it's allowed to crawl based on robots.txt
   */
  protected async isAllowedByRobots(url: string): Promise<boolean> {
    if (!this.source.respectRobotsTxt) {
      return true;
    }
    
    const userAgent = this.source.userAgent || 'FinanceNewsBot/1.0';
    return await checkRobotsTxt(url, userAgent);
  }
  
  /**
   * Wait according to politeness configuration
   */
  protected async waitPolitely(): Promise<void> {
    if (this.source.waitTime) {
      await delay(this.source.waitTime);
    }
  }
  
  /**
   * Track crawl statistics and update last crawled timestamp
   */
  protected updateCrawlStats(articleCount: number): void {
    this.source.lastCrawled = new Date();
    logCrawlerActivity(`Crawled ${this.source.name}: found ${articleCount} articles`);
  }
  
  /**
   * Execute the crawler with error handling and logging
   */
  async run(): Promise<Article[]> {
    if (!this.source.isActive) {
      logCrawlerActivity(`Skipping inactive source: ${this.source.name}`, 'info');
      return [];
    }
    
    try {
      logCrawlerActivity(`Started crawling ${this.source.name}`);
      const articles = await this.fetchArticles();
      this.updateCrawlStats(articles.length);
      return articles;
    } catch (error) {
      logCrawlerActivity(`Error crawling ${this.source.name}: ${error}`, 'error');
      return [];
    }
  }
}
