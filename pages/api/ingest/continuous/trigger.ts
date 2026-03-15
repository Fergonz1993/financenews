import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiAdminRequest,
  isMissingServerAdminCredentialsError,
  sendReadOnlyFallback,
  sendProxyError,
} from '../../_utils/fastapiProxy';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['POST'])) {
    return;
  }

  try {
    const payload = await fastApiAdminRequest<Record<string, unknown>>({
      path: '/api/ingest/continuous/trigger',
      method: 'POST',
      req,
      actor: 'next-continuous-trigger',
      role: 'ops',
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(payload);
  } catch (error) {
    if (isMissingServerAdminCredentialsError(error)) {
      sendReadOnlyFallback(
        res,
        req,
        'Continuous ingest triggers are disabled until explicit server-side admin credentials are configured.'
      );
      return;
    }
    sendProxyError(res, error, 'Continuous ingest trigger proxy error', req);
  }
}
