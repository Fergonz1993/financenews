import { NextApiRequest, NextApiResponse } from 'next';
import { enforceMethod, fastApiRequest, sendProxyError } from '../../../_utils/fastapiProxy';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['POST'])) {
    return;
  }

  const connectorRaw = req.query.connector;
  const connector = Array.isArray(connectorRaw) ? connectorRaw[0] : connectorRaw;
  if (!connector) {
    res.status(400).json({ error: 'connector is required' });
    return;
  }

  try {
    const payload = await fastApiRequest<Record<string, unknown>>({
      path: `/api/ingest/continuous/connectors/${encodeURIComponent(connector)}`,
      method: 'POST',
      body: req.body,
      req,
    });
    res.status(200).json(payload);
  } catch (error) {
    sendProxyError(res, error, 'Connector toggle proxy error');
  }
}
