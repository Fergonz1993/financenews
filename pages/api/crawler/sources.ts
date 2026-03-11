import { NextApiRequest, NextApiResponse } from 'next';
import {
  applyProxyResponseHeaders,
  enforceMethod,
  fastApiRequest,
  isBackendUnavailableError,
  sendReadOnlyFallback,
  sendProxyError,
} from '../_utils/fastapiProxy';
import {
  isLocalApiFallbackEnabled,
  loadLocalSources,
} from '../_utils/localDataFallback';

type SourceRow = {
  id: string;
  source_id?: number;
  name: string;
  url: string;
  source_type?: string;
  source_category?: string | null;
  crawl_interval_minutes?: number;
  enabled?: boolean;
};

type HealthRow = {
  source_id?: number;
  last_success_at?: string | null;
};

type CrawlerSourcePayload = {
  id?: string;
  name?: string;
  url?: string;
  type?: string;
  category?: string;
  crawlFrequency?: number;
  isActive?: boolean;
};

function mapSourceForAdmin(source: SourceRow, healthMap: Map<number, HealthRow>) {
  const sourceId = source.source_id;
  const sourceHealth =
    typeof sourceId === 'number' ? healthMap.get(sourceId) : undefined;
  return {
    id: source.id,
    name: source.name,
    url: source.url,
    type: source.source_type || 'rss',
    category: source.source_category || 'news',
    crawlFrequency: source.crawl_interval_minutes || 30,
    isActive: Boolean(source.enabled),
    useProxy: false,
    respectRobotsTxt: true,
    lastCrawled: sourceHealth?.last_success_at || null,
  };
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!enforceMethod(req, res, ['GET', 'POST', 'DELETE'])) {
    return;
  }

  try {
    if (req.method === 'GET') {
      const [sources, health] = await Promise.all([
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
      ]);
      const healthMap = new Map<number, HealthRow>();
      health.forEach((item) => {
        if (typeof item.source_id === 'number') {
          healthMap.set(item.source_id, item);
        }
      });
      applyProxyResponseHeaders(res, req);
      res.status(200).json(sources.map((source) => mapSourceForAdmin(source, healthMap)));
      return;
    }

    if (req.method === 'POST') {
      const sourceData = req.body as CrawlerSourcePayload;
      if (!sourceData.name || !sourceData.url || !sourceData.type) {
        res.status(400).json({ error: 'Missing required fields' });
        return;
      }

      const upserted = await fastApiRequest<SourceRow>({
        path: '/api/sources',
        method: 'POST',
        body: {
          id: sourceData.id || undefined,
          name: sourceData.name,
          url: sourceData.url,
          source_type: sourceData.type,
          source_category: sourceData.category || 'news',
          crawl_interval_minutes: Number(sourceData.crawlFrequency || 30),
          enabled: sourceData.isActive !== false,
          connector_type: sourceData.type,
          legal_basis: 'public_web_feed',
          rate_profile: 'standard',
        },
        req,
      });
      applyProxyResponseHeaders(res, req);
      res.status(200).json({
        id: upserted.id,
        name: upserted.name,
        url: upserted.url,
        type: upserted.source_type || 'rss',
        category: upserted.source_category || 'news',
        crawlFrequency: upserted.crawl_interval_minutes || 30,
        isActive: Boolean(upserted.enabled),
      });
      return;
    }

    const idRaw = req.query.id;
    const sourceId = Array.isArray(idRaw) ? idRaw[0] : idRaw;
    if (!sourceId) {
      res.status(400).json({ error: 'Source ID is required' });
      return;
    }

    await fastApiRequest({
      path: `/api/sources/${encodeURIComponent(sourceId)}`,
      method: 'DELETE',
      req,
    });
    applyProxyResponseHeaders(res, req);
    res.status(200).json({ status: 'Source removed' });
  } catch (error) {
    if (isLocalApiFallbackEnabled() && isBackendUnavailableError(error)) {
      if (req.method === 'GET') {
        const localSources = loadLocalSources().map((source) => ({
          id: source.id,
          name: source.name,
          url: source.url,
          type: source.type,
          category: source.category || 'news',
          crawlFrequency: source.crawlFrequency || 30,
          isActive: source.isActive,
          useProxy: source.useProxy,
          respectRobotsTxt: source.respectRobotsTxt,
          lastCrawled: source.lastCrawled || null,
          selector: source.selector,
          rssUrl: source.rssUrl,
          apiEndpoint: source.apiEndpoint,
          apiKey: source.apiKey,
          userAgent: source.userAgent,
          waitTime: source.waitTime,
        }));
        applyProxyResponseHeaders(res, req, 'fallback_read_only');
        res.status(200).json(localSources);
        return;
      }

      if (req.method === 'POST') {
        sendReadOnlyFallback(
          res,
          req,
          'Source changes are disabled while the backend is unavailable.'
        );
        return;
      }

      if (req.method === 'DELETE') {
        sendReadOnlyFallback(
          res,
          req,
          'Source changes are disabled while the backend is unavailable.'
        );
        return;
      }
    }
    sendProxyError(res, error, 'Sources API proxy error', req);
  }
}
