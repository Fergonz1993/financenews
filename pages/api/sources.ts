import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    // Mock data
    const sources = [
      { id: "financial-times", name: "Financial Times" },
      { id: "bloomberg", name: "Bloomberg" },
      { id: "wall-street-journal", name: "Wall Street Journal" },
      { id: "reuters", name: "Reuters" },
      { id: "cnbc", name: "CNBC" },
    ];
    
    res.status(200).json(sources);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
