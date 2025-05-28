import { NextApiRequest, NextApiResponse } from 'next';

// Article type definition
type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  content: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
  is_saved?: boolean;
};

// Mock data for initial testing
const getMockArticles = (): Article[] => {
  const articles = [
    {
      id: 'article-1',
      title: "Apple Reports Record Profits in Q3",
      url: "https://example.com/apple-profits",
      source: "Financial Times",
      published_at: "2025-05-27T10:00:00Z",
      content: "Apple Inc. reported record profits in the third quarter, exceeding analyst expectations...",
      summarized_headline: "Summary: Apple Reports Record Profits in Q3",
      summary_bullets: ["Key point 1", "Key point 2", "Key point 3"],
      sentiment: "positive",
      sentiment_score: 0.7,
      market_impact_score: 0.8,
      key_entities: ["Apple", "NASDAQ"],
      topics: ["Technology", "Earnings"],
    },
    {
      id: 'article-2',
      title: "Tesla Announces New Battery Technology",
      url: "https://example.com/tesla-battery",
      source: "Bloomberg",
      published_at: "2025-05-26T15:30:00Z",
      content: "Tesla unveiled a new battery technology that extends vehicle range by 50%...",
      summarized_headline: "Summary: Tesla Announces New Battery Technology",
      summary_bullets: ["Key point 1", "Key point 2", "Key point 3"],
      sentiment: "neutral",
      sentiment_score: 0.5,
      market_impact_score: 0.6,
      key_entities: ["Tesla", "Battery"],
      topics: ["Technology", "Innovation"],
    },
    {
      id: 'article-3',
      title: "Federal Reserve Signals Interest Rate Cut",
      url: "https://example.com/fed-rate-cut",
      source: "Wall Street Journal",
      published_at: "2025-05-25T12:15:00Z",
      content: "The Federal Reserve indicated it may cut interest rates in the next meeting...",
      summarized_headline: "Summary: Federal Reserve Signals Interest Rate Cut",
      summary_bullets: ["Key point 1", "Key point 2", "Key point 3"],
      sentiment: "negative",
      sentiment_score: 0.2,
      market_impact_score: 0.4,
      key_entities: ["Federal Reserve", "Interest Rates"],
      topics: ["Economy", "Policy"],
    },
  ];
  
  return articles;
};

// Mock function to check if an article is saved by a user
const isArticleSaved = (userId: string, articleId: string): boolean => {
  // In a real app, this would check a database
  // For demo purposes, we'll return true for specific combinations
  return (userId === 'user1' && articleId === 'article-1') || 
         (userId === 'user1' && articleId === 'article-3');
};

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    const { id } = req.query;
    const userId = req.query.user_id as string | undefined;
    
    if (!id || Array.isArray(id)) {
      return res.status(400).json({ error: 'Invalid article ID' });
    }
    
    const articles = getMockArticles();
    const article = articles.find(a => a.id === id);
    
    if (!article) {
      return res.status(404).json({ error: 'Article not found' });
    }
    
    // If user_id is provided, check if the article is saved
    if (userId) {
      article.is_saved = isArticleSaved(userId, id);
    }
    
    res.status(200).json(article);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
