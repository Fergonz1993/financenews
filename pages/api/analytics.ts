import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    // Mock analytics data
    const analytics = {
      sentiment_distribution: { positive: 42, neutral: 28, negative: 14 },
      source_distribution: {
        "Financial Times": 25,
        "Bloomberg": 22,
        "Wall Street Journal": 18,
        "Reuters": 12,
        "CNBC": 7
      },
      top_entities: [
        { name: "Apple", count: 15 },
        { name: "Tesla", count: 12 },
        { name: "Federal Reserve", count: 10 },
        { name: "Microsoft", count: 8 },
        { name: "Amazon", count: 7 },
      ],
      top_topics: [
        { name: "Technology", count: 28 },
        { name: "Economy", count: 22 },
        { name: "Markets", count: 18 },
        { name: "Policy", count: 12 },
        { name: "Earnings", count: 10 },
      ],
      processing_stats: {
        avg_processing_time: 1.5,
        articles_processed: 84,
        last_update: Date.now(),
      }
    };
    
    res.status(200).json(analytics);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
