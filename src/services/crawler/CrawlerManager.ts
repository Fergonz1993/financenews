import { NewsSource, Article } from '../../types';
import { RSSCrawler } from './implementations/RSSCrawler';
import { WebCrawler } from './implementations/WebCrawler';
import { APICrawler } from './implementations/APICrawler';
import { BaseCrawler } from './implementations/BaseCrawler';
import { logCrawlerActivity } from './utils/crawler-utils';
import fs from 'fs';
import path from 'path';

// Default sources configuration
import { defaultSources } from './data/default-sources';

/**
 * CrawlerManager coordinates the different crawler implementations
 * and manages data persistence
 */
export class CrawlerManager {
  private sources: NewsSource[] = [];
  private dataDir: string = path.join(process.cwd(), 'data');
  private sourcesFile: string = path.join(this.dataDir, 'sources.json');
  private articlesFile: string = path.join(this.dataDir, 'articles.json');
  private crawlInProgress: boolean = false;
  
  constructor() {
    this.initDataDirectory();
    this.loadSources();
  }
  
  /**
   * Initialize data directory and files
   */
  private initDataDirectory(): void {
    // Create data directory if it doesn't exist
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
      logCrawlerActivity(`Created data directory at ${this.dataDir}`);
    }
    
    // Create sources file if it doesn't exist
    if (!fs.existsSync(this.sourcesFile)) {
      fs.writeFileSync(this.sourcesFile, JSON.stringify(defaultSources, null, 2));
      logCrawlerActivity(`Created default sources file at ${this.sourcesFile}`);
    }
    
