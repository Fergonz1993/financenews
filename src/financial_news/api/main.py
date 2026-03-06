#!/usr/bin/env python3
# mypy: disable-error-code=no-untyped-def
"""Financial News API"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from financial_news.api.saved_articles import (
    get_saved_articles,
    is_article_saved,
    save_article,
    unsave_article,
)
from financial_news.api.websockets import (
    generate_demo_alerts,
)
from financial_news.api.websockets import (
    manager as notification_manager,
)
from financial_news.core.sentiment import analyze_article_sentiment
from financial_news.core.summarizer_config import setup_logging
from financial_news.services.continuous_runner import (
    get_runner as get_continuous_runner,
)
from financial_news.services.feed_ranking import rank_articles, suppress_near_duplicates
from financial_news.services.news_ingest import NewsIngestor
from financial_news.storage import get_session_factory, initialize_schema
from financial_news.storage.repositories import (
    SourceConfig,
    SourceRepository,
    UserAlertPreferencesRepository,
    UserSettingsRepository,
)

logger = setup_logging()

app = FastAPI(
    title="Financial News API",
    description="API for Financial News Analysis Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a correlation request ID to every response."""
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or str(uuid.uuid4())
    )
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


class ArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str
    summarized_headline: str | None = None
    summary_bullets: list[str] = []
    sentiment: str | None = None
    sentiment_score: float | None = None
    market_impact_score: float | None = None
    key_entities: list[str] = []
    topics: list[str] = []


class AnalyticsResponse(BaseModel):
    sentiment_distribution: dict[str, int]
    source_distribution: dict[str, int]
    top_entities: list[dict[str, int]]
    top_topics: list[dict[str, int]]
    processing_stats: dict[str, float]


class SourceUpsertRequest(BaseModel):
    id: str | None = None
    name: str
    url: str
    source_type: str = "rss"
    source_category: str | None = None
    connector_type: str | None = None
    crawl_interval_minutes: int = 30
    rate_limit_per_minute: int = 60
    enabled: bool = True
    terms_url: str | None = None
    legal_basis: str | None = None
    provider_domain: str | None = None
    rate_profile: str | None = None
    requires_api_key: bool = False
    requires_user_agent: bool = False
    user_agent: str | None = None
    retry_policy: dict[str, Any] | None = None
    parser_contract: dict[str, Any] | None = None


class SourceValidationRequest(BaseModel):
    source_url: str
    source_type: str = "rss"


class ConnectorToggleRequest(BaseModel):
    enabled: bool | None = None
    reset_override: bool = False


class DefaultFiltersPayload(BaseModel):
    sources: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    sentiment: str | None = None


class EmailAlertsPayload(BaseModel):
    enabled: bool = False
    frequency: str = Field(default="daily")
    keywords: list[str] = Field(default_factory=list)


class VisualizationPayload(BaseModel):
    chartType: str = "bar"
    colorScheme: str = "default"


class UserSettingsPayload(BaseModel):
    darkMode: bool = True
    autoRefresh: bool = False
    refreshInterval: int = Field(default=5, ge=1, le=3600)
    defaultFilters: DefaultFiltersPayload = Field(default_factory=DefaultFiltersPayload)
    emailAlerts: EmailAlertsPayload = Field(default_factory=EmailAlertsPayload)
    visualization: VisualizationPayload = Field(default_factory=VisualizationPayload)


class UserAlertRulePayload(BaseModel):
    id: str | None = None
    source: str | None = None
    sentiment: str | None = None
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True


class UserAlertsPayload(BaseModel):
    enabled: bool = False
    deliveryMode: str = "digest"
    rules: list[UserAlertRulePayload] = Field(default_factory=list)


class IngestTriggerRequest(BaseModel):
    source_filters: list[str] | str | None = None
    source_urls: list[str] | str | None = None
    source_ids: list[int] | str | None = None
    idempotency_key: str | None = None
    reason: str | None = None


session_factory = get_session_factory()
ingester = NewsIngestor(session_factory=session_factory)
source_repo = SourceRepository(session_factory=session_factory)
user_settings_repo = UserSettingsRepository(session_factory=session_factory)
user_alerts_repo = UserAlertPreferencesRepository(session_factory=session_factory)
continuous_runner = get_continuous_runner(session_factory=session_factory)
LAST_INGEST_RUN = None
AUTO_INGEST_INTERVAL_SECONDS = int(
    os.getenv("NEWS_INGEST_INTERVAL_SECONDS", "0") or "0"
)
_BACKGROUND_TASKS: list[asyncio.Task[Any]] = []
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
ADMIN_ALLOWED_ROLES = {
    role.strip().lower()
    for role in os.getenv("ADMIN_ALLOWED_ROLES", "admin,ops").split(",")
    if role.strip()
}
ADMIN_RATE_LIMIT_PER_MINUTE = int(
    os.getenv("ADMIN_RATE_LIMIT_PER_MINUTE", "30") or "30"
)
_ADMIN_REQUEST_WINDOW_SECONDS = 60
_ADMIN_REQUEST_HISTORY: dict[str, list[float]] = {}
_INGEST_IDEMPOTENCY_TTL_SECONDS = int(
    os.getenv("INGEST_IDEMPOTENCY_TTL_SECONDS", "900") or "900"
)
_INGEST_IDEMPOTENCY_CACHE: dict[str, tuple[str, float]] = {}

_FILTER_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ENTITY_NOISE_MARKERS = ("wiz", "dotssplash", "setprefs", "boq")
_ENTITY_EXPLICIT_BLOCKLIST = {
    "AfY8Hf",
    "Dftppe",
    "DpimGf",
    "EP1ykd",
    "FL1an",
    "FdrFJe",
    "Fwhl2e",
    "Document Format Files",
    "EIN",
    "Filer",
    "Incorp",
    "But",
    "Friday",
    "Thursday",
    "Wednesday",
    "Tuesday",
    "Monday",
    "State",
}


