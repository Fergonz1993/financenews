import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'GET') {
    // Mock data
    const topics = [
      { id: "technology", name: "Technology" },
      { id: "economy", name: "Economy" },
      { id: "markets", name: "Markets" },
      { id: "policy", name: "Policy" },
      { id: "earnings", name: "Earnings" },
    ];
    
    res.status(200).json(topics);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
