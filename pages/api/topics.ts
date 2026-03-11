import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from './_utils/fastapiProxy';
import {
  getLocalTopicOptions,
  isLocalApiFallbackEnabled,
} from './_utils/localDataFallback';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  try {
    const topics = await fastApiRequest<Array<Record<string, unknown>>>({
      path: '/api/topics',
      method: 'GET',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(topics);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      applyProxyResponseHeaders(res, req, 'fallback_read_only');
      res.status(200).json(getLocalTopicOptions());
      return;
    }
    sendProxyError(res, error, 'Failed to fetch topics', req);
  }
}
