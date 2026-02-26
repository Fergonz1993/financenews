/**
 * Financial News Crawler Service
 * 
 * This service provides functionality to crawl, scrape, and aggregate financial news
 * from various sources including RSS feeds, websites, and APIs.
 */
import { crawlerScheduler } from './CrawlerScheduler';

// Export manager and scheduler
export { crawlerManager } from './CrawlerManager';
export { crawlerScheduler } from './CrawlerScheduler';

// Export crawler implementations
export { BaseCrawler } from './implementations/BaseCrawler';
export { RSSCrawler } from './implementations/RSSCrawler';
export { WebCrawler } from './implementations/WebCrawler';
export { APICrawler } from './implementations/APICrawler';

// Export utilities
export * from './utils/crawler-utils';

// Export default sources
export { defaultSources } from './data/default-sources';

/**
 * Initialize the crawler system
 */
export function initCrawlerSystem(autoStart: boolean = true): boolean {
  try {
    if (autoStart) {
      // Start the crawler scheduler
      crawlerScheduler.start();
      
      console.log('Crawler system initialized successfully');
    }
    return true;
  } catch (error) {
    console.error('Failed to initialize crawler system:', error);
    return false;
  }
}
