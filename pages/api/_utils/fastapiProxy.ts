import { NextApiRequest, NextApiResponse } from 'next';

type QueryParams = Record<string, unknown>;

const rawFastApiBaseUrl =
  process.env.FASTAPI_URL ||
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://127.0.0.1:8000';

const normalizeFastApiBaseUrl = (value: string): string => {
  if (value.startsWith('http://') || value.startsWith('https://')) {
    return value;
  }
  // NEXT_PUBLIC_API_URL is commonly '/api' for browser calls; API routes need an absolute backend URL.
  return 'http://127.0.0.1:8000';
};

export const FASTAPI_BASE_URL = normalizeFastApiBaseUrl(rawFastApiBaseUrl);
const FASTAPI_REQUEST_TIMEOUT_MS = Number(process.env.FASTAPI_REQUEST_TIMEOUT_MS || 8000);
const FASTAPI_GET_RETRIES = Math.max(
  0,
  Number.parseInt(process.env.FASTAPI_GET_RETRIES || '1', 10) || 0
);
const FASTAPI_ADMIN_API_KEY =
  process.env.FASTAPI_ADMIN_API_KEY || process.env.ADMIN_API_KEY || '';

export class FastApiProxyError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = 'FastApiProxyError';
    this.status = status;
    this.payload = payload;
  }
}

function appendQuery(url: URL, query?: QueryParams): void {
  if (!query) {
    return;
  }
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== undefined && entry !== null && entry !== '') {
          url.searchParams.append(key, String(entry));
        }
      });
      return;
    }
    url.searchParams.set(key, String(value));
  });
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type')?.toLowerCase() || '';
  if (!contentType.includes('application/json')) {
    const text = await response.text();
    return text ? { detail: text } : null;
  }
  return response.json();
}

function errorDetail(payload: unknown): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    return String((payload as { detail?: unknown }).detail || '');
  }
  return '';
}

export function isBackendUnavailableError(error: unknown): error is FastApiProxyError {
  if (!(error instanceof FastApiProxyError)) {
    return false;
  }

  if (error.status !== 502) {
    return false;
  }

  const detail = `${error.message} ${errorDetail(error.payload)}`.toLowerCase();
  return (
    detail.includes('unable to connect') ||
    detail.includes('fetch failed') ||
    detail.includes('connection refused') ||
    detail.includes('timed out') ||
    detail.includes('econnrefused') ||
    detail.includes('socket hang up') ||
    detail.includes('abort')
  );
}

async function fetchWithRetries(
  url: string,
  init: RequestInit,
  retries: number
): Promise<Response> {
  let attempt = 0;
  let lastError: unknown;

  while (attempt <= retries) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FASTAPI_REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        ...init,
        signal: controller.signal,
      });
      clearTimeout(timer);
      return response;
    } catch (error) {
      clearTimeout(timer);
      lastError = error;
      if (attempt >= retries) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, (attempt + 1) * 120));
      attempt += 1;
    }
  }

  throw lastError instanceof Error ? lastError : new Error('fetch failed');
}

