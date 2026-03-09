import { NextApiRequest, NextApiResponse } from 'next';
import { checkBackendHealth, enforceMethod } from './_utils/fastapiProxy';
import { localDataDiagnostics } from './_utils/localDataFallback';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  const [backend, local] = await Promise.all([
    checkBackendHealth(),
    Promise.resolve(localDataDiagnostics()),
  ]);

  const fallbackReady = local.fallback_enabled;
  const mode = backend.reachable ? 'backend' : fallbackReady ? 'fallback' : 'degraded';
  const statusCode = mode === 'degraded' ? 503 : 200;

  res.status(statusCode).json({
    status: mode === 'degraded' ? 'degraded' : 'ok',
    mode,
    checked_at: new Date().toISOString(),
    backend,
    local,
  });
}
