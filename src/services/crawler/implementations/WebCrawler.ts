import { BaseCrawler } from './BaseCrawler';
import { NewsSource, Article } from '../../../types';
import puppeteer from 'puppeteer';
import cheerio from 'cheerio';
import { generateArticleHash, logCrawlerActivity, extractTextFromHtml } from '../utils/crawler-utils';
import { format } from 'date-fns';

/**
 * Specialized crawler for web scraping sources
 */
export class WebCrawler extends BaseCrawler {
  constructor(source: NewsSource) {
    super(source);
  }
  
  async fetchArticles(): Promise<Article[]> {
    const articles: Article[] = [];
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    try {
      // Check if allowed by robots.txt
      if (!(await this.isAllowedByRobots(this.source.url))) {
        logCrawlerActivity(`Skipping disallowed URL: ${this.source.url}`, 'warn');
        await browser.close();
        return [];
      }
      
      logCrawlerActivity(`Fetching main page from ${this.source.url}`);
      const page = await browser.newPage();
      
      // Set user agent
      if (this.source.userAgent) {
        await page.setUserAgent(this.source.userAgent);
      }
      
      // Visit the main page
      await page.goto(this.source.url, { waitUntil: 'networkidle2' });
      
      // Wait a bit for any JavaScript to execute
      await this.waitPolitely();
      
      // Get page content
      const content = await page.content();
      const $ = cheerio.load(content);
      
      // Find all links that might be articles
      const links = new Set<string>();
      $('a').each((i, el) => {
        const href = $(el).attr('href');
        if (!href) return;
        
        // Filter links that look like news articles
        if (href.match(/article|news|story|finance|market|economy|release|press|blog/i)) {
          // Make sure it's an absolute URL
          let fullUrl = href;
          if (href.startsWith('/')) {
            fullUrl = `${this.source.url.replace(/\/$/, '')}${href}`;
          } else if (!href.startsWith('http')) {
            fullUrl = `${this.source.url.replace(/\/$/, '')}/${href.replace(/^\.\//, '')}`;
          }
          
          links.add(fullUrl);
        }
      });
      
      logCrawlerActivity(`Found ${links.size} potential article links from ${this.source.url}`);
      
      // Limit the number of articles to crawl to avoid overloading
      const articlesToProcess = Array.from(links).slice(0, 10);
      
      // Process each article link
      for (const link of articlesToProcess) {
        // Check if allowed by robots.txt
        if (!(await this.isAllowedByRobots(link))) {
          logCrawlerActivity(`Skipping disallowed URL: ${link}`, 'warn');
          continue;
        }
        
        try {
          logCrawlerActivity(`Processing article: ${link}`);
          await page.goto(link, { waitUntil: 'networkidle2' });
          await this.waitPolitely();
          
          const articleHtml = await page.content();
          const $article = cheerio.load(articleHtml);
          
          // Extract article information using provided selectors
          const titleSelector = this.source.selector?.title || 'h1, .article-title, .post-title, .entry-title';
          const contentSelector = this.source.selector?.content || 'article, .article-body, .post-content, .entry-content';
          const dateSelector = this.source.selector?.date || 'time, .date, .article-date, .post-date, .published-date';
          const authorSelector = this.source.selector?.author || '.author, .byline, .article-author';
          const imageSelector = this.source.selector?.image || 'img.featured, .article-featured-image img, .post-thumbnail img';
          
          const title = $article(titleSelector).first().text().trim();
          const rawContent = $article(contentSelector).html() || '';
          const content = extractTextFromHtml(rawContent);
          const dateText = $article(dateSelector).first().text().trim() || 
                           $article(dateSelector).first().attr('datetime') || '';
          const author = $article(authorSelector).first().text().trim();
          const imageUrl = $article(imageSelector).first().attr('src');
          
          // Skip if no title or content
          if (!title || !content) {
            logCrawlerActivity(`Skipping article with missing title or content: ${link}`, 'warn');
            continue;
          }
          
          // Try to parse the date
          let publishedDate = new Date();
          try {
            if (dateText) {
              publishedDate = new Date(dateText);
              // If invalid date, use current date
              if (isNaN(publishedDate.getTime())) {
                publishedDate = new Date();
              }
            }
          } catch {
            // Use current date if parsing fails
            publishedDate = new Date();
          }
          
          const article: Article = {
            title,
            url: link,
            source: this.source.name,
            sourceId: this.source.id,
            published_at: format(publishedDate, "yyyy-MM-dd'T'HH:mm:ss'Z'"),
            content,
            author: author || undefined,
            image_url: imageUrl || undefined,
            crawled_at: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
            hash: generateArticleHash(title, content)
          };
          
          articles.push(article);
          logCrawlerActivity(`Successfully processed article: ${title}`);
        } catch (error) {
          logCrawlerActivity(`Error processing article ${link}: ${error}`, 'error');
        }
      }
      
    } catch (error) {
      logCrawlerActivity(`Web crawler error for ${this.source.name}: ${error}`, 'error');
    } finally {
      await browser.close();
    }
    
    return articles;
  }
}
