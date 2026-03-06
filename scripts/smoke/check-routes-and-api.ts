import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const frontendBaseUrl = process.env.SMOKE_FRONTEND_BASE_URL ?? 'http://127.0.0.1:3000';
const requestTimeoutMs = Number(process.env.SMOKE_TIMEOUT_MS ?? '15000');
const maxLatencyMs = Number(process.env.SMOKE_MAX_LATENCY_MS ?? '8000');
const smokeMetricsPath = process.env.SMOKE_METRICS_PATH ?? '';

type SmokeMetric = {
  label: string;
  endpoint: string;
  elapsedMs: number;
  status: number;
};

type SmokeSummary = {
  checkedAt: string;
  baseUrl: string;
  mode: 'backend' | 'fallback' | 'unknown';
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

async function fetchTimed(url: string, label: string): Promise<TimedResponse> {
  const startedAt = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { signal: controller.signal });
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

async function requireHttp200(url: string, label: string): Promise<TimedResponse> {
  const result = await fetchTimed(url, label);
  assertCondition(
    result.status === 200,
    `${label} returned HTTP ${result.status}: ${result.bodyText.slice(0, 240)}`
  );
  return result;
}

async function checkHealth(): Promise<void> {
  const url = `${frontendBaseUrl}/api/health`;
  const result = await requireHttp200(url, 'health endpoint');
  const payload = parseJson('health endpoint', result.bodyText);

  assertCondition(isRecord(payload), 'Health payload must be an object');
  assertCondition(payload.status === 'ok', 'Health status must be "ok"');
  assertCondition(
    payload.mode === 'backend' || payload.mode === 'fallback',
    'Health mode must be "backend" or "fallback"'
  );
  smokeSummary.mode = payload.mode as 'backend' | 'fallback';
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
    const result = await requireHttp200(`${frontendBaseUrl}/api/sources`, '/api/sources');
    const payload = parseJson('/api/sources', result.bodyText);
    assertCondition(Array.isArray(payload), '/api/sources payload must be array');
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
    smokeSummary.checks.push({
      label: '/api/crawler/sources',
      endpoint: '/api/crawler/sources',
      elapsedMs: result.elapsedMs,
      status: result.status,
    });
    console.log(`PASS /api/crawler/sources (${result.elapsedMs}ms)`);
  }
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
  await writeSmokeMetrics();

  console.log('All smoke checks passed.');
}

main().catch((error) => {
  console.error('Smoke checks failed.');
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
