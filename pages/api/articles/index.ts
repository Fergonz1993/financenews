import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from '../_utils/fastapiProxy';
import {
  isLocalApiFallbackEnabled,
  queryLocalArticles,
} from '../_utils/localDataFallback';

function toInt(value: unknown, defaultValue: number): number {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : defaultValue;
}

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

  const limit = Math.max(1, toInt(req.query.limit, 10));
  const offset = Math.max(0, toInt(req.query.offset, 0));

  const startDate = asSingle(req.query.startDate);
  const endDate = asSingle(req.query.endDate);

  const query: Record<string, unknown> = {
    source: asSingle(req.query.source),
    sentiment: asSingle(req.query.sentiment),
    topic: asSingle(req.query.topic),
    search: asSingle(req.query.search),
    sort_by: asSingle(req.query.sort_by),
    sort_order: asSingle(req.query.sort_order) || 'desc',
    published_since: startDate,
    published_until: endDate,
  };

  try {
    const [articles, totalPayload] = await Promise.all([
      fastApiRequest<Array<Record<string, unknown>>>({
        path: '/api/articles',
        method: 'GET',
        query: {
          ...query,
          limit,
          offset,
        },
        req,
      }),
      fastApiRequest<{ total?: number }>({
        path: '/api/articles/count',
        method: 'GET',
        query,
        req,
      }),
    ]);

    applyProxyResponseHeaders(res, req);
    res.status(200).json({
      articles,
      total: Number.isFinite(totalPayload?.total) ? Number(totalPayload.total) : articles.length,
      limit,
      offset,
    });
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      const fallback = queryLocalArticles({
        ...query,
        limit,
        offset,
      });
      applyProxyResponseHeaders(res, req, 'fallback_read_only');
      res.status(200).json(fallback);
      return;
    }
    sendProxyError(res, error, 'Failed to fetch articles', req);
  }
}
