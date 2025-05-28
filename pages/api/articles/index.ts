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

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    // Parse query parameters
    const { 
      limit = '10',
      source,
      sentiment,
      topic,
      search,
      sort_by,
      sort_order = 'desc'
    } = req.query;

    // Get articles
    let articles = getMockArticles();
    
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
    }
    
    // Apply limit
    const limitNum = parseInt(String(limit), 10);
    articles = articles.slice(0, limitNum);
    
    res.status(200).json(articles);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
