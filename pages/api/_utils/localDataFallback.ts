import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { defaultSources } from '@/lib/fallback/defaultSources';

export type LocalArticle = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  content?: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
  processed_at?: string;
  is_saved?: boolean;
};

export type LocalSource = {
  id: string;
  name: string;
  url: string;
  type: 'rss' | 'scrape' | 'api';
  category: string;
  crawlFrequency: number;
  isActive: boolean;
  useProxy: boolean;
  respectRobotsTxt: boolean;
  lastCrawled?: string | null;
  rssUrl?: string;
  apiEndpoint?: string;
  apiKey?: string;
  userAgent?: string;
  waitTime?: number;
  selector?: {
    title?: string;
    content?: string;
    date?: string;
    author?: string;
    image?: string;
  };
};

type ArticlesQuery = {
  source?: string;
  sentiment?: string;
  topic?: string;
  search?: string;
  published_since?: string;
  published_until?: string;
  sort_by?: string;
  sort_order?: string;
  limit: number;
  offset: number;
};

const DATA_DIR = path.join(process.cwd(), 'data');
const INGESTED_ARTICLES_FILE = path.join(DATA_DIR, 'ingested_articles.json');
const CRAWLER_ARTICLES_FILE = path.join(DATA_DIR, 'articles.json');
const SOURCES_FILE = path.join(DATA_DIR, 'sources.json');
const SAVED_ARTICLES_DIR = path.join(DATA_DIR, 'saved_articles');

const FALLBACK_OFF_VALUES = new Set(['0', 'false', 'no', 'off']);
const SOURCE_SLUG_REGEX = /[^a-z0-9]+/g;
const ENTITY_EXPLICIT_BLOCKLIST = new Set([
  'AfY8Hf',
  'Dftppe',
  'DpimGf',
  'EP1ykd',
  'FL1an',
  'FdrFJe',
  'Fwhl2e',
  'Document Format Files',
  'EIN',
  'Filer',
  'Incorp',
  'But',
  'Friday',
  'Thursday',
  'Wednesday',
  'Tuesday',
  'Monday',
  'State',
]);
const ENTITY_NOISE_MARKERS = ['wiz', 'dotssplash', 'setprefs', 'boq'];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const toTextList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((entry) => String(entry || '').trim())
      .filter((entry) => entry.length > 0);
  }
  if (value == null) {
    return [];
  }
  const text = String(value).trim();
  return text ? [text] : [];
};

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const slugify = (value: unknown): string =>
  String(value || '')
    .toLowerCase()
    .trim()
    .replace(SOURCE_SLUG_REGEX, '-')
    .replace(/^-+|-+$/g, '');

const isValidEntityName = (value: unknown): boolean => {
  const entity = String(value || '').trim();
  if (!entity) {
    return false;
  }
  if (ENTITY_EXPLICIT_BLOCKLIST.has(entity)) {
    return false;
  }

  const lowered = entity.toLowerCase();
  if (ENTITY_NOISE_MARKERS.some((marker) => lowered.includes(marker))) {
    return false;
  }

  if (/^[A-Za-z0-9]{5,12}$/.test(entity)) {
    const tail = entity.slice(1);
    const hasUpperAfterFirst = /[A-Z]/.test(tail);
    const hasLowerAfterFirst = /[a-z]/.test(tail);
    if (hasUpperAfterFirst && hasLowerAfterFirst) {
      return false;
    }
  }

  return true;
};

const ensureDir = (targetDir: string): void => {
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
};

const safeReadJson = <T>(filePath: string, fallback: T): T => {
  try {
    if (!fs.existsSync(filePath)) {
      return fallback;
    }
    const raw = fs.readFileSync(filePath, 'utf8');
    if (!raw.trim()) {
      return fallback;
    }
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

const safeWriteJson = (filePath: string, payload: unknown): void => {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2));
};

const fallbackArticleId = (raw: Record<string, unknown>): string => {
  const material = `${String(raw.title || '')}|${String(raw.url || '')}|${String(raw.published_at || '')}`;
  return crypto.createHash('md5').update(material).digest('hex');
};

