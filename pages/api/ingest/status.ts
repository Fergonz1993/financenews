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
  localDataDiagnostics,
} from '../_utils/localDataFallback';

const FALLBACK_FRESHNESS_THRESHOLD_SECONDS = 172800;

function getFallbackFreshnessState(
  lagSeconds: number | null
): 'fresh' | 'stale' | 'unknown' {
  if (lagSeconds === null || !Number.isFinite(lagSeconds)) {
    return 'unknown';
  }
  return lagSeconds <= FALLBACK_FRESHNESS_THRESHOLD_SECONDS ? 'fresh' : 'stale';
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET'])) {
    return;
  }

  try {
    const payload = await fastApiRequest<Record<string, unknown>>({
      path: '/api/ingest/status',
      method: 'GET',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json(payload);
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      const diagnostics = localDataDiagnostics();
      const freshnessLagSeconds = diagnostics.freshness_lag_seconds;

      applyProxyResponseHeaders(res, req, 'fallback_read_only');
      res.status(200).json({
        run_id: null,
        status: 'fallback_read_only',
        items_seen: 0,
        items_stored: 0,
        stored_article_count: diagnostics.local_articles_count,
        scheduled_refresh_seconds: 0,
        last_success_at: diagnostics.latest_article_at,
        last_failure_at: null,
        freshness_lag_seconds: freshnessLagSeconds,
        freshness_threshold_seconds: FALLBACK_FRESHNESS_THRESHOLD_SECONDS,
        freshness_state: getFallbackFreshnessState(freshnessLagSeconds),
        data_mode: diagnostics.mode,
        source_of_truth: 'local_json_cache',
        continuous_runner: {
          enabled: false,
          running: false,
          interval_seconds: 0,
          cycle_count: 0,
          last_cycle_at: null,
          next_cycle_at: null,
          last_cycle_articles: 0,
          total_articles_ingested: 0,
          connectors: {},
          recent_errors: [],
        },
      });
      return;
    }
    sendProxyError(res, error, 'Ingest status proxy error', req);
  }
}
