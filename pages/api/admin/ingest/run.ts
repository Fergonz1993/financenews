import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from '../../_utils/fastapiProxy';

type TriggerResponse = Record<string, unknown>;

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['POST'])) {
    return;
  }

  try {
    const body = req.body && typeof req.body === 'object' ? req.body : {};
    const payload = {
      reason: body.reason || 'manual trigger via API route',
      source_filters: body.source_filters || null,
      source_urls: body.source_urls || null,
      source_ids: body.source_ids || null,
      idempotency_key: body.idempotency_key || undefined,
    };

    const response = await fastApiRequest<TriggerResponse>({
      path: '/api/admin/ingest/run',
      method: 'POST',
      body: payload,
      req,
    });

    applyProxyResponseHeaders(res, req);
    res.status(202).json(response);
  } catch (error) {
    if (isBackendUnavailableError(error)) {
      applyProxyResponseHeaders(res, req, 'backend_error');
      res.status(502).json({
        status: 'backend_unavailable',
        message: 'Unable to reach backend ingest control endpoint.',
      });
      return;
    }
    sendProxyError(res, error, 'Admin ingest run proxy error', req);
  }
}