const normalizeArticle = (raw: unknown): LocalArticle | null => {
  if (!isRecord(raw)) {
    return null;
  }

  const title = String(raw.title || '').trim();
  const url = String(raw.url || '').trim();
  if (!title || !url) {
    return null;
  }

  const source = String(raw.source || '').trim() || 'unknown';
  const publishedAt = String(raw.published_at || '').trim();
  const id = String(raw.id || '').trim() || fallbackArticleId(raw);

  return {
    id,
    title,
    url,
    source,
    published_at: publishedAt,
    content: typeof raw.content === 'string' ? raw.content : undefined,
    summarized_headline:
      typeof raw.summarized_headline === 'string' ? raw.summarized_headline : undefined,
    summary_bullets: toTextList(raw.summary_bullets),
    sentiment: typeof raw.sentiment === 'string' ? raw.sentiment : undefined,
    sentiment_score: toNumber(raw.sentiment_score),
    market_impact_score: toNumber(raw.market_impact_score),
    key_entities: toTextList(raw.key_entities),
    topics: toTextList(raw.topics),
    processed_at: typeof raw.processed_at === 'string' ? raw.processed_at : undefined,
  };
};

const articleSortTimestamp = (article: LocalArticle): number => {
  const parsed = Date.parse(article.published_at || article.processed_at || '');
  return Number.isFinite(parsed) ? parsed : 0;
};

const sentimentWeight = (article: LocalArticle): number => {
  if (typeof article.sentiment_score === 'number' && Number.isFinite(article.sentiment_score)) {
    return article.sentiment_score;
  }

  switch ((article.sentiment || '').toLowerCase()) {
    case 'positive':
      return 1;
    case 'negative':
      return -1;
    case 'neutral':
      return 0;
    default:
      return 0;
  }
};

const relevanceWeight = (article: LocalArticle, query: string): number => {
  if (!query) {
    return articleSortTimestamp(article);
  }

  const haystack = [
    article.title,
    article.summarized_headline || '',
    article.content || '',
    article.source,
    ...(article.topics || []),
    ...(article.key_entities || []),
  ]
    .join(' ')
    .toLowerCase();

  if (!haystack.includes(query)) {
    return 0;
  }

  const parts = query.split(/\s+/).filter(Boolean);
  const score = parts.reduce((acc, term) => {
    const matches = haystack.split(term).length - 1;
    return acc + matches;
  }, 0);

  return score * 10_000_000_000 + articleSortTimestamp(article);
};

const localArticleStoreFiles = (): string[] => [
  INGESTED_ARTICLES_FILE,
  CRAWLER_ARTICLES_FILE,
];

export const isLocalApiFallbackEnabled = (): boolean => {
  const raw = String(process.env.ENABLE_LOCAL_API_FALLBACK || 'true').toLowerCase().trim();
  return !FALLBACK_OFF_VALUES.has(raw);
};

export const loadLocalArticles = (): LocalArticle[] => {
  const foundFile = localArticleStoreFiles().find((candidate) => fs.existsSync(candidate));
  if (!foundFile) {
    return [];
  }

  const payload = safeReadJson<unknown[]>(foundFile, []);
  if (!Array.isArray(payload)) {
    return [];
  }

  const normalized = payload
    .map(normalizeArticle)
    .filter((article): article is LocalArticle => Boolean(article));

  normalized.sort((a, b) => articleSortTimestamp(b) - articleSortTimestamp(a));
  return normalized;
};

