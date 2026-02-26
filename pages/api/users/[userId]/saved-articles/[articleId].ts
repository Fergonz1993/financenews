import { NextApiRequest, NextApiResponse } from 'next';
import {
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from '../../../_utils/fastapiProxy';
import {
  isLocalApiFallbackEnabled,
  markArticleSavedLocally,
  isArticleSavedLocally,
} from '../../../_utils/localDataFallback';

function asSingle(value: string | string[] | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return Array.isArray(value) ? value[0] : value;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET', 'POST', 'DELETE'])) {
    return;
  }

  const userId = asSingle(req.query.userId);
  const articleId = asSingle(req.query.articleId);
  if (!userId || !articleId) {
    res.status(400).json({ error: 'Missing userId or articleId' });
    return;
  }

  try {
    if (req.method === 'POST') {
      const payload = await fastApiRequest<Record<string, unknown>>({
        path: `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(articleId)}`,
        method: 'POST',
        req,
      });
      res.status(200).json(payload);
      return;
    }

    if (req.method === 'DELETE') {
      const payload = await fastApiRequest<Record<string, unknown>>({
        path: `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(articleId)}`,
        method: 'DELETE',
        req,
      });
      res.status(200).json(payload);
      return;
    }

    const status = await fastApiRequest<Record<string, unknown>>({
      path: `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(articleId)}/status`,
      method: 'GET',
      req,
    });
    res.status(200).json(status);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      res.setHeader('X-Data-Source', 'local-fallback');

      if (req.method === 'POST') {
        res.status(200).json(markArticleSavedLocally(userId, articleId, true));
        return;
      }

      if (req.method === 'DELETE') {
        res.status(200).json(markArticleSavedLocally(userId, articleId, false));
        return;
      }

      res.status(200).json({
        user_id: userId,
        article_id: articleId,
        is_saved: isArticleSavedLocally(userId, articleId),
      });
      return;
    }
    sendProxyError(res, error, 'Saved article proxy failure');
  }
}
