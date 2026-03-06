import { NextApiRequest, NextApiResponse } from 'next';
import { enforceMethod, fastApiRequest, sendProxyError } from '../_utils/fastapiProxy';

function asSingle(value: string | string[] | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return Array.isArray(value) ? value[0] : value;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET', 'PUT', 'POST'])) {
    return;
  }

  try {
    if (req.method === 'GET') {
      const payload = await fastApiRequest<Record<string, unknown>>({
        path: '/api/user/settings',
        method: 'GET',
        query: {
          user_id: asSingle(req.query.user_id),
        },
        req,
      });
      res.status(200).json(payload);
      return;
    }

    const payload = await fastApiRequest<Record<string, unknown>>({
      path: '/api/user/settings',
      method: req.method === 'POST' ? 'POST' : 'PUT',
      query: {
        user_id: asSingle(req.query.user_id),
      },
      body: req.body || {},
      req,
    });
    res.status(200).json(payload);
  } catch (error) {
    sendProxyError(res, error, 'User settings proxy error');
  }
}