export const queryLocalArticles = (query: ArticlesQuery): {
  articles: LocalArticle[];
  total: number;
  limit: number;
  offset: number;
} => {
  const sourceFilter = slugify(query.source);
  const sentimentFilter = String(query.sentiment || '').toLowerCase().trim();
  const topicFilter = slugify(query.topic);
  const searchFilter = String(query.search || '').toLowerCase().trim();
  const publishedSince = query.published_since ? Date.parse(query.published_since) : Number.NaN;
  const publishedUntil = query.published_until ? Date.parse(query.published_until) : Number.NaN;
  const sortBy = String(query.sort_by || 'date').toLowerCase();
  const sortOrder = String(query.sort_order || 'desc').toLowerCase() === 'asc' ? 'asc' : 'desc';

  let filtered = loadLocalArticles();

  if (sourceFilter) {
    filtered = filtered.filter((article) => {
      const sourceSlug = slugify(article.source);
      return sourceSlug === sourceFilter || article.source.toLowerCase() === sourceFilter;
    });
  }

  if (sentimentFilter) {
    filtered = filtered.filter(
      (article) => String(article.sentiment || '').toLowerCase() === sentimentFilter
    );
  }

  if (topicFilter) {
    filtered = filtered.filter((article) =>
      (article.topics || []).some((topic) => slugify(topic) === topicFilter)
    );
  }

  if (searchFilter) {
    filtered = filtered.filter((article) => {
      const searchable = [
        article.title,
        article.summarized_headline || '',
        article.content || '',
        article.source,
        ...(article.topics || []),
        ...(article.key_entities || []),
      ]
        .join(' ')
        .toLowerCase();
      return searchable.includes(searchFilter);
    });
  }

  if (Number.isFinite(publishedSince)) {
    filtered = filtered.filter((article) => articleSortTimestamp(article) >= publishedSince);
  }

  if (Number.isFinite(publishedUntil)) {
    filtered = filtered.filter((article) => articleSortTimestamp(article) <= publishedUntil);
  }

  filtered.sort((a, b) => {
    let left: number;
    let right: number;

    if (sortBy === 'sentiment') {
      left = sentimentWeight(a);
      right = sentimentWeight(b);
    } else if (sortBy === 'relevance') {
      left = relevanceWeight(a, searchFilter);
      right = relevanceWeight(b, searchFilter);
    } else {
      left = articleSortTimestamp(a);
      right = articleSortTimestamp(b);
    }

    return sortOrder === 'asc' ? left - right : right - left;
  });

  const total = filtered.length;
  const offset = Math.max(0, Number.isFinite(query.offset) ? query.offset : 0);
  const limit = Math.max(1, Number.isFinite(query.limit) ? query.limit : 10);

  return {
    total,
    limit,
    offset,
    articles: filtered.slice(offset, offset + limit),
  };
};

export const getLocalArticleById = (articleId: string): LocalArticle | null => {
  const normalizedId = String(articleId || '').trim();
  if (!normalizedId) {
    return null;
  }

  return loadLocalArticles().find((article) => article.id === normalizedId) || null;
};

const normalizeSource = (raw: unknown): LocalSource | null => {
  if (!isRecord(raw)) {
    return null;
  }

  const id = String(raw.id || '').trim();
  const name = String(raw.name || '').trim();
  const url = String(raw.url || '').trim();
  if (!id || !name || !url) {
    return null;
  }

  const typeCandidate = String(raw.type || 'rss').toLowerCase();
  const type: LocalSource['type'] =
    typeCandidate === 'api' || typeCandidate === 'scrape' ? typeCandidate : 'rss';

  return {
    id,
    name,
    url,
    type,
    category: String(raw.category || 'finance'),
    crawlFrequency: Math.max(5, Number(toNumber(raw.crawlFrequency) || 30)),
    isActive: raw.isActive !== false,
    useProxy: raw.useProxy === true,
    respectRobotsTxt: raw.respectRobotsTxt !== false,
    lastCrawled: raw.lastCrawled ? String(raw.lastCrawled) : null,
    rssUrl: typeof raw.rssUrl === 'string' ? raw.rssUrl : undefined,
    apiEndpoint: typeof raw.apiEndpoint === 'string' ? raw.apiEndpoint : undefined,
    apiKey: typeof raw.apiKey === 'string' ? raw.apiKey : undefined,
    userAgent: typeof raw.userAgent === 'string' ? raw.userAgent : undefined,
    waitTime: toNumber(raw.waitTime),
    selector: isRecord(raw.selector)
      ? {
          title: typeof raw.selector.title === 'string' ? raw.selector.title : undefined,
          content: typeof raw.selector.content === 'string' ? raw.selector.content : undefined,
          date: typeof raw.selector.date === 'string' ? raw.selector.date : undefined,
          author: typeof raw.selector.author === 'string' ? raw.selector.author : undefined,
          image: typeof raw.selector.image === 'string' ? raw.selector.image : undefined,
        }
      : undefined,
  };
};

const defaultLocalSources = (): LocalSource[] =>
  defaultSources.map((source) => ({
    ...source,
    lastCrawled: source.lastCrawled ? new Date(source.lastCrawled).toISOString() : null,
  }));

