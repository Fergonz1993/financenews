import { BaseCrawler } from './BaseCrawler';
import { Article, NewsSource } from '../../../types';
import Parser from 'rss-parser';
import { generateArticleHash, extractTextFromHtml, logCrawlerActivity } from '../utils/crawler-utils';
import { format } from 'date-fns';

type RssContentField = {
  'content:encoded'?: string;
  'media:content'?: {
    $?: {
      url?: string;
    };
  };
};

/**
 * Specialized crawler for RSS feed sources
 */
export class RSSCrawler extends BaseCrawler {
  private parser: Parser;
  
  constructor(source: NewsSource) {
    super(source);
    this.parser = new Parser({
      headers: {
        'User-Agent': this.source.userAgent || 'FinanceNewsBot/1.0',
      },
      customFields: {
        item: ['content:encoded', 'media:content', 'description']
      }
    });
  }
  
  async fetchArticles(): Promise<Article[]> {
    if (!this.source.rssUrl) {
      logCrawlerActivity(`Missing RSS URL for source ${this.source.name}`, 'error');
      return [];
    }
    
    try {
      const feed = await this.parser.parseURL(this.source.rssUrl);
      const articles: Article[] = [];
      
      for (const item of feed.items) {
        await this.waitPolitely();
        
        if (!(await this.isAllowedByRobots(item.link || ''))) {
          logCrawlerActivity(`Skipping disallowed URL: ${item.link}`, 'warn');
          continue;
        }
        
        // Get content from the best available field
        const feedItem = item as Parser.Item & RssContentField;
        const content = feedItem['content:encoded'] || feedItem.content || item.description || '';
        const textContent = extractTextFromHtml(content);
        
        const publishedDate = item.pubDate ? new Date(item.pubDate) : new Date();
        
        const article: Article = {
          title: item.title || 'Untitled',
          url: item.link || '',
          source: this.source.name,
          sourceId: this.source.id,
          published_at: format(publishedDate, "yyyy-MM-dd'T'HH:mm:ss'Z'"),
          content: textContent,
          author: item.creator || item.author || undefined,
          image_url: feedItem['media:content']?.$?.url || undefined,
          crawled_at: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
          hash: generateArticleHash(item.title || '', textContent)
        };
        
        articles.push(article);
      }
      
      logCrawlerActivity(`RSS Crawler: Successfully fetched ${articles.length} articles from ${this.source.name}`);
      return articles;
    } catch (error) {
      logCrawlerActivity(`Failed to fetch RSS feed from ${this.source.rssUrl}: ${error}`, 'error');
      return [];
    }
  }
}
