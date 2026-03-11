import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  checkBackendHealth,
  enforceMethod,
} from './_utils/fastapiProxy';
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
  const mode = backend.reachable
    ? 'backend'
    : fallbackReady
      ? 'fallback_read_only'
      : 'degraded';
  const statusCode = mode === 'degraded' ? 503 : 200;

  applyProxyResponseHeaders(res, req, mode);
  res.status(statusCode).json({
    status: mode === 'degraded' ? 'degraded' : 'ok',
    mode,
    checked_at: new Date().toISOString(),
    source_of_truth: backend.reachable ? 'postgres' : 'local_json_cache',
    backend,
    local,
  });
}