export const loadLocalSources = (): LocalSource[] => {
  ensureDir(DATA_DIR);
  if (!fs.existsSync(SOURCES_FILE)) {
    safeWriteJson(SOURCES_FILE, defaultLocalSources());
  }

  const payload = safeReadJson<unknown[]>(SOURCES_FILE, []);
  const normalized = payload
    .map(normalizeSource)
    .filter((source): source is LocalSource => Boolean(source));

  if (normalized.length > 0) {
    return normalized;
  }

  const defaults = defaultLocalSources();
  safeWriteJson(SOURCES_FILE, defaults);
  return defaults;
};

export const saveLocalSources = (sources: LocalSource[]): void => {
  safeWriteJson(SOURCES_FILE, sources);
};

export const upsertLocalSource = (
  payload: Omit<Partial<LocalSource>, 'type'> & {
    name: string;
    url: string;
    type: string;
  }
): LocalSource => {
  const existing = loadLocalSources();
  const nextId = String(payload.id || '').trim() || `${slugify(payload.name)}-${Date.now()}`;
  const normalizedType = String(payload.type || 'rss').toLowerCase();

  const candidate: LocalSource = {
    id: nextId,
    name: String(payload.name || '').trim(),
    url: String(payload.url || '').trim(),
    type: normalizedType === 'api' || normalizedType === 'scrape' ? normalizedType : 'rss',
    category: String(payload.category || 'finance'),
    crawlFrequency: Math.max(5, Number(payload.crawlFrequency || 30)),
    isActive: payload.isActive !== false,
    useProxy: payload.useProxy === true,
    respectRobotsTxt: payload.respectRobotsTxt !== false,
    lastCrawled: payload.lastCrawled || null,
    rssUrl: payload.rssUrl,
    apiEndpoint: payload.apiEndpoint,
    apiKey: payload.apiKey,
    userAgent: payload.userAgent,
    waitTime: payload.waitTime,
    selector: payload.selector,
  };

  const index = existing.findIndex((source) => source.id === nextId);
  if (index >= 0) {
    existing[index] = candidate;
  } else {
    existing.push(candidate);
  }

  saveLocalSources(existing);
  return candidate;
};

export const deleteLocalSource = (sourceId: string): boolean => {
  const existing = loadLocalSources();
  const next = existing.filter((source) => source.id !== sourceId);
  const deleted = next.length < existing.length;
  if (deleted) {
    saveLocalSources(next);
  }
  return deleted;
};

export const getLocalSourceOptions = (): Array<{ id: string; name: string }> => {
  const articleCounts = new Map<string, number>();
  loadLocalArticles().forEach((article) => {
    articleCounts.set(article.source, (articleCounts.get(article.source) || 0) + 1);
  });

  if (articleCounts.size === 0) {
    return loadLocalSources().map((source) => ({ id: source.id, name: source.name }));
  }

  return Array.from(articleCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([name]) => ({ id: slugify(name), name }));
};

export const getLocalTopicOptions = (): Array<{ id: string; name: string }> => {
  const topicCounts = new Map<string, number>();

  loadLocalArticles().forEach((article) => {
    (article.topics || []).forEach((topic) => {
      topicCounts.set(topic, (topicCounts.get(topic) || 0) + 1);
    });
  });

  return Array.from(topicCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([name]) => ({ id: slugify(name), name }));
};

const pickTop = (entries: Map<string, number>, limit: number): Array<{ name: string; count: number }> =>
  Array.from(entries.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));

