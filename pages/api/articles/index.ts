import { NextApiRequest, NextApiResponse } from 'next';
import { crawlerManager } from '../../../lib/crawlers/CrawlerManager';
import { Article, ArticleFilters } from '../../../lib/models/Article';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    // Parse query parameters
    const { 
      limit = '10',
      offset = '0',
      source,
      sentiment,
      topic,
      search,
      sort_by,
      sort_order = 'desc',
      startDate,
      endDate
    } = req.query;

    try {
      // Get articles from the crawler manager
      let articles = await crawlerManager.getArticles();
      
      // If no articles yet, start a crawl
      if (articles.length === 0) {
        await crawlerManager.runCrawlers();
        articles = await crawlerManager.getArticles();
      }
      
      // Apply filters
      if (source) {
        articles = articles.filter(a => a.source.toLowerCase() === String(source).toLowerCase());
      }
      if (sentiment) {
        articles = articles.filter(a => a.sentiment === sentiment);
      }
      if (topic) {
        articles = articles.filter(a => a.topics?.includes(String(topic)));
      }
      
      // Apply date filters
      if (startDate) {
        const startDateObj = new Date(String(startDate));
        articles = articles.filter(a => new Date(a.published_at) >= startDateObj);
      }
      if (endDate) {
        const endDateObj = new Date(String(endDate));
        articles = articles.filter(a => new Date(a.published_at) <= endDateObj);
      }
      
      // Apply search
      if (search) {
        const searchLower = String(search).toLowerCase();
        articles = articles.filter(a => 
          a.title.toLowerCase().includes(searchLower) || 
          a.content.toLowerCase().includes(searchLower) ||
          a.key_entities?.some(entity => entity.toLowerCase().includes(searchLower)) ||
          a.topics?.some(topic => topic.toLowerCase().includes(searchLower))
        );
      }
      
      // Apply sorting
      if (sort_by) {
        const reverse = sort_order === 'desc';
        if (sort_by === 'date') {
          articles = articles.sort((a, b) => {
            return reverse 
              ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
              : new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
          });
        } else if (sort_by === 'relevance') {
          articles = articles.sort((a, b) => {
            return reverse 
              ? (b.market_impact_score || 0) - (a.market_impact_score || 0)
              : (a.market_impact_score || 0) - (b.market_impact_score || 0);
          });
        } else if (sort_by === 'sentiment') {
          articles = articles.sort((a, b) => {
            return reverse 
              ? (b.sentiment_score || 0) - (a.sentiment_score || 0)
              : (a.sentiment_score || 0) - (b.sentiment_score || 0);
          });
        }
      } else {
        // Default sort by date, newest first
        articles = articles.sort((a, b) => 
          new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
        );
      }
      
      // Apply pagination
      const limitNum = parseInt(String(limit), 10);
      const offsetNum = parseInt(String(offset), 10);
      const paginatedArticles = articles.slice(offsetNum, offsetNum + limitNum);
      
      // Return with count for pagination
      res.status(200).json({
        articles: paginatedArticles,
        total: articles.length,
        limit: limitNum,
        offset: offsetNum
      });
    } catch (error) {
      console.error('Error fetching articles:', error);
      res.status(500).json({ error: 'Failed to fetch articles' });
    }
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
