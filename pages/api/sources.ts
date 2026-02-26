import { NextApiRequest, NextApiResponse } from 'next';
import {
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from './_utils/fastapiProxy';
import {
  getLocalSourceOptions,
  isLocalApiFallbackEnabled,
} from './_utils/localDataFallback';

function asSingle(value: string | string[] | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return Array.isArray(value) ? value[0] : value;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  try {
    const sources = await fastApiRequest<Array<Record<string, unknown>>>({
      path: '/api/sources',
      method: 'GET',
      query: {
        source_category: asSingle(req.query.source_category),
        connector_type: asSingle(req.query.connector_type),
        include_disabled: asSingle(req.query.include_disabled),
      },
      req,
    });
    res.status(200).json(sources);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      res.setHeader('X-Data-Source', 'local-fallback');
      res.status(200).json(getLocalSourceOptions());
      return;
    }
    sendProxyError(res, error, 'Failed to fetch sources');
  }
}