export const getLocalAnalytics = (): {
  sentiment_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  top_entities: Array<{ name: string; count: number }>;
  top_topics: Array<{ name: string; count: number }>;
  processing_stats: {
    avg_processing_time: number;
    articles_processed: number;
    last_update: number;
  };
} => {
  const articles = loadLocalArticles();
  const sentiment = new Map<string, number>();
  const sources = new Map<string, number>();
  const entities = new Map<string, number>();
  const topics = new Map<string, number>();

  let lastUpdate = 0;

  articles.forEach((article) => {
    const sentimentKey = String(article.sentiment || 'neutral').toLowerCase();
    sentiment.set(sentimentKey, (sentiment.get(sentimentKey) || 0) + 1);

    sources.set(article.source, (sources.get(article.source) || 0) + 1);

    (article.key_entities || []).forEach((entity) => {
      if (!isValidEntityName(entity)) {
        return;
      }
      entities.set(entity, (entities.get(entity) || 0) + 1);
    });

    (article.topics || []).forEach((topic) => {
      topics.set(topic, (topics.get(topic) || 0) + 1);
    });

    const timestamp = Date.parse(article.processed_at || article.published_at || '');
    if (Number.isFinite(timestamp) && timestamp > lastUpdate) {
      lastUpdate = timestamp;
    }
  });

  const sentimentDistribution: Record<string, number> = {
    positive: sentiment.get('positive') || 0,
    neutral: sentiment.get('neutral') || 0,
    negative: sentiment.get('negative') || 0,
  };

  const sourceDistribution: Record<string, number> = {};
  Array.from(sources.entries()).forEach(([name, count]) => {
    sourceDistribution[name] = count;
  });

  return {
    sentiment_distribution: sentimentDistribution,
    source_distribution: sourceDistribution,
    top_entities: pickTop(entities, 12),
    top_topics: pickTop(topics, 12),
    processing_stats: {
      avg_processing_time: 0,
      articles_processed: articles.length,
      last_update: lastUpdate || Date.now(),
    },
  };
};

const sourceIsDue = (source: LocalSource): boolean => {
  if (!source.lastCrawled) {
    return true;
  }
  const last = Date.parse(source.lastCrawled);
  if (!Number.isFinite(last)) {
    return true;
  }
  const elapsedMinutes = (Date.now() - last) / 60000;
  return elapsedMinutes >= Math.max(1, source.crawlFrequency);
};

export const getLocalCrawlerStats = (): {
  totalSources: number;
  activeSources: number;
  sourcesDueCrawling: number;
  scheduler: { enabled: boolean; intervalSeconds: number };
} => {
  const sources = loadLocalSources();
  const activeSources = sources.filter((source) => source.isActive);
  return {
    totalSources: sources.length,
    activeSources: activeSources.length,
    sourcesDueCrawling: activeSources.filter(sourceIsDue).length,
    scheduler: {
      enabled: false,
      intervalSeconds: 0,
    },
  };
};

const savedArticlesPath = (userId: string): string =>
  path.join(SAVED_ARTICLES_DIR, `${slugify(userId) || 'default'}.json`);

const loadSavedIds = (userId: string): Set<string> => {
  ensureDir(SAVED_ARTICLES_DIR);
  const payload = safeReadJson<unknown[]>(savedArticlesPath(userId), []);
  const ids = Array.isArray(payload)
    ? payload.map((entry) => String(entry || '').trim()).filter(Boolean)
    : [];
  return new Set(ids);
};

const saveSavedIds = (userId: string, ids: Set<string>): void => {
  safeWriteJson(savedArticlesPath(userId), Array.from(ids));
};

export const isArticleSavedLocally = (userId: string, articleId: string): boolean =>
  loadSavedIds(userId).has(articleId);

export const markArticleSavedLocally = (
  userId: string,
  articleId: string,
  shouldSave: boolean
): { user_id: string; article_id: string; is_saved: boolean } => {
  const ids = loadSavedIds(userId);
  if (shouldSave) {
    ids.add(articleId);
  } else {
    ids.delete(articleId);
  }
  saveSavedIds(userId, ids);
  return {
    user_id: userId,
    article_id: articleId,
    is_saved: shouldSave,
  };
};

export const localDataDiagnostics = (): {
  fallback_enabled: boolean;
  mode: 'fallback_read_only';
  local_articles_file: string | null;
  local_articles_count: number;
  local_sources_count: number;
  latest_article_at: string | null;
  freshness_lag_seconds: number | null;
} => {
  const articles = loadLocalArticles();
  const latest = articles[0];
  const foundFile = localArticleStoreFiles().find((candidate) => fs.existsSync(candidate)) || null;
  const latestArticleAt = latest?.published_at || latest?.processed_at || null;
  const freshnessLagSeconds = latestArticleAt
    ? Math.max(0, Math.floor((Date.now() - Date.parse(latestArticleAt)) / 1000))
    : null;

  return {
    fallback_enabled: isLocalApiFallbackEnabled(),
    mode: 'fallback_read_only',
    local_articles_file: foundFile,
    local_articles_count: articles.length,
    local_sources_count: loadLocalSources().length,
    latest_article_at: latestArticleAt,
    freshness_lag_seconds: Number.isFinite(freshnessLagSeconds) ? freshnessLagSeconds : null,
  };
};
