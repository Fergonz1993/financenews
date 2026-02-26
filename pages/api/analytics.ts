import { NextApiRequest, NextApiResponse } from 'next';
import {
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
    res.status(200).json(analytics);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      res.setHeader('X-Data-Source', 'local-fallback');
      res.status(200).json(getLocalAnalytics());
      return;
    }
    sendProxyError(res, error, 'Failed to fetch analytics');
  }
}
