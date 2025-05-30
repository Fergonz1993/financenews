import { NextApiRequest, NextApiResponse } from 'next';
import { crawlerManager } from '../../../lib/crawlers/CrawlerManager';
import { Article } from '../../../lib/models/Article';

// Mock function to check if an article is saved by a user
// In a production app, this would be replaced with a real database check
const isArticleSaved = (userId: string, articleId: string): boolean => {
  // For demo purposes, we'll return true for specific combinations
  return (userId === 'user1' && articleId === 'article-1') || 
         (userId === 'user1' && articleId === 'article-3');
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    const { id } = req.query;
    const userId = req.query.user_id as string | undefined;
    
    if (!id || Array.isArray(id)) {
      return res.status(400).json({ error: 'Invalid article ID' });
    }
    
    try {
      // Get articles from crawler manager
      const articles = await crawlerManager.getArticles();
      
      // First try to find by ID
      let article = articles.find(a => a.id === id);
      
      // If not found by ID, try by hash (URL might have changed)
      if (!article) {
        article = articles.find(a => a.hash === id);
      }
      
      // If still not found, try by URL match
      if (!article) {
        article = articles.find(a => a.url.includes(id));
      }
      
      if (!article) {
        return res.status(404).json({ error: 'Article not found' });
      }
      
      // Create a copy of the article to avoid modifying the original
      const articleResponse = { ...article };
      
      // If user_id is provided, check if the article is saved
      if (userId) {
        articleResponse.is_saved = isArticleSaved(userId, id);
      }
      
      res.status(200).json(articleResponse);
    } catch (error) {
      console.error('Error fetching article:', error);
      res.status(500).json({ error: 'Failed to fetch article' });
    }
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
