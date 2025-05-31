import { CronJob } from 'cron';
import { crawlerManager } from './CrawlerManager';
import { logCrawlerActivity } from './utils/crawler-utils';

/**
 * Scheduler for running crawlers at regular intervals
 */
export class CrawlerScheduler {
  private mainJob: CronJob;
  private sourcesCheckJob: CronJob;
  private isRunning: boolean = false;
  
  constructor() {
    // Main job runs every 30 minutes
    this.mainJob = new CronJob('0 */30 * * * *', this.runScheduledCrawl.bind(this));
    
    // Check for sources due for crawling every 10 minutes
    this.sourcesCheckJob = new CronJob('0 */10 * * * *', this.checkDueSources.bind(this));
  }
  
  /**
   * Start the scheduler
   */
  start(): void {
    if (!this.isRunning) {
      this.mainJob.start();
      this.sourcesCheckJob.start();
      this.isRunning = true;
      logCrawlerActivity('Crawler scheduler started');
      
      // Run immediately on start
      this.runScheduledCrawl();
    }
  }
  
  /**
   * Stop the scheduler
   */
  stop(): void {
    if (this.isRunning) {
      this.mainJob.stop();
      this.sourcesCheckJob.stop();
      this.isRunning = false;
      logCrawlerActivity('Crawler scheduler stopped');
    }
  }
  
  /**
   * Run the crawler for all sources
   */
  async runScheduledCrawl(): Promise<void> {
    logCrawlerActivity('Running scheduled crawl');
    try {
      const articleCount = await crawlerManager.runCrawlers();
      logCrawlerActivity(`Scheduled crawl completed. Found ${articleCount} new articles`);
    } catch (error) {
      logCrawlerActivity(`Error in scheduled crawl: ${error}`, 'error');
    }
  }
  
  /**
   * Check for sources that are due for crawling
   */
  async checkDueSources(): Promise<void> {
    try {
      const dueSources = crawlerManager.findSourcesDueCrawling();
      if (dueSources.length > 0) {
        logCrawlerActivity(`Found ${dueSources.length} sources due for crawling`);
        await crawlerManager.runCrawlers();
      }
    } catch (error) {
      logCrawlerActivity(`Error checking due sources: ${error}`, 'error');
    }
  }
  
  /**
   * Run a one-off crawl immediately
   */
  async runImmediately(): Promise<number> {
    logCrawlerActivity('Running immediate crawl');
    try {
      const articleCount = await crawlerManager.runCrawlers();
      logCrawlerActivity(`Immediate crawl completed. Found ${articleCount} new articles`);
      return articleCount;
    } catch (error) {
      logCrawlerActivity(`Error in immediate crawl: ${error}`, 'error');
      return 0;
    }
  }
}

// Create and export a singleton instance
export const crawlerScheduler = new CrawlerScheduler();
