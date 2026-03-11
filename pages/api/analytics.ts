import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from './_utils/fastapiProxy';
import {
  getLocalAnalytics,
  isLocalApiFallbackEnabled,
} from './_utils/localDataFallback';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  try {
    const analytics = await fastApiRequest<Record<string, unknown>>({
      path: '/api/analytics',
      method: 'GET',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(analytics);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      applyProxyResponseHeaders(res, req, 'fallback_read_only');
      res.status(200).json(getLocalAnalytics());
      return;
    }
    sendProxyError(res, error, 'Failed to fetch analytics', req);
  }
}
