import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const frontendBaseUrl = process.env.SMOKE_FRONTEND_BASE_URL ?? 'http://127.0.0.1:3000';
const requestTimeoutMs = Number(process.env.SMOKE_TIMEOUT_MS ?? '15000');
const maxLatencyMs = Number(process.env.SMOKE_MAX_LATENCY_MS ?? '8000');
const smokeMetricsPath = process.env.SMOKE_METRICS_PATH ?? '';
const FALLBACK_READ_ONLY_MODE = 'fallback_read_only';

type SmokeMetric = {
  label: string;
  endpoint: string;
  elapsedMs: number;
  status: number;
};

type SmokeSummary = {
  checkedAt: string;
  baseUrl: string;
  mode: 'backend' | 'fallback_read_only' | 'unknown';
  maxLatencyMs: number;
  checks: SmokeMetric[];
};

const smokeSummary: SmokeSummary = {
  checkedAt: new Date().toISOString(),
  baseUrl: frontendBaseUrl,
  mode: 'unknown',
  maxLatencyMs,
  checks: [],
};

type TimedResponse = {
  status: number;
  elapsedMs: number;
  bodyText: string;
  headers: Headers;
};

function assertCondition(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseJson(label: string, bodyText: string): unknown {
  try {
    return JSON.parse(bodyText);
  } catch {
    throw new Error(`${label} returned invalid JSON: ${bodyText.slice(0, 240)}`);
  }
}

function headerValue(headers: Headers, name: string): string | null {
  const value = headers.get(name);
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed || null;
}

function assertProxyHeaders(
  result: TimedResponse,
  label: string,
  expectedDataSource?: string
): void {
  const requestId = headerValue(result.headers, 'x-request-id');
  assertCondition(requestId, `${label} missing X-Request-Id header`);

  const dataSource = headerValue(result.headers, 'x-data-source');
  assertCondition(dataSource, `${label} missing X-Data-Source header`);
  if (expectedDataSource) {
    assertCondition(
      dataSource === expectedDataSource,
      `${label} expected X-Data-Source=${expectedDataSource} but received ${dataSource}`
    );
  }
}

async function fetchTimed(
  url: string,
  label: string,
  init: RequestInit = {}
): Promise<TimedResponse> {
  const startedAt = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
  const bodyText = await response.text();
  const elapsedMs = Date.now() - startedAt;

  assertCondition(
    elapsedMs <= maxLatencyMs,
    `${label} exceeded latency budget (${elapsedMs}ms > ${maxLatencyMs}ms)`
  );

  return {
    status: response.status,
    elapsedMs,
    bodyText,
    headers: response.headers,
  };
}

async function requireStatus(
  url: string,
  label: string,
  expectedStatus: number,
  init: RequestInit = {}
): Promise<TimedResponse> {
  const result = await fetchTimed(url, label, init);
  assertCondition(
    result.status === expectedStatus,
    `${label} returned HTTP ${result.status}: ${result.bodyText.slice(0, 240)}`
  );
  return result;
}

async function requireHttp200(
  url: string,
  label: string,
  init: RequestInit = {}
): Promise<TimedResponse> {
  return requireStatus(url, label, 200, init);
}

async function checkHealth(): Promise<void> {
  const url = `${frontendBaseUrl}/api/health`;
  const result = await requireHttp200(url, 'health endpoint');
  const payload = parseJson('health endpoint', result.bodyText);

  assertCondition(isRecord(payload), 'Health payload must be an object');
  assertCondition(payload.status === 'ok', 'Health status must be "ok"');
  assertCondition(
    payload.mode === 'backend' || payload.mode === FALLBACK_READ_ONLY_MODE,
    'Health mode must be "backend" or "fallback_read_only"'
  );
  smokeSummary.mode = payload.mode as 'backend' | 'fallback_read_only';
  assertProxyHeaders(result, 'health endpoint', String(payload.mode));
  smokeSummary.checks.push({
    label: '/api/health',
    endpoint: '/api/health',
    elapsedMs: result.elapsedMs,
    status: result.status,
  });

  console.log(`PASS /api/health (${result.elapsedMs}ms) mode=${String(payload.mode)}`);
}

async function checkFrontendRoutes(): Promise<void> {
  const routes: Array<{ path: string; marker: string }> = [
    { path: '/', marker: 'Financial News Dashboard' },
    { path: '/articles', marker: 'Financial News Articles' },
    { path: '/analytics', marker: 'Analytics Dashboard' },
    { path: '/saved', marker: 'Saved Articles' },
    { path: '/settings', marker: 'Settings' },
    { path: '/admin/ingest', marker: 'Ingest Dashboard' },
    { path: '/admin/crawler', marker: 'News Crawler Admin' },
  ];

  for (const route of routes) {
    const result = await requireHttp200(
      `${frontendBaseUrl}${route.path}`,
      `frontend route ${route.path}`
    );
    assertCondition(
      result.bodyText.includes(route.marker),
      `Route ${route.path} missing marker "${route.marker}"`
    );
    smokeSummary.checks.push({
      label: `route ${route.path}`,
      endpoint: route.path,
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS route ${route.path} (${result.elapsedMs}ms)`);
  }
}

async function checkApiContracts(): Promise<void> {
  {
    const result = await requireHttp200(
      `${frontendBaseUrl}/api/articles?limit=1`,
      '/api/articles'
    );
    const payload = parseJson('/api/articles', result.bodyText);
    assertCondition(isRecord(payload), '/api/articles payload must be object');
    assertCondition(Array.isArray(payload.articles), '/api/articles.articles must be array');
    assertCondition(typeof payload.total === 'number', '/api/articles.total must be number');
    assertCondition(typeof payload.limit === 'number', '/api/articles.limit must be number');
    assertCondition(typeof payload.offset === 'number', '/api/articles.offset must be number');
    smokeSummary.checks.push({
      label: '/api/articles',
      endpoint: '/api/articles',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/articles (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(
      `${frontendBaseUrl}/api/articles/count`,
      '/api/articles/count'
    );
    const payload = parseJson('/api/articles/count', result.bodyText);
    assertCondition(isRecord(payload), '/api/articles/count payload must be object');
    assertCondition(typeof payload.total === 'number', '/api/articles/count.total must be number');
    smokeSummary.checks.push({
      label: '/api/articles/count',
      endpoint: '/api/articles/count',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/articles/count (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(
      `${frontendBaseUrl}/api/ingest/status`,
      '/api/ingest/status'
    );
    const payload = parseJson('/api/ingest/status', result.bodyText);
    assertCondition(isRecord(payload), '/api/ingest/status payload must be object');
    assertCondition(
      typeof payload.stored_article_count === 'number',
      '/api/ingest/status.stored_article_count must be number'
    );
    assertCondition(
      'freshness_lag_seconds' in payload,
      '/api/ingest/status must include freshness_lag_seconds'
    );
    assertCondition(
      'freshness_state' in payload,
      '/api/ingest/status must include freshness_state'
    );
    assertCondition(
      typeof payload.source_of_truth === 'string',
      '/api/ingest/status.source_of_truth must be string'
    );
    const expectedDataSource =
      typeof payload.data_mode === 'string' ? payload.data_mode : smokeSummary.mode;
    assertProxyHeaders(result, '/api/ingest/status', expectedDataSource);
    smokeSummary.checks.push({
      label: '/api/ingest/status',
      endpoint: '/api/ingest/status',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/ingest/status (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(`${frontendBaseUrl}/api/sources`, '/api/sources');
    const payload = parseJson('/api/sources', result.bodyText);
    assertCondition(Array.isArray(payload), '/api/sources payload must be array');
    assertProxyHeaders(result, '/api/sources');
    smokeSummary.checks.push({
      label: '/api/sources',
      endpoint: '/api/sources',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/sources (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(`${frontendBaseUrl}/api/topics`, '/api/topics');
    const payload = parseJson('/api/topics', result.bodyText);
    assertCondition(Array.isArray(payload), '/api/topics payload must be array');
    assertProxyHeaders(result, '/api/topics');
    smokeSummary.checks.push({
      label: '/api/topics',
      endpoint: '/api/topics',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/topics (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(`${frontendBaseUrl}/api/analytics`, '/api/analytics');
    const payload = parseJson('/api/analytics', result.bodyText);
    assertCondition(isRecord(payload), '/api/analytics payload must be object');
    assertCondition(
      isRecord(payload.sentiment_distribution),
      '/api/analytics.sentiment_distribution must be object'
    );
    assertCondition(
      isRecord(payload.source_distribution),
      '/api/analytics.source_distribution must be object'
    );
    assertCondition(Array.isArray(payload.top_entities), '/api/analytics.top_entities must be array');
    assertCondition(Array.isArray(payload.top_topics), '/api/analytics.top_topics must be array');
    assertCondition(
      isRecord(payload.processing_stats),
      '/api/analytics.processing_stats must be object'
    );
    assertProxyHeaders(result, '/api/analytics');
    smokeSummary.checks.push({
      label: '/api/analytics',
      endpoint: '/api/analytics',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/analytics (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(`${frontendBaseUrl}/api/crawler`, '/api/crawler');
    const payload = parseJson('/api/crawler', result.bodyText);
    assertCondition(isRecord(payload), '/api/crawler payload must be object');
    assertCondition(typeof payload.totalSources === 'number', '/api/crawler.totalSources must be number');
    assertCondition(typeof payload.activeSources === 'number', '/api/crawler.activeSources must be number');
    assertCondition(
      typeof payload.sourcesDueCrawling === 'number',
      '/api/crawler.sourcesDueCrawling must be number'
    );
    assertCondition(Array.isArray(payload.sourcesInfo), '/api/crawler.sourcesInfo must be array');
    assertCondition(isRecord(payload.scheduler), '/api/crawler.scheduler must be object');
    assertProxyHeaders(result, '/api/crawler');
    smokeSummary.checks.push({
      label: '/api/crawler',
      endpoint: '/api/crawler',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/crawler (${result.elapsedMs}ms)`);
  }

  {
    const result = await requireHttp200(
      `${frontendBaseUrl}/api/crawler/sources`,
      '/api/crawler/sources'
    );
    const payload = parseJson('/api/crawler/sources', result.bodyText);
    assertCondition(Array.isArray(payload), '/api/crawler/sources payload must be array');
    assertProxyHeaders(result, '/api/crawler/sources');
    smokeSummary.checks.push({
      label: '/api/crawler/sources',
      endpoint: '/api/crawler/sources',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/crawler/sources (${result.elapsedMs}ms)`);
  }
}

async function checkReadOnlyFallbackMutations(): Promise<void> {
  if (smokeSummary.mode !== FALLBACK_READ_ONLY_MODE) {
    console.log('SKIP read-only fallback mutation checks (backend mode)');
    return;
  }

  const jsonHeaders = { 'Content-Type': 'application/json' };

  {
    const result = await requireStatus(
      `${frontendBaseUrl}/api/crawler`,
      '/api/crawler POST',
      503,
      {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify({ action: 'run_now' }),
      }
    );
    const payload = parseJson('/api/crawler POST', result.bodyText);
    assertCondition(isRecord(payload), '/api/crawler POST payload must be object');
    assertCondition(payload.mode === FALLBACK_READ_ONLY_MODE, '/api/crawler POST mode mismatch');
    assertCondition(payload.read_only === true, '/api/crawler POST must be read_only');
    assertProxyHeaders(result, '/api/crawler POST', FALLBACK_READ_ONLY_MODE);
    smokeSummary.checks.push({
      label: '/api/crawler POST',
      endpoint: '/api/crawler',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/crawler POST (${result.elapsedMs}ms) read-only`);
  }

  {
    const result = await requireStatus(
      `${frontendBaseUrl}/api/crawler/sources`,
      '/api/crawler/sources POST',
      503,
      {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify({
          name: 'Smoke Source',
          url: 'https://example.com/feed',
          type: 'rss',
        }),
      }
    );
    const payload = parseJson('/api/crawler/sources POST', result.bodyText);
    assertCondition(
      isRecord(payload),
      '/api/crawler/sources POST payload must be object'
    );
    assertCondition(
      payload.mode === FALLBACK_READ_ONLY_MODE,
      '/api/crawler/sources POST mode mismatch'
    );
    assertCondition(
      payload.read_only === true,
      '/api/crawler/sources POST must be read_only'
    );
    assertProxyHeaders(result, '/api/crawler/sources POST', FALLBACK_READ_ONLY_MODE);
    smokeSummary.checks.push({
      label: '/api/crawler/sources POST',
      endpoint: '/api/crawler/sources',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/crawler/sources POST (${result.elapsedMs}ms) read-only`);
  }

  {
    const result = await requireStatus(
      `${frontendBaseUrl}/api/users/smoke-user/saved-articles/smoke-article`,
      '/api/users saved article POST',
      503,
      { method: 'POST' }
    );
    const payload = parseJson('/api/users saved article POST', result.bodyText);
    assertCondition(
      isRecord(payload),
      '/api/users saved article POST payload must be object'
    );
    assertCondition(
      payload.mode === FALLBACK_READ_ONLY_MODE,
      '/api/users saved article POST mode mismatch'
    );
    assertCondition(
      payload.read_only === true,
      '/api/users saved article POST must be read_only'
    );
    assertProxyHeaders(result, '/api/users saved article POST', FALLBACK_READ_ONLY_MODE);
    smokeSummary.checks.push({
      label: '/api/users saved article POST',
      endpoint: '/api/users/smoke-user/saved-articles/smoke-article',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/users saved article POST (${result.elapsedMs}ms) read-only`);
  }

  {
    const result = await requireStatus(
      `${frontendBaseUrl}/api/users/smoke-user/saved-articles/smoke-article`,
      '/api/users saved article DELETE',
      503,
      { method: 'DELETE' }
    );
    const payload = parseJson('/api/users saved article DELETE', result.bodyText);
    assertCondition(
      isRecord(payload),
      '/api/users saved article DELETE payload must be object'
    );
    assertCondition(
      payload.mode === FALLBACK_READ_ONLY_MODE,
      '/api/users saved article DELETE mode mismatch'
    );
    assertCondition(
      payload.read_only === true,
      '/api/users saved article DELETE must be read_only'
    );
    assertProxyHeaders(result, '/api/users saved article DELETE', FALLBACK_READ_ONLY_MODE);
    smokeSummary.checks.push({
      label: '/api/users saved article DELETE',
      endpoint: '/api/users/smoke-user/saved-articles/smoke-article',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/users saved article DELETE (${result.elapsedMs}ms) read-only`);
  }
}

async function checkProxyErrorContracts(): Promise<void> {
  const endpoint = `${frontendBaseUrl}/api/ingest/continuous/status`;
  const label = '/api/ingest/continuous/status';

  if (smokeSummary.mode === FALLBACK_READ_ONLY_MODE) {
    const result = await requireStatus(endpoint, label, 502);
    const payload = parseJson(label, result.bodyText);
    assertCondition(isRecord(payload), `${label} error payload must be object`);
    assertCondition(
      typeof payload.error_code === 'string',
      `${label} error payload must include error_code`
    );
    assertProxyHeaders(result, label, 'backend_error');
    smokeSummary.checks.push({
      label,
      endpoint: '/api/ingest/continuous/status',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS ${label} (${result.elapsedMs}ms) proxy error headers`);
    return;
  }

  const result = await requireHttp200(endpoint, label);
  assertProxyHeaders(result, label, 'backend');
  smokeSummary.checks.push({
    label,
    endpoint: '/api/ingest/continuous/status',
    elapsedMs: result.elapsedMs,
    status: result.status,
  });
  console.log(`PASS ${label} (${result.elapsedMs}ms)`);
}

async function writeSmokeMetrics(): Promise<void> {
  if (!smokeMetricsPath.trim()) {
    return;
  }
  const outputPath = path.resolve(smokeMetricsPath);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, JSON.stringify(smokeSummary, null, 2), 'utf8');
}

async function main(): Promise<void> {
  console.log(`Running frontend smoke checks against ${frontendBaseUrl}`);

  await checkHealth();
  await checkFrontendRoutes();
  await checkApiContracts();
  await checkReadOnlyFallbackMutations();
  await checkProxyErrorContracts();
  await writeSmokeMetrics();

  console.log('All smoke checks passed.');
}

main().catch((error) => {
  console.error('Smoke checks failed.');
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
