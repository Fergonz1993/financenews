import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  sendProxyError,
} from '../../_utils/fastapiProxy';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  try {
    const payload = await fastApiRequest<Record<string, unknown>>({
      path: '/api/ingest/continuous/status',
      method: 'GET',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(payload);
  } catch (error) {
    sendProxyError(res, error, 'Continuous ingest status proxy error', req);
  }
}
