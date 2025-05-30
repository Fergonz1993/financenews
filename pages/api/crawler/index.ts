import { NextApiRequest, NextApiResponse } from 'next';
import { crawlerManager } from '../../../lib/crawlers/CrawlerManager';
import { crawlerScheduler } from '../../../lib/crawlers/CrawlerScheduler';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Only allow GET and POST methods
  if (req.method !== 'GET' && req.method !== 'POST') {
    res.setHeader('Allow', ['GET', 'POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  try {
    if (req.method === 'GET') {
      // Get crawler status and statistics
      const sources = crawlerManager.getSources();
      const dueSources = crawlerManager.findSourcesDueCrawling();
      
      return res.status(200).json({
        totalSources: sources.length,
        activeSources: sources.filter(s => s.isActive).length,
        sourcesDueCrawling: dueSources.length,
        sourcesInfo: sources.map(s => ({
          id: s.id,
          name: s.name,
          type: s.type,
          isActive: s.isActive,
          lastCrawled: s.lastCrawled,
          crawlFrequency: s.crawlFrequency
        }))
      });
    }
    
    if (req.method === 'POST') {
      // Handle different actions
      const { action } = req.body;
      
      switch (action) {
        case 'start_scheduler':
          crawlerScheduler.start();
          return res.status(200).json({ status: 'Scheduler started' });
          
        case 'stop_scheduler':
          crawlerScheduler.stop();
          return res.status(200).json({ status: 'Scheduler stopped' });
          
        case 'run_now':
          const articleCount = await crawlerScheduler.runImmediately();
          return res.status(200).json({ 
            status: 'Crawl completed',
            newArticles: articleCount
          });
          
        default:
          return res.status(400).json({ error: 'Invalid action' });
      }
    }
  } catch (error) {
    console.error('Crawler API error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
