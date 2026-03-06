import { NextApiRequest, NextApiResponse } from 'next';
import {
  FastApiProxyError,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendProxyError,
} from '../_utils/fastapiProxy';
import {
  getLocalCrawlerStats,
  isLocalApiFallbackEnabled,
  loadLocalSources,
} from '../_utils/localDataFallback';

type SourceRow = {
  id?: string;
  source_id?: number;
  name?: string;
  source_type?: string;
  enabled?: boolean;
  crawl_interval_minutes?: number;
};

type HealthRow = {
  source_id?: number;
  last_success_at?: string | null;
};

type IngestStatusRow = {
  scheduled_refresh_seconds?: number | null;
};

function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const detail = (payload as { detail?: unknown }).detail;
  return typeof detail === 'string' && detail.trim() ? detail : null;
}

function isDue(lastSuccessAt: string | null | undefined, frequencyMinutes: number): boolean {
  if (!lastSuccessAt) {
    return true;
  }
  const parsed = new Date(lastSuccessAt);
  if (!Number.isFinite(parsed.getTime())) {
    return true;
  }
  const frequencyMs = Math.max(frequencyMinutes, 1) * 60_000;
  return Date.now() - parsed.getTime() >= frequencyMs;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET', 'POST'])) {
    return;
  }

  try {
    if (req.method === 'GET') {
      const [sources, health, ingestStatus] = await Promise.all([
        fastApiRequest<SourceRow[]>({
          path: '/api/sources',
          method: 'GET',
          query: { include_disabled: 'true' },
          req,
        }),
        fastApiRequest<HealthRow[]>({
          path: '/api/ingestion/health',
          method: 'GET',
          req,
        }),
        fastApiRequest<IngestStatusRow>({
          path: '/api/ingest/status',
          method: 'GET',
          req,
        }),
      ]);

      const healthMap = new Map<number, HealthRow>();
      health.forEach((item) => {
        if (typeof item.source_id === 'number') {
          healthMap.set(item.source_id, item);
        }
      });

      const sourcesInfo = sources.map((source) => {
        const sourceId = source.source_id;
        const sourceHealth =
          typeof sourceId === 'number' ? healthMap.get(sourceId) : undefined;
        return {
          id: source.id,
          name: source.name,
          type: source.source_type || 'rss',
          isActive: Boolean(source.enabled),
          lastCrawled: sourceHealth?.last_success_at || null,
          crawlFrequency: source.crawl_interval_minutes || 30,
        };
      });

      const sourcesDueCrawling = sourcesInfo.filter(
        (source) =>
          source.isActive && isDue(source.lastCrawled ?? null, Number(source.crawlFrequency))
      ).length;
      const scheduledRefreshSeconds = Number(ingestStatus.scheduled_refresh_seconds || 0);
      const schedulerEnabled =
        Number.isFinite(scheduledRefreshSeconds) && scheduledRefreshSeconds > 0;

      res.status(200).json({
        totalSources: sourcesInfo.length,
        activeSources: sourcesInfo.filter((source) => source.isActive).length,
        sourcesDueCrawling,
        sourcesInfo,
        scheduler: {
          enabled: schedulerEnabled,
          intervalSeconds: schedulerEnabled ? scheduledRefreshSeconds : 0,
        },
      });
      return;
    }

    const action = String(req.body?.action || '').trim();
    if (!action) {
      res.status(400).json({ error: 'Invalid action' });
      return;
    }

    if (action === 'run_now') {
      try {
        const result = await fastApiRequest<Record<string, unknown>>({
          path: '/api/admin/ingest/run',
          method: 'POST',
          req,
        });
        const runId = typeof result.run_id === 'string' ? result.run_id : null;
        const statusText =
          typeof result.status === 'string' && result.status.trim()
            ? result.status
            : 'Crawl queued';
        res.status(200).json({
          status: statusText,
          queued: true,
          alreadyRunning: false,
          newArticles: 0,
          runId,
          startedAt: result.started_at ?? null,
          sourceFilters: Array.isArray(result.source_filters) ? result.source_filters : [],
        });
        return;
      } catch (error) {
        if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
          res.setHeader('X-Data-Source', 'local-fallback');
          res.status(200).json({
            status: 'Backend unavailable. Showing cached local data.',
            queued: false,
            alreadyRunning: false,
            error: false,
            newArticles: 0,
            runId: null,
            fallback: true,
          });
          return;
        }
        if (error instanceof FastApiProxyError) {
          const detail = extractDetail(error.payload) || error.message || 'Failed to queue crawl';
          if (error.status === 409) {
            res.status(200).json({
              status: detail || 'Ingestion already running',
              queued: false,
              alreadyRunning: true,
              error: false,
              newArticles: 0,
              runId: null,
            });
            return;
          }
          res.status(200).json({
            status: 'Unable to queue crawl',
            queued: false,
            alreadyRunning: false,
            error: true,
            errors: [detail],
            backendStatus: error.status,
            newArticles: 0,
            runId: null,
          });
          return;
        }
        throw error;
      }
    }

    if (action === 'start_scheduler' || action === 'stop_scheduler') {
      try {
        const ingestStatus = await fastApiRequest<IngestStatusRow>({
          path: '/api/ingest/status',
          method: 'GET',
          req,
        });
        const intervalSeconds = Number(ingestStatus.scheduled_refresh_seconds || 0);
        const intervalMessage =
          intervalSeconds > 0
            ? `Current configured interval is ${intervalSeconds} seconds.`
            : 'Current interval is disabled (0 seconds).';
        res.status(200).json({
          status:
            action === 'start_scheduler'
              ? `Scheduler is controlled by NEWS_INGEST_INTERVAL_SECONDS at backend startup. ${intervalMessage}`
              : `Scheduler stop is not runtime-mutable; adjust backend env and restart. ${intervalMessage}`,
          action,
          scheduler: {
            enabled: intervalSeconds > 0,
            intervalSeconds: intervalSeconds > 0 ? intervalSeconds : 0,
          },
        });
        return;
      } catch (error) {
        if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
          res.setHeader('X-Data-Source', 'local-fallback');
          res.status(200).json({
            status: 'Backend unavailable. Scheduler controls require backend mode.',
            action,
            scheduler: {
              enabled: false,
              intervalSeconds: 0,
            },
            fallback: true,
          });
          return;
        }
        throw error;
      }
    }

    res.status(400).json({ error: 'Invalid action' });
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      const localSources = loadLocalSources();
      const localStats = getLocalCrawlerStats();
      res.setHeader('X-Data-Source', 'local-fallback');
      res.status(200).json({
        ...localStats,
        sourcesInfo: localSources.map((source) => ({
          id: source.id,
          name: source.name,
          type: source.type,
          isActive: source.isActive,
          lastCrawled: source.lastCrawled || null,
          crawlFrequency: source.crawlFrequency,
        })),
      });
      return;
    }
    sendProxyError(res, error, 'Crawler API proxy error');
  }
}
