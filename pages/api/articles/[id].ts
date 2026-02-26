import { NextApiRequest, NextApiResponse } from 'next';
import {
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from '../_utils/fastapiProxy';
import {
  getLocalArticleById,
  isArticleSavedLocally,
  isLocalApiFallbackEnabled,
  queryLocalArticles,
} from '../_utils/localDataFallback';

function asSingle(value: string | string[] | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return Array.isArray(value) ? value[0] : value;
}

function toInt(value: unknown, defaultValue: number): number {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : defaultValue;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  const articleId = asSingle(req.query.id);
  if (!articleId) {
    res.status(400).json({ error: 'Invalid article ID' });
    return;
  }

  try {
    const userId = asSingle(req.query.user_id);
    const article = await fastApiRequest<Record<string, unknown>>({
      path: `/api/articles/${encodeURIComponent(articleId)}`,
      method: 'GET',
      query: userId ? { user_id: userId } : undefined,
      req,
    });
    res.status(200).json(article);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      if (articleId === 'count') {
        const fallback = queryLocalArticles({
          source: asSingle(req.query.source),
          sentiment: asSingle(req.query.sentiment),
          topic: asSingle(req.query.topic),
          search: asSingle(req.query.search),
          published_since: asSingle(req.query.published_since),
          published_until: asSingle(req.query.published_until),
          sort_by: asSingle(req.query.sort_by),
          sort_order: asSingle(req.query.sort_order) || 'desc',
          limit: Math.max(1, toInt(req.query.limit, 10)),
          offset: Math.max(0, toInt(req.query.offset, 0)),
        });
        res.setHeader('X-Data-Source', 'local-fallback');
        res.status(200).json({ total: fallback.total });
        return;
      }

      const localArticle = getLocalArticleById(articleId);
      if (!localArticle) {
        res.status(404).json({ error: 'Article not found' });
        return;
      }
      const userId = asSingle(req.query.user_id);
      const saved = userId ? isArticleSavedLocally(userId, articleId) : false;
      res.setHeader('X-Data-Source', 'local-fallback');
      res.status(200).json({
        ...localArticle,
        is_saved: saved,
      });
      return;
    }
    sendProxyError(res, error, 'Failed to fetch article');
  }
}