def _slugify_filter_value(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    return _FILTER_SLUG_RE.sub("-", normalized).strip("-")


def _is_valid_entity_name(value: Any) -> bool:
    entity = str(value or "").strip()
    if not entity:
        return False
    if entity in _ENTITY_EXPLICIT_BLOCKLIST:
        return False

    lowered = entity.lower()
    if any(marker in lowered for marker in _ENTITY_NOISE_MARKERS):
        return False

    if " " not in entity and entity.isalnum() and 5 <= len(entity) <= 12:
        has_upper_after_first = any(char.isupper() for char in entity[1:])
        has_lower_after_first = any(char.islower() for char in entity[1:])
        if has_upper_after_first and has_lower_after_first:
            return False

    return True


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed


FEED_RANKING_V2_ENABLED = (
    os.getenv("FEED_RANKING_V2_ENABLED", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
FEED_RANKING_V2_CANDIDATE_MULTIPLIER = max(
    2,
    _env_int("FEED_RANKING_V2_CANDIDATE_MULTIPLIER", 5),
)
FEED_RANKING_V2_MAX_CANDIDATES = max(
    50,
    _env_int("FEED_RANKING_V2_MAX_CANDIDATES", 500),
)
FEED_RANKING_V2_DEDUP_ENABLED = (
    os.getenv("FEED_RANKING_V2_DEDUP_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


def _request_id_from_request(request: Request | None) -> str:
    if request is None:
        return str(uuid.uuid4())
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _request_actor_from_headers(request: Request, *, trusted: bool = True) -> str:
    actor = request.headers.get("x-admin-user") or request.headers.get("x-admin-actor")
    if actor:
        return actor.strip()
    if not trusted:
        return "anonymous"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def _enforce_admin_rate_limit(request: Request) -> None:
    if ADMIN_RATE_LIMIT_PER_MINUTE <= 0:
        return

    now = time.monotonic()
    actor = _request_actor_from_headers(request, trusted=bool(ADMIN_API_KEY))
    window_start = now - _ADMIN_REQUEST_WINDOW_SECONDS
    history = _ADMIN_REQUEST_HISTORY.get(actor, [])
    recent = [timestamp for timestamp in history if timestamp >= window_start]
    if len(recent) >= ADMIN_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Admin rate limit exceeded. Retry in one minute.",
        )
    recent.append(now)
    _ADMIN_REQUEST_HISTORY[actor] = recent


def _require_admin_access(request: Request) -> str:
    """Validate admin auth when ADMIN_API_KEY is configured."""
    _enforce_admin_rate_limit(request)

    if not ADMIN_API_KEY:
        return _request_actor_from_headers(request, trusted=False)

    supplied_key = (
        request.headers.get("x-admin-key")
        or request.headers.get("x-admin-api-key")
        or request.headers.get("x-api-key")
        or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    )
    if not supplied_key:
        raise HTTPException(status_code=401, detail="Missing admin credentials")
    if not secrets.compare_digest(supplied_key, ADMIN_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin credentials")

    role = request.headers.get("x-admin-role", "admin").strip().lower()
    if ADMIN_ALLOWED_ROLES and role not in ADMIN_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient admin role")

    return request.headers.get("x-admin-user", role or "admin")


def require_admin_access(*roles: str):
    required_roles = {role.strip().lower() for role in roles if role and role.strip()}

    def _dependency(request: Request) -> str:
        actor = _require_admin_access(request)
        if not ADMIN_API_KEY or not required_roles:
            return actor
        role = request.headers.get("x-admin-role", "admin").strip().lower()
        if role not in required_roles:
            raise HTTPException(status_code=403, detail="Role not permitted for this endpoint")
        return actor

    return _dependency


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=UTC)
    if isinstance(value, datetime):
        return value
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime(1970, 1, 1, tzinfo=UTC)


def _parse_optional_datetime_param(
    value: str | None,
    *,
    param_name: str,
) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {param_name} value. Use ISO-8601 format, "
                "(for example 2026-02-20T00:00:00Z)."
            ),
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_published_since(value: str | None) -> datetime | None:
    return _parse_optional_datetime_param(value, param_name="published_since")


def _parse_published_until(value: str | None) -> datetime | None:
    return _parse_optional_datetime_param(value, param_name="published_until")


def _normalize_search_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value)
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _search_matches_article(article: dict[str, Any], search: str | None) -> bool:
    if not search:
        return True
    search_query = _normalize_search_text(search)
    compact = " ".join(
        [
            _normalize_search_text(article.get("title", "")),
            _normalize_search_text(article.get("content", "")),
            _normalize_search_text(article.get("summarized_headline", "")),
            _normalize_search_text(article.get("source", "")),
            _normalize_search_text(article.get("topics", [])),
            _normalize_search_text(article.get("key_entities", [])),
        ]
    )
    return search_query in compact


def _normalize_article_payload(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": article.get("id", ""),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "source": article.get("source", "Unknown"),
        "published_at": article.get("published_at", ""),
        "summarized_headline": article.get("summarized_headline"),
        "summary_bullets": _coerce_list(article.get("summary_bullets")),
        "sentiment": article.get("sentiment"),
        "sentiment_score": _coerce_float(article.get("sentiment_score")),
        "market_impact_score": _coerce_float(article.get("market_impact_score")),
        "key_entities": _coerce_list(article.get("key_entities")),
        "topics": _coerce_list(article.get("topics")),
    }


def _slug_like(source: str | None, candidate: str) -> bool:
    return _slugify_filter_value(source) == _slugify_filter_value(candidate)


def _serialize_source(source: Any) -> dict[str, Any]:
    return {
        "id": source.source_key,
        "source_id": source.id,
        "source_key": source.source_key,
        "name": source.name,
        "url": source.url,
        "source_type": source.source_type,
        "source_category": source.source_category,
        "connector_type": source.connector_type,
        "terms_url": source.terms_url,
        "legal_basis": source.legal_basis,
        "provider_domain": source.provider_domain,
        "rate_profile": source.rate_profile,
        "requires_api_key": source.requires_api_key,
        "requires_user_agent": source.requires_user_agent,
        "user_agent": source.user_agent,
        "enabled": source.enabled,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "rate_limit_per_minute": source.rate_limit_per_minute,
    }


def _source_key_from_request(payload: SourceUpsertRequest) -> str:
    candidate = payload.id or payload.name
    slug = _slugify_filter_value(candidate)
    if slug:
        return slug
    return f"source-{uuid.uuid4().hex[:8]}"


def _validate_source_url_or_raise(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="source_url must be an absolute http(s) URL",
        )


def _resolve_user_id(request: Request, explicit_user_id: str | None = None) -> str:
    if explicit_user_id and explicit_user_id.strip():
        return explicit_user_id.strip()
    header_user_id = request.headers.get("x-user-id")
    if header_user_id and header_user_id.strip():
        return header_user_id.strip()
    query_user_id = request.query_params.get("user_id")
    if query_user_id and query_user_id.strip():
        return query_user_id.strip()
    return "anonymous"


def _default_user_settings() -> dict[str, Any]:
    return {
        "darkMode": True,
        "autoRefresh": False,
        "refreshInterval": 5,
        "defaultFilters": {
            "sources": [],
            "topics": [],
            "sentiment": None,
        },
        "emailAlerts": {
            "enabled": False,
            "frequency": "daily",
            "keywords": [],
        },
        "visualization": {
            "chartType": "bar",
            "colorScheme": "default",
        },
    }


def _default_user_alerts() -> dict[str, Any]:
    return {
        "enabled": False,
        "deliveryMode": "digest",
        "rules": [],
    }


def _normalize_user_settings(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_payload = payload or _default_user_settings()
    try:
        model = UserSettingsPayload.model_validate(normalized_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid user settings payload: {exc.errors()}",
        ) from exc
    return model.model_dump()


def _normalize_user_alerts(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = payload or _default_user_alerts()
    try:
        model = UserAlertsPayload.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid user alerts payload: {exc.errors()}",
        ) from exc
    data = model.model_dump()
    for rule in data.get("rules", []):
        if not rule.get("id"):
            rule["id"] = uuid.uuid4().hex[:12]
    return data


def _normalize_filter_list(values: list[str] | str | None) -> list[str] | None:
    if values is None:
        return None
    if isinstance(values, str):
        normalized = [value.strip() for value in values.split(",") if value.strip()]
        return normalized or None
    normalized = [str(value).strip() for value in values if str(value).strip()]
    return normalized or None


def _parse_csv_filters(value: str | None) -> list[str] | None:
    return _normalize_filter_list(value)


def _parse_csv_source_urls(value: str | None) -> list[tuple[str, str]] | None:
    if not value:
        return None
    override_sources = [url.strip() for url in value.split(",") if url.strip()]
    if not override_sources:
        return None
    return [
        (urlparse(url).netloc or f"Source {idx}", url)
        for idx, url in enumerate(override_sources, start=1)
    ]


def _parse_csv_source_ids(value: list[int] | str | None) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [int(item) for item in value]
    parsed: list[int] = []
    for item in str(value).split(","):
        candidate = item.strip()
        if not candidate:
            continue
        if not candidate.isdigit():
            raise HTTPException(
                status_code=400,
                detail="source_ids must be a comma-separated list of integers",
            )
        parsed.append(int(candidate))
    return parsed or None


def _prune_ingest_idempotency_cache() -> None:
    now = time.monotonic()
    expired_keys = [
        key
        for key, (_run_id, expires_at) in _INGEST_IDEMPOTENCY_CACHE.items()
        if expires_at <= now
    ]
    for key in expired_keys:
        _INGEST_IDEMPOTENCY_CACHE.pop(key, None)


def _get_existing_run_for_idempotency(idempotency_key: str | None) -> str | None:
    if not idempotency_key:
        return None
    _prune_ingest_idempotency_cache()
    existing = _INGEST_IDEMPOTENCY_CACHE.get(idempotency_key)
    if not existing:
        return None
    return existing[0]


def _remember_ingest_idempotency(idempotency_key: str | None, run_id: str) -> None:
    if not idempotency_key:
        return
    expires_at = time.monotonic() + max(60, _INGEST_IDEMPOTENCY_TTL_SECONDS)
    _INGEST_IDEMPOTENCY_CACHE[idempotency_key] = (run_id, expires_at)


async def _load_articles_from_db(
    *,
    source: str | None,
    sentiment: str | None,
    topic: str | None,
    search: str | None,
    published_since: datetime | None,
    published_until: datetime | None,
    offset: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    try:
        articles = await ingester.get_articles(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=published_since,
            published_until=published_until,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:
        logger.warning("DB read failed in _load_articles_from_db; returning empty list: %s", exc)
        return []
    if not articles:
        return []
    return [_normalize_article_payload(item) for item in articles]


async def _load_ranked_articles_v2(
    *,
    source: str | None,
    sentiment: str | None,
    topic: str | None,
    search: str | None,
    published_since: datetime | None,
    published_until: datetime | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    candidate_size = min(
        FEED_RANKING_V2_MAX_CANDIDATES,
        max(limit + offset, limit * FEED_RANKING_V2_CANDIDATE_MULTIPLIER),
    )
    candidates = await _load_articles_from_db(
        source=source,
        sentiment=sentiment,
        topic=topic,
        search=search,
        published_since=published_since,
        published_until=published_until,
        offset=0,
        limit=candidate_size,
        sort_by="date",
        sort_order="desc",
    )

    ranked = rank_articles(candidates)
    suppressed = 0
    if FEED_RANKING_V2_DEDUP_ENABLED:
        ranked, suppressed = suppress_near_duplicates(ranked)
    if suppressed:
        logger.info(
            "feed_ranking_v2 near_dedup_suppressed=%d candidates=%d",
            suppressed,
            len(candidates),
        )

    return ranked[offset : offset + limit]


async def _count_articles_from_db(
    *,
    source: str | None,
    sentiment: str | None,
    topic: str | None,
    search: str | None,
    published_since: datetime | None,
    published_until: datetime | None,
) -> int:
    try:
        return await ingester.count_articles_for_filters(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=published_since,
            published_until=published_until,
        )
    except Exception as exc:
        logger.warning("DB read failed in _count_articles_from_db; returning 0: %s", exc)
        return 0


async def _build_analytics_payload(articles: list[dict[str, Any]]) -> dict[str, Any]:
    sentiment_count: dict[str, int] = {}
    source_count: dict[str, int] = {}
    entity_count: dict[str, int] = {}
    topic_count: dict[str, int] = {}

    for article in articles:
        if article.get("sentiment"):
            sentiment = article.get("sentiment")
            sentiment_count[str(sentiment)] = sentiment_count.get(str(sentiment), 0) + 1
        if article.get("source"):
            source = article.get("source")
            source_count[str(source)] = source_count.get(str(source), 0) + 1
        for entity in article.get("key_entities", []):
            if not _is_valid_entity_name(entity):
                continue
            entity_name = str(entity)
            entity_count[entity_name] = entity_count.get(entity_name, 0) + 1
        for topic in article.get("topics", []):
            topic_count[str(topic)] = topic_count.get(str(topic), 0) + 1

    top_entities = sorted(
        [{"name": name, "count": count} for name, count in entity_count.items()],
        key=lambda row: cast("int", row["count"]),
        reverse=True,
    )[:5]
    top_topics = sorted(
        [{"name": name, "count": count} for name, count in topic_count.items()],
        key=lambda row: cast("int", row["count"]),
        reverse=True,
    )[:5]

    latest_run = await ingester.get_last_run()
    last_update = (
        latest_run.finished_at.timestamp()
        if latest_run and latest_run.finished_at
        else datetime.now().timestamp()
    )

    return {
        "sentiment_distribution": sentiment_count,
        "source_distribution": source_count,
        "top_entities": top_entities,
        "top_topics": top_topics,
        "processing_stats": {
            "avg_processing_time": 0.0,
            "articles_processed": len(articles),
            "last_update": last_update,
        },
    }


# Root
@app.get("/")
async def root():
    return {"message": "Financial News API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/articles", response_model=list[ArticleResponse])
async def get_articles(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    sentiment: str | None = None,
    topic: str | None = None,
    search: str | None = None,
    published_since: str | None = Query(
        None,
        description="ISO-8601 timestamp used as lower bound for published_at.",
    ),
    published_until: str | None = Query(
        None,
        description="ISO-8601 timestamp used as upper bound for published_at.",
    ),
    days: int | None = Query(
        None,
        ge=1,
        le=365,
        description="Only articles published in the last N days.",
    ),
    sort_by: str | None = Query(None, enum=["date", "relevance", "sentiment"]),
    sort_order: str | None = Query("desc", enum=["asc", "desc"]),
):
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    if FEED_RANKING_V2_ENABLED and sort_by == "relevance":
        articles = await _load_ranked_articles_v2(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=parsed_published_since,
            published_until=parsed_published_until,
            offset=offset,
            limit=limit,
        )
    else:
        articles = await _load_articles_from_db(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=parsed_published_since,
            published_until=parsed_published_until,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order or "desc",
        )
    return [ArticleResponse(**article) for article in articles]


@app.get("/api/articles/count")
async def get_articles_count(
    source: str | None = None,
    sentiment: str | None = None,
    topic: str | None = None,
    search: str | None = None,
    published_since: str | None = Query(
        None,
        description="ISO-8601 timestamp used as lower bound for published_at.",
    ),
    published_until: str | None = Query(
        None,
        description="ISO-8601 timestamp used as upper bound for published_at.",
    ),
    days: int | None = Query(
        None,
        ge=1,
        le=365,
        description="Only articles published in the last N days.",
    ),
):
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    total = await _count_articles_from_db(
        source=source,
        sentiment=sentiment,
        topic=topic,
        search=search,
        published_since=parsed_published_since,
        published_until=parsed_published_until,
    )
    return {"total": total}


@app.get("/api/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str, user_id: str | None = None):
    article_data = _normalize_article_payload(
        await ingester.get_article_payload(article_id) or {}
    )
    if not article_data.get("id"):
        raise HTTPException(status_code=404, detail="Article not found")
    if user_id:
        article_data["is_saved"] = await is_article_saved(user_id, article_id)
    return ArticleResponse(**article_data)


@app.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    articles = await _load_articles_from_db(
        source=None,
        sentiment=None,
        topic=None,
        search=None,
        published_since=None,
        published_until=None,
        offset=0,
        limit=500,
        sort_by="date",
        sort_order="desc",
    )
    return await _build_analytics_payload(articles)


@app.get("/api/sources")
async def get_sources(
    source_category: str | None = Query(
        None, description="Filter by source category."
    ),
    connector_type: str | None = Query(
        None, description="Filter by connector type."
    ),
    include_disabled: bool = Query(
        False, description="Include disabled sources."
    ),
):
    try:
        sources = await source_repo.list_sources(
            enabled_only=not include_disabled,
            source_category=source_category,
            connector_type=connector_type,
        )
    except Exception as exc:
        logger.warning("DB read failed in get_sources; using article-derived fallback: %s", exc)
        sources = []
    if not sources:
        articles = await _load_articles_from_db(
            source=None,
            sentiment=None,
            topic=None,
            search=None,
            published_since=None,
            published_until=None,
            offset=0,
            limit=500,
            sort_by="date",
            sort_order="desc",
        )
        values = sorted(
            {str(article.get("source", "")) for article in articles if article.get("source")}
        )
        return [
            {
                "id": _slugify_filter_value(source),
                "source_key": _slugify_filter_value(source),
                "name": source,
                "source_type": "rss",
                "source_category": None,
                "connector_type": None,
                "terms_url": None,
                "legal_basis": None,
                "provider_domain": None,
                "rate_profile": None,
                "requires_api_key": False,
                "requires_user_agent": False,
                "user_agent": None,
                "enabled": True,
                "crawl_interval_minutes": 30,
                "rate_limit_per_minute": 60,
            }
            for source in values
        ]

    return [_serialize_source(source) for source in sources]


@app.post("/api/sources")
async def upsert_source(
    source: SourceUpsertRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin")),
):
    request_id = _request_id_from_request(request)
    logger.info(
        "admin_upsert_source request_id=%s actor=%s source_key=%s",
        request_id,
        admin_actor,
        _source_key_from_request(source),
    )
    _validate_source_url_or_raise(source.url)
    source_key = _source_key_from_request(source)
    parsed = urlparse(source.url)

    source_config = SourceConfig(
        source_key=source_key,
        name=source.name,
        url=source.url,
        source_type=source.source_type,
        source_category=source.source_category,
        connector_type=source.connector_type or source.source_type,
        terms_url=source.terms_url,
        legal_basis=source.legal_basis or "public_web_feed",
        provider_domain=source.provider_domain or parsed.netloc.lower(),
        rate_profile=source.rate_profile or "standard",
        requires_api_key=source.requires_api_key,
        requires_user_agent=source.requires_user_agent,
        user_agent=source.user_agent,
        enabled=source.enabled,
        crawl_interval_minutes=max(1, int(source.crawl_interval_minutes)),
        rate_limit_per_minute=max(1, int(source.rate_limit_per_minute)),
        retry_policy=source.retry_policy or {},
        parser_contract=source.parser_contract or {},
    )
    persisted = await source_repo.upsert_sources([source_config])
    if not persisted:
        raise HTTPException(status_code=500, detail="Unable to persist source")
    return _serialize_source(persisted[0])


@app.delete("/api/sources/{source_identifier}")
async def disable_source(
    source_identifier: str,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin")),
):
    request_id = _request_id_from_request(request)
    logger.info(
        "admin_disable_source request_id=%s actor=%s source_identifier=%s",
        request_id,
        admin_actor,
        source_identifier,
    )
    source = await source_repo.set_enabled(source_identifier, enabled=False)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "disabled", "source": _serialize_source(source)}


@app.get("/api/sources/{source_identifier}/health")
async def get_source_health_by_id(source_identifier: str):
    source = await source_repo.get_by_identifier(source_identifier)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    health = await ingester.get_source_health()
    matched = next((item for item in health if item.get("source_id") == source.id), None)
    if matched is None:
        matched = {
            "source_id": source.id,
            "cursor_type": None,
            "cursor_value": None,
            "last_success_at": None,
            "consecutive_failures": 0,
            "next_retry_at": None,
            "last_latency_ms": None,
            "last_failure_at": None,
            "disabled_by_failure": False,
            "last_error": None,
            "updated_at": source.updated_at.isoformat() if source.updated_at else None,
        }

    crawl_interval_minutes = int(getattr(source, "crawl_interval_minutes", 30) or 30)
    if crawl_interval_minutes < 1:
        crawl_interval_minutes = 1

    now = datetime.now(UTC)
    last_success_at = matched.get("last_success_at")
    next_retry_at = matched.get("next_retry_at")
    consecutive_failures = int(matched.get("consecutive_failures") or 0)
    last_error = matched.get("last_error")
    disabled_by_failure = bool(matched.get("disabled_by_failure"))

    next_due_at = None
    if isinstance(next_retry_at, str) and next_retry_at.strip():
        next_due_at = next_retry_at
    elif isinstance(last_success_at, str) and last_success_at.strip():
        try:
            parsed_last_success = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
            if parsed_last_success.tzinfo is None:
                parsed_last_success = parsed_last_success.replace(tzinfo=UTC)
            next_due_at = (
                parsed_last_success + timedelta(minutes=crawl_interval_minutes)
            ).isoformat()
        except ValueError:
            next_due_at = None

    status = "unknown"
    if not source.enabled:
        status = "disabled"
    elif disabled_by_failure or consecutive_failures > 0 or bool(last_error):
        status = "degraded"
    elif isinstance(next_retry_at, str) and next_retry_at.strip():
        try:
            parsed_next_retry = datetime.fromisoformat(next_retry_at.replace("Z", "+00:00"))
            if parsed_next_retry.tzinfo is None:
                parsed_next_retry = parsed_next_retry.replace(tzinfo=UTC)
            status = "retrying" if parsed_next_retry > now else "stale"
        except ValueError:
            status = "degraded"
    elif isinstance(last_success_at, str) and last_success_at.strip():
        try:
            parsed_last_success = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
            if parsed_last_success.tzinfo is None:
                parsed_last_success = parsed_last_success.replace(tzinfo=UTC)
            status = (
                "healthy"
                if (now - parsed_last_success).total_seconds()
                <= crawl_interval_minutes * 60 * 2
                else "stale"
            )
        except ValueError:
            status = "unknown"
    elif source.enabled:
        status = "pending"

    matched = {
        **matched,
        "backfill_window_minutes": crawl_interval_minutes * 3,
        "next_due_at": next_due_at,
        "status": status,
    }

    return {
        "source": _serialize_source(source),
        "health": matched,
    }


@app.get("/api/admin/sources/{source_identifier}/health")
async def get_admin_source_health_by_id(
    source_identifier: str,
    _admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    return await get_source_health_by_id(source_identifier)


@app.post("/api/sources/validate")
async def validate_source(payload: SourceValidationRequest):
    _validate_source_url_or_raise(payload.source_url)
    parsed = urlparse(payload.source_url)
    messages: list[str] = []
    if "sec.gov" in parsed.netloc.lower():
        messages.append("SEC sources should include an explicit user-agent.")
    if payload.source_type not in {"rss", "sec", "json", "html"}:
        messages.append("Unknown source_type; fallback parser behavior will be used.")
    return {
        "valid": True,
        "source_url": payload.source_url,
        "source_type": payload.source_type,
        "provider_domain": parsed.netloc.lower(),
        "messages": messages,
    }


@app.get("/api/topics")
async def get_topics():
    try:
        topics = await ingester.get_topics()
    except Exception as exc:
        logger.warning("DB read failed in get_topics; returning empty list: %s", exc)
        topics = []
    topics = topics or []
    topics = sorted({str(topic) for topic in topics if topic})
    return [{"id": _slugify_filter_value(topic), "name": topic} for topic in topics]


@app.post("/api/analyze/sentiment")
async def analyze_sentiment(data: dict):
    if "text" not in data:
        raise HTTPException(status_code=400, detail="Text field is required")
    text = data["text"]
    return analyze_article_sentiment(text)


@app.get("/api/user/settings")
async def get_user_settings(request: Request, user_id: str | None = Query(None)):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_settings_repo.get(resolved_user_id)
    return _normalize_user_settings(persisted)


@app.put("/api/user/settings")
async def put_user_settings(
    payload: UserSettingsPayload,
    request: Request,
    user_id: str | None = Query(None),
):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_settings_repo.upsert(
        resolved_user_id,
        payload.model_dump(),
    )
    return _normalize_user_settings(persisted)


@app.post("/api/user/settings")
async def update_user_settings(
    settings: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_settings(settings)
    persisted = await user_settings_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "settings": _normalize_user_settings(persisted),
    }


@app.get("/api/user/alerts")
async def get_user_alerts(request: Request, user_id: str | None = Query(None)):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_alerts_repo.get(resolved_user_id)
    return _normalize_user_alerts(persisted)


@app.put("/api/user/alerts")
async def put_user_alerts(
    payload: UserAlertsPayload,
    request: Request,
    user_id: str | None = Query(None),
):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_alerts(payload.model_dump())
    persisted = await user_alerts_repo.upsert(resolved_user_id, normalized)
    return _normalize_user_alerts(persisted)


@app.post("/api/user/alerts")
async def update_user_alerts(
    payload: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
):
    await initialize_schema()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_alerts(payload)
    persisted = await user_alerts_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Alerts updated successfully",
        "alerts": _normalize_user_alerts(persisted),
    }


async def _queue_ingest_trigger(
    *,
    request_id: str,
    admin_actor: str,
    source_filter_values: list[str] | None,
    source_url_overrides: list[tuple[str, str]] | None,
    source_ids: list[int] | None,
    idempotency_key: str | None,
) -> dict[str, Any]:
    if idempotency_key:
        existing_run_id = _get_existing_run_for_idempotency(idempotency_key)
        if existing_run_id:
            return {
                "status": "queued",
                "run_id": existing_run_id,
                "started_at": datetime.now(UTC).isoformat(),
                "source_filters": source_filter_values,
                "source_ids": source_ids,
                "idempotent_replay": True,
            }

    logger.info(
        "admin_ingest_trigger request_id=%s actor=%s source_filters=%s source_ids=%s source_override_count=%d idempotency_key=%s",
        request_id,
        admin_actor,
        source_filter_values,
        source_ids,
        len(source_url_overrides or []),
        bool(idempotency_key),
    )
    run_id = await ingester.start_async_ingest(
        source_filters=source_filter_values,
        sources=source_url_overrides,
        source_ids=source_ids,
    )
    _remember_ingest_idempotency(idempotency_key, run_id)
    return {
        "status": "queued",
        "run_id": run_id,
        "started_at": datetime.now(UTC).isoformat(),
        "source_filters": source_filter_values,
        "source_ids": source_ids,
        "idempotent_replay": False,
    }


@app.post("/api/ingest")
async def run_ingest_sync(
    request: Request,
    source_urls: str | None = Query(None),
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    request_id = _request_id_from_request(request)
    sources: list[tuple[str, str]] | None = None
    if source_urls:
        override_sources = [url.strip() for url in source_urls.split(",") if url.strip()]
        if not override_sources:
            raise HTTPException(status_code=400, detail="source_urls cannot be empty")
        sources = [(urlparse(url).netloc or f"Source {idx}", url) for idx, url in enumerate(override_sources, start=1)]

    try:
        logger.info(
            "admin_ingest_sync request_id=%s actor=%s source_override_count=%d",
            request_id,
            admin_actor,
            len(sources or []),
        )
        result = await ingester.run_ingest(sources=sources)
        return result.as_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


@app.post("/api/ingest/trigger", status_code=202)
async def run_ingest_trigger(
    request: Request,
    payload: IngestTriggerRequest | None = None,
    source_filters: str | None = Query(None),
    source_urls: str | None = Query(None),
    source_ids: str | None = Query(None),
    idempotency_key_query: str | None = Query(None),
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    request_id = _request_id_from_request(request)
    payload = payload or IngestTriggerRequest()
    idempotency_key = (
        payload.idempotency_key
        or idempotency_key_query
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = _normalize_filter_list(payload.source_filters)
    if source_filter_values is None:
        source_filter_values = _parse_csv_filters(source_filters)

    source_url_overrides = None
    payload_source_urls = _normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    if source_url_overrides is None:
        source_url_overrides = _parse_csv_source_urls(source_urls)

    source_id_values = _parse_csv_source_ids(
        payload.source_ids if payload.source_ids is not None else source_ids
    )
    if source_url_overrides is not None and not source_url_overrides:
        raise HTTPException(status_code=400, detail="source_urls cannot be empty")

    try:
        return await _queue_ingest_trigger(
            request_id=request_id,
            admin_actor=admin_actor,
            source_filter_values=source_filter_values,
            source_url_overrides=source_url_overrides,
            source_ids=source_id_values,
            idempotency_key=idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/admin/ingest/run", status_code=202)
async def run_admin_ingest(
    payload: IngestTriggerRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    request_id = _request_id_from_request(request)
    idempotency_key = (
        payload.idempotency_key
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
    )
    source_filter_values = _normalize_filter_list(payload.source_filters)
    source_url_overrides = None
    payload_source_urls = _normalize_filter_list(payload.source_urls)
    if payload_source_urls is not None:
        source_url_overrides = [
            (urlparse(url).netloc or f"Source {idx}", url)
            for idx, url in enumerate(payload_source_urls, start=1)
            if str(url).strip()
        ]
    source_id_values = _parse_csv_source_ids(payload.source_ids)
    try:
        return await _queue_ingest_trigger(
            request_id=request_id,
            admin_actor=admin_actor,
            source_filter_values=source_filter_values,
            source_url_overrides=source_url_overrides,
            source_ids=source_id_values,
            idempotency_key=idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/ingest/status")
async def get_ingest_status():
    payload = (await ingester.get_last_run()).as_dict()
    try:
        payload["stored_article_count"] = await ingester.count_articles()
    except Exception as exc:
        logger.warning("DB read failed in get_ingest_status; using 0 stored_article_count: %s", exc)
        payload["stored_article_count"] = 0
    payload["scheduled_refresh_seconds"] = AUTO_INGEST_INTERVAL_SECONDS
    payload["continuous_runner"] = continuous_runner.get_status()
    return payload


@app.get("/api/ingest/telemetry")
async def get_ingest_telemetry():
    status_payload = await get_ingest_status()
    try:
        source_health = await ingester.get_source_health()
    except Exception as exc:
        logger.warning("DB read failed in get_ingest_telemetry; returning empty health: %s", exc)
        source_health = []

    requested_sources = int(status_payload.get("requested_sources") or 0)
    failed_sources = int(status_payload.get("failed_sources") or 0)
    success_rate = None
    if requested_sources > 0:
        success_rate = max(0.0, (requested_sources - failed_sources) / requested_sources)

    stale_cutoff = datetime.now(UTC) - timedelta(minutes=120)
    stale_sources = 0
    degraded_sources = 0
    for health_row in source_health:
        last_success_at = health_row.get("last_success_at")
        parsed_last_success_at: datetime | None = None
        if isinstance(last_success_at, str) and last_success_at.strip():
            try:
                parsed_last_success_at = datetime.fromisoformat(
                    last_success_at.replace("Z", "+00:00")
                )
                if parsed_last_success_at.tzinfo is None:
                    parsed_last_success_at = parsed_last_success_at.replace(tzinfo=UTC)
            except ValueError:
                parsed_last_success_at = None

        if parsed_last_success_at is None or parsed_last_success_at < stale_cutoff:
            stale_sources += 1
        if (
            bool(health_row.get("disabled_by_failure"))
            or int(health_row.get("consecutive_failures") or 0) > 0
            or bool(health_row.get("last_error"))
        ):
            degraded_sources += 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_minutes": 120,
        "runs": {
            "latest": status_payload,
            "success_rate": success_rate,
        },
        "sources": {
            "total": len(source_health),
            "degraded": degraded_sources,
            "stale": stale_sources,
        },
        "health": source_health,
    }


@app.post("/api/ingest/continuous/trigger", status_code=200)
async def trigger_continuous_ingest(
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    """Manually trigger one cycle of the continuous runner (all connectors + RSS)."""
    try:
        request_id = _request_id_from_request(request)
        logger.info(
            "admin_trigger_continuous_ingest request_id=%s actor=%s",
            request_id,
            admin_actor,
        )
        result = await continuous_runner.trigger_immediate()
        return {"status": "completed", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Continuous ingest failed: {exc}") from exc


@app.get("/api/ingest/continuous/status")
async def get_continuous_ingest_status():
    """Get detailed status of the continuous ingest runner and all connectors."""
    return continuous_runner.get_status()


@app.post("/api/ingest/continuous/connectors/{connector_name}")
async def set_continuous_connector_state(
    connector_name: str,
    payload: ConnectorToggleRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    request_id = _request_id_from_request(request)
    try:
        if payload.reset_override:
            result = continuous_runner.clear_connector_override(connector_name)
        elif payload.enabled is None:
            raise HTTPException(
                status_code=400,
                detail="Either enabled must be set or reset_override must be true.",
            )
        else:
            result = continuous_runner.set_connector_enabled(connector_name, payload.enabled)
        logger.info(
            "admin_connector_toggle request_id=%s actor=%s connector=%s payload=%s",
            request_id,
            admin_actor,
            connector_name,
            result,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "toggle": result, "connectors": continuous_runner.get_status().get("connectors", {})}


@app.get("/api/ingest/runs/{run_id}")
async def get_ingest_run(run_id: str):
    run = await ingester.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.as_dict()


@app.get("/api/ingestion/health")
async def get_ingestion_health():
    try:
        return await ingester.get_source_health()
    except Exception as exc:
        logger.warning("DB read failed in get_ingestion_health; returning empty list: %s", exc)
        return []


async def _notification_socket_loop(
    websocket: WebSocket,
    connection_id: str,
    user_id: str | None,
) -> None:
    await notification_manager.connect(websocket, connection_id, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(connection_id, user_id)


@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = str(uuid.uuid4())
    user_id = websocket.query_params.get("user_id")
    await _notification_socket_loop(websocket, connection_id, user_id)


@app.websocket("/ws")
async def websocket_canonical_endpoint(websocket: WebSocket):
    connection_id = str(uuid.uuid4())
    user_id = websocket.query_params.get("user_id")
    await _notification_socket_loop(websocket, connection_id, user_id)


@app.websocket("/ws/notifications/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str):
    connection_id = str(uuid.uuid4())
    await _notification_socket_loop(websocket, connection_id, user_id)


@app.post("/api/notifications/send")
async def send_notification(
    data: dict,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
):
    request_id = _request_id_from_request(request)
    logger.info(
        "admin_send_notification request_id=%s actor=%s notification_type=%s",
        request_id,
        admin_actor,
        data.get("type"),
    )
    if "type" not in data:
        raise HTTPException(status_code=400, detail="Notification type is required")
    if data["type"] == "market_alert" and "alert" in data:
        await notification_manager.broadcast_market_alert(
            data["alert"],
            request_id=request_id,
        )
    elif data["type"] == "news_update" and "news" in data:
        await notification_manager.broadcast_news_update(
            data["news"],
            request_id=request_id,
        )
    elif data["type"] == "user_notification" and "user_id" in data and "message" in data:
        message_payload = data["message"]
        if not isinstance(message_payload, dict):
            message_payload = {"message": str(message_payload)}
        await notification_manager.send_to_user(
            message_payload,
            data["user_id"],
            event_type="user_notification",
            request_id=request_id,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid notification format")
    return {"status": "success", "message": "Notification sent"}


@app.post("/api/users/{user_id}/saved-articles/{article_id}")
async def save_article_endpoint(user_id: str, article_id: str):
    raw_article = await ingester.get_article_payload(article_id)
    if raw_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article = _normalize_article_payload(raw_article)
    result = await save_article(user_id=user_id, article_id=article_id, snapshot=article)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.delete("/api/users/{user_id}/saved-articles/{article_id}")
async def unsave_article_endpoint(user_id: str, article_id: str):
    result = await unsave_article(user_id=user_id, article_id=article_id)
    if result["status"] == "error" and "not found" in result["message"]:
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.get("/api/users/{user_id}/saved-articles")
async def get_saved_articles_endpoint(user_id: str):
    return await get_saved_articles(user_id=user_id)


@app.get("/api/users/{user_id}/saved-articles/{article_id}/status")
async def check_article_saved_status(user_id: str, article_id: str):
    is_saved = await is_article_saved(user_id=user_id, article_id=article_id)
    return {"is_saved": is_saved}


async def run_startup_ingest() -> None:
    try:
        try:
            count = await ingester.count_articles()
        except Exception as exc:
            logger.warning("Startup count_articles failed; attempting bootstrap ingest: %s", exc)
            await ingester.run_ingest()
            return

        if count == 0:
            await ingester.run_ingest()
    except Exception as exc:
        logger.warning("Startup ingest failed: %s", exc)


async def _run_periodic_ingest(interval_seconds: int) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            return
        try:
            run_id = await ingester.start_async_ingest()
            logger.info(
                "Scheduled ingest queued run_id=%s interval_seconds=%s",
                run_id,
                interval_seconds,
            )
        except RuntimeError as exc:
            logger.info("Scheduled ingest skipped: %s", exc)
        except Exception as exc:
            logger.warning("Scheduled ingest failed: %s", exc)


@app.on_event("startup")
async def startup_event():
    _BACKGROUND_TASKS.append(asyncio.create_task(generate_demo_alerts()))
    _BACKGROUND_TASKS.append(asyncio.create_task(run_startup_ingest()))
    if AUTO_INGEST_INTERVAL_SECONDS > 0:
        _BACKGROUND_TASKS.append(
            asyncio.create_task(_run_periodic_ingest(AUTO_INGEST_INTERVAL_SECONDS))
        )
    # Start the continuous ingest runner (GDELT, SEC EDGAR, Newsdata.io + RSS)
    await continuous_runner.start()


@app.on_event("shutdown")
async def shutdown_event():
    # Stop the continuous runner first
    await continuous_runner.stop()
    for task in _BACKGROUND_TASKS:
        task.cancel()
    for task in _BACKGROUND_TASKS:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Background task shutdown warning: %s", exc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