    // Create articles file if it doesn't exist
    if (!fs.existsSync(this.articlesFile)) {
      fs.writeFileSync(this.articlesFile, JSON.stringify([]));
      logCrawlerActivity(`Created empty articles file at ${this.articlesFile}`);
    }
  }
  
  /**
   * Load news sources from file
   */
  private loadSources(): void {
    try {
      const data = fs.readFileSync(this.sourcesFile, 'utf8');
      this.sources = JSON.parse(data);
      logCrawlerActivity(`Loaded ${this.sources.length} sources from ${this.sourcesFile}`);
    } catch (error) {
      logCrawlerActivity(`Error loading sources: ${error}`, 'error');
      this.sources = defaultSources;
    }
  }
  
  /**
   * Save news sources to file
   */
  private saveSources(): void {
    try {
      fs.writeFileSync(this.sourcesFile, JSON.stringify(this.sources, null, 2));
      logCrawlerActivity(`Saved ${this.sources.length} sources to ${this.sourcesFile}`);
    } catch (error) {
      logCrawlerActivity(`Error saving sources: ${error}`, 'error');
    }
  }
  
  /**
   * Get all sources
   */
  getSources(): NewsSource[] {
    return this.sources;
  }
  
  /**
   * Add or update a source
   */
  addOrUpdateSource(source: NewsSource): NewsSource {
    const index = this.sources.findIndex(s => s.id === source.id);
    if (index !== -1) {
      this.sources[index] = source;
      logCrawlerActivity(`Updated source: ${source.name}`);
    } else {
      // Generate a new ID if none is provided
      if (!source.id) {
        source.id = Date.now().toString();
      }
      this.sources.push(source);
      logCrawlerActivity(`Added new source: ${source.name}`);
    }
    
    this.saveSources();
    return source;
  }
  
  /**
   * Remove a source
   */
  removeSource(id: string): boolean {
    const initialLength = this.sources.length;
    this.sources = this.sources.filter(s => s.id !== id);
    
    const removed = this.sources.length < initialLength;
    if (removed) {
      logCrawlerActivity(`Removed source with ID: ${id}`);
      this.saveSources();
    }
    
    return removed;
  }
  
  /**
   * Create the appropriate crawler based on source type
   */
  private createCrawler(source: NewsSource): BaseCrawler {
    switch (source.type) {
      case 'rss':
        return new RSSCrawler(source);
      case 'scrape':
        return new WebCrawler(source);
      case 'api':
        return new APICrawler(source);
      default:
        throw new Error(`Unknown source type: ${source.type}`);
    }
  }
  
  /**
   * Load articles from file
   */
  async getArticles(): Promise<Article[]> {
    try {
      const data = fs.readFileSync(this.articlesFile, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      logCrawlerActivity(`Error loading articles: ${error}`, 'error');
      return [];
    }
  }
  
  /**
   * Save articles to file
   */
  private async saveArticles(articles: Article[]): Promise<void> {
    try {
      // Deduplicate articles by hash
      const uniqueArticles = articles.reduce((acc, current) => {
        if (!acc.find(item => item.hash === current.hash)) {
          acc.push(current);
        }
        return acc;
      }, [] as Article[]);
      
      fs.writeFileSync(this.articlesFile, JSON.stringify(uniqueArticles, null, 2));
      logCrawlerActivity(`Saved ${uniqueArticles.length} articles to ${this.articlesFile}`);
    } catch (error) {
      logCrawlerActivity(`Error saving articles: ${error}`, 'error');
    }
  }
  
  /**
   * Merge new articles with existing ones, handling duplicates
   */
  private async mergeArticles(newArticles: Article[]): Promise<void> {
    try {
      const existingArticles = await this.getArticles();
      
      // Create a hash map of existing articles for faster lookup
      const existingHashes = new Set(existingArticles.map(article => article.hash));
      
      // Filter out duplicates and add only new articles
      const uniqueNewArticles = newArticles.filter(article => !existingHashes.has(article.hash));
      
      if (uniqueNewArticles.length > 0) {
        // Add new articles to the beginning (most recent first)
        const combinedArticles = [...uniqueNewArticles, ...existingArticles];
        
        // Limit to 1000 articles to prevent the file from growing too large
        const limitedArticles = combinedArticles.slice(0, 1000);
        
        await this.saveArticles(limitedArticles);
        logCrawlerActivity(`Added ${uniqueNewArticles.length} new articles, total count: ${limitedArticles.length}`);
      } else {
        logCrawlerActivity('No new articles found');
      }
    } catch (error) {
      logCrawlerActivity(`Error merging articles: ${error}`, 'error');
    }
  }
  
  /**
   * Run crawlers for each active source
   */
  async runCrawlers(): Promise<number> {
    if (this.crawlInProgress) {
      logCrawlerActivity('Crawl already in progress, skipping', 'warn');
      return 0;
    }
    
    this.crawlInProgress = true;
    let totalNewArticles = 0;
    
    try {
      logCrawlerActivity('Started crawling process');
      
      const activeSources = this.sources.filter(source => source.isActive);
      logCrawlerActivity(`Found ${activeSources.length} active sources to crawl`);
      
      // Process sources sequentially to avoid overloading
      for (const source of activeSources) {
        try {
          const crawler = this.createCrawler(source);
          const articles = await crawler.run();
          
          if (articles.length > 0) {
            totalNewArticles += articles.length;
            await this.mergeArticles(articles);
            
            // Update source with last crawled timestamp
            source.lastCrawled = new Date();
            this.saveSources();
          }
        } catch (error) {
          logCrawlerActivity(`Error crawling source ${source.name}: ${error}`, 'error');
        }
      }
      
      logCrawlerActivity(`Crawling process completed. Total new articles: ${totalNewArticles}`);
    } finally {
      this.crawlInProgress = false;
    }
    
    return totalNewArticles;
  }
  
  /**
   * Find sources that are due for crawling based on their frequency
   */
  findSourcesDueCrawling(): NewsSource[] {
    const now = new Date();
    
    return this.sources.filter(source => {
      if (!source.isActive) return false;
      
      if (!source.lastCrawled) return true;
      
      const lastCrawled = new Date(source.lastCrawled);
      const minutesSinceLastCrawl = (now.getTime() - lastCrawled.getTime()) / (1000 * 60);
      
      return minutesSinceLastCrawl >= source.crawlFrequency;
    });
  }
}

// Create and export a singleton instance
export const crawlerManager = new CrawlerManager();