export async function fastApiRequest<T = unknown>({
  path,
  method = 'GET',
  query,
  body,
  req,
}: {
  path: string;
  method?: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH';
  query?: QueryParams;
  body?: unknown;
  req?: NextApiRequest;
}): Promise<T> {
  const url = new URL(path, FASTAPI_BASE_URL);
  appendQuery(url, query);

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (req?.headers.authorization) {
    headers.Authorization = req.headers.authorization;
  }
  const adminApiKeyHeader =
    req?.headers['x-admin-key'] ||
    req?.headers['x-admin-api-key'] ||
    req?.headers['x-api-key'];
  if (adminApiKeyHeader) {
    headers['X-Admin-Key'] = String(adminApiKeyHeader);
    headers['X-Admin-Api-Key'] = String(adminApiKeyHeader);
  } else if (FASTAPI_ADMIN_API_KEY) {
    headers['X-Admin-Key'] = FASTAPI_ADMIN_API_KEY;
    headers['X-Admin-Api-Key'] = FASTAPI_ADMIN_API_KEY;
  }
  if (req?.headers['x-admin-role']) {
    headers['X-Admin-Role'] = String(req.headers['x-admin-role']);
  }
  if (req?.headers['x-admin-user']) {
    headers['X-Admin-User'] = String(req.headers['x-admin-user']);
  }
  if (req?.headers['x-admin-actor']) {
    headers['X-Admin-Actor'] = String(req.headers['x-admin-actor']);
  }
  if (req?.headers.cookie) {
    headers.Cookie = String(req.headers.cookie);
  }
  if (req?.headers['x-request-id']) {
    headers['X-Request-Id'] = String(req.headers['x-request-id']);
  }

  let response: Response;
  try {
    response = await fetchWithRetries(
      url.toString(),
      {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      },
      method === 'GET' ? FASTAPI_GET_RETRIES : 0
    );
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'fetch failed';
    throw new FastApiProxyError(
      `Unable to connect to backend at ${url.toString()}`,
      502,
      { detail }
    );
  }

  const payload = await parseResponseBody(response);
  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload && 'detail' in payload
        ? String((payload as { detail?: unknown }).detail)
        : `FastAPI returned ${response.status}`;
    throw new FastApiProxyError(detail, response.status, payload);
  }
  return payload as T;
}

export async function checkBackendHealth(): Promise<{
  reachable: boolean;
  status: number | null;
  detail: string | null;
  checked_at: string;
  backend_url: string;
}> {
  const apiBase = new URL('/api/', FASTAPI_BASE_URL);
  const healthUrl = new URL('/health', apiBase).toString();
  try {
    const response = await fetchWithRetries(
      healthUrl,
      {
        method: 'GET',
        headers: { Accept: 'application/json' },
      },
      0
    );

    const detail = response.ok
      ? null
      : `Health endpoint returned ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
    return {
      reachable: response.ok,
      status: response.status,
      detail,
      checked_at: new Date().toISOString(),
      backend_url: FASTAPI_BASE_URL,
    };
  } catch (error) {
    return {
      reachable: false,
      status: null,
      detail: error instanceof Error ? error.message : 'fetch failed',
      checked_at: new Date().toISOString(),
      backend_url: FASTAPI_BASE_URL,
    };
  }
}

export function sendProxyError(
  res: NextApiResponse,
  error: unknown,
  fallbackMessage = 'FastAPI proxy failure'
): void {
  if (error instanceof FastApiProxyError) {
    const payloadObject =
      error.payload && typeof error.payload === 'object'
        ? (error.payload as Record<string, unknown>)
        : {};
    const detail =
      typeof payloadObject.detail === 'string' && payloadObject.detail.trim()
        ? payloadObject.detail
        : error.message || fallbackMessage;
    res.status(error.status || 502).json({
      ...payloadObject,
      error: typeof payloadObject.error === 'string' ? payloadObject.error : fallbackMessage,
      detail,
      error_code: isBackendUnavailableError(error) ? 'backend_unreachable' : 'upstream_error',
      retryable: error.status >= 500 || error.status === 429,
      backend_url: FASTAPI_BASE_URL,
    });
    return;
  }

  const detail = error instanceof Error ? error.message : fallbackMessage;
  res.status(502).json({
    error: fallbackMessage,
    detail,
    error_code: 'proxy_error',
    retryable: true,
    backend_url: FASTAPI_BASE_URL,
  });
}

export function enforceMethod(
  req: NextApiRequest,
  res: NextApiResponse,
  allowed: Array<'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH'>
): boolean {
  if (!req.method || !allowed.includes(req.method as typeof allowed[number])) {
    res.setHeader('Allow', allowed);
    res.status(405).end(`Method ${req.method} Not Allowed`);
    return false;
  }
  return true;
}
