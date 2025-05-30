import { NextApiRequest, NextApiResponse } from 'next';
import { crawlerManager } from '../../../lib/crawlers/CrawlerManager';
import { NewsSource } from '../../../lib/models/NewsSource';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // GET - List all sources
    if (req.method === 'GET') {
      const sources = crawlerManager.getSources();
      return res.status(200).json(sources);
    }
    
    // POST - Add a new source or update an existing one
    if (req.method === 'POST') {
      const sourceData = req.body as NewsSource;
      
      // Validate required fields
      if (!sourceData.name || !sourceData.url || !sourceData.type) {
        return res.status(400).json({ error: 'Missing required fields' });
      }
      
      const source = crawlerManager.addOrUpdateSource(sourceData);
      return res.status(200).json(source);
    }
    
    // DELETE - Remove a source
    if (req.method === 'DELETE') {
      const { id } = req.query;
      
      if (!id || typeof id !== 'string') {
        return res.status(400).json({ error: 'Source ID is required' });
      }
      
      const removed = crawlerManager.removeSource(id);
      
      if (removed) {
        return res.status(200).json({ status: 'Source removed' });
      } else {
        return res.status(404).json({ error: 'Source not found' });
      }
    }
    
    // Method not allowed
    res.setHeader('Allow', ['GET', 'POST', 'DELETE']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  } catch (error) {
    console.error('Sources API error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
