import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendReadOnlyFallback,
  sendProxyError,
} from '../../../_utils/fastapiProxy';
import {
  isLocalApiFallbackEnabled,
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
      applyProxyResponseHeaders(res, req);
      res.status(200).json(payload);
      return;
    }

    if (req.method === 'DELETE') {
      const payload = await fastApiRequest<Record<string, unknown>>({
        path: `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(articleId)}`,
        method: 'DELETE',
        req,
      });
      applyProxyResponseHeaders(res, req);
      res.status(200).json(payload);
      return;
    }

    const status = await fastApiRequest<Record<string, unknown>>({
      path: `/api/users/${encodeURIComponent(userId)}/saved-articles/${encodeURIComponent(articleId)}/status`,
      method: 'GET',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(status);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      if (req.method === 'POST') {
        sendReadOnlyFallback(
          res,
          req,
          'Saved-article updates are disabled while the backend is unavailable.'
        );
        return;
      }

      if (req.method === 'DELETE') {
        sendReadOnlyFallback(
          res,
          req,
          'Saved-article updates are disabled while the backend is unavailable.'
        );
        return;
      }

      applyProxyResponseHeaders(res, req, 'fallback_read_only');
      res.status(200).json({
        user_id: userId,
        article_id: articleId,
        is_saved: isArticleSavedLocally(userId, articleId),
      });
      return;
    }
    sendProxyError(res, error, 'Saved article proxy failure', req);
  }
}
