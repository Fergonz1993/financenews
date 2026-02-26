import { NextApiRequest, NextApiResponse } from 'next';
import {
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
    res.status(200).json(topics);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      res.setHeader('X-Data-Source', 'local-fallback');
      res.status(200).json(getLocalTopicOptions());
      return;
    }
    sendProxyError(res, error, 'Failed to fetch topics');
  }
}
