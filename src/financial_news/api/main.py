#!/usr/bin/env python3
# mypy: disable-error-code=no-untyped-def
"""Financial News API compatibility module and app entrypoint."""

from __future__ import annotations

import asyncio
import os
import secrets
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from pydantic import ValidationError

from financial_news.api.app_factory import create_app
from financial_news.api.dependencies import require_admin_access
from financial_news.api.middleware import request_id_middleware
from financial_news.api.routes.articles import (
    get_analytics,
    get_article,
    get_articles,
    get_articles_count,
)
from financial_news.api.routes.ingest import (
    get_continuous_ingest_status,
    get_ingest_run,
    get_ingest_status,
    get_ingest_telemetry,
    get_ingestion_health,
    run_admin_ingest,
    run_ingest_sync,
    run_ingest_trigger,
    set_continuous_connector_state,
    trigger_continuous_ingest,
)
from financial_news.api.routes.notifications import (
    send_notification,
    user_websocket_endpoint,
    websocket_canonical_endpoint,
    websocket_endpoint,
)
from financial_news.api.routes.sources import (
    disable_source,
    get_source_health_by_id,
    get_sources,
    upsert_source,
    validate_source,
)
from financial_news.api.routes.system import (
    analyze_sentiment as analyze_sentiment_route,
)
from financial_news.api.routes.system import (
    get_topics,
    health_check,
    health_live,
    health_ready,
    root,
)
from financial_news.api.routes.users import (
    check_article_saved_status,
    get_saved_articles_endpoint,
    get_user_alerts,
    get_user_settings,
    put_user_alerts,
    put_user_settings,
    save_article_endpoint,
    unsave_article_endpoint,
)
from financial_news.api.saved_articles import (
    get_saved_articles,
    is_article_saved,
    save_article,
    unsave_article,
)
from financial_news.api.schemas import (
    AnalyticsResponse,
    ArticleResponse,
    ConnectorToggleRequest,
    DefaultFiltersPayload,
    EmailAlertsPayload,
    IngestTriggerRequest,
    SourceUpsertRequest,
    SourceValidationRequest,
    UserAlertRulePayload,
    UserAlertsPayload,
    UserSettingsPayload,
    VisualizationPayload,
)
from financial_news.api.websockets import (
    generate_demo_alerts,
)
from financial_news.api.websockets import (
    manager as notification_manager,
)
from financial_news.config import get_settings
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
from financial_news.utils import (
    coerce_datetime_utc,
    coerce_string_list,
    normalize_search_text,
    slugify_value,
)

logger = setup_logging()
settings = get_settings()

session_factory = get_session_factory()
ingester = NewsIngestor(session_factory=session_factory)
source_repo = SourceRepository(session_factory=session_factory)
user_settings_repo = UserSettingsRepository(session_factory=session_factory)
user_alerts_repo = UserAlertPreferencesRepository(session_factory=session_factory)
continuous_runner = get_continuous_runner(session_factory=session_factory)
LAST_INGEST_RUN = None
AUTO_INGEST_INTERVAL_SECONDS = max(0, settings.ingest.auto_ingest_interval_seconds)
_BACKGROUND_TASKS: list[asyncio.Task[Any]] = []
ADMIN_API_KEY = settings.admin.api_key.strip()
ADMIN_ALLOWED_ROLES = settings.admin.allowed_roles
ADMIN_RATE_LIMIT_PER_MINUTE = settings.admin.rate_limit_per_minute
_ADMIN_REQUEST_WINDOW_SECONDS = 60
_ADMIN_REQUEST_HISTORY: dict[str, list[float]] = {}
_INGEST_IDEMPOTENCY_TTL_SECONDS = settings.ingest.idempotency_ttl_seconds
_INGEST_IDEMPOTENCY_CACHE: dict[str, tuple[str, float]] = {}

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
    return slugify_value(value)


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
        return int(raw)
    except ValueError:
        return default


FEED_RANKING_V2_ENABLED = settings.ingest.feed_ranking_v2_enabled
FEED_RANKING_V2_CANDIDATE_MULTIPLIER = max(
    2,
    settings.ingest.feed_ranking_v2_candidate_multiplier,
)
FEED_RANKING_V2_MAX_CANDIDATES = max(
    50,
    settings.ingest.feed_ranking_v2_max_candidates,
)
FEED_RANKING_V2_DEDUP_ENABLED = settings.ingest.feed_ranking_v2_dedup_enabled


def _with_request_id(payload: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {"request_id": request_id, **payload}


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


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any) -> list[str]:
    return coerce_string_list(value)


def _parse_datetime(value: Any) -> datetime:
    return coerce_datetime_utc(value)


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
    return normalize_search_text(value)


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
        logger.warning(
            "DB read failed in _load_articles_from_db; returning empty list: %s",
            exc,
        )
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


async def run_startup_ingest() -> None:
    try:
        try:
            count = await ingester.count_articles()
        except Exception as exc:
            logger.warning(
                "Startup count_articles failed; attempting bootstrap ingest: %s",
                exc,
            )
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


async def startup_event():
    _BACKGROUND_TASKS.clear()
    _BACKGROUND_TASKS.append(asyncio.create_task(generate_demo_alerts()))
    _BACKGROUND_TASKS.append(asyncio.create_task(run_startup_ingest()))
    if AUTO_INGEST_INTERVAL_SECONDS > 0:
        _BACKGROUND_TASKS.append(
            asyncio.create_task(_run_periodic_ingest(AUTO_INGEST_INTERVAL_SECONDS))
        )
    await continuous_runner.start()


async def shutdown_event():
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
    _BACKGROUND_TASKS.clear()

app = create_app()
analyze_sentiment = analyze_sentiment_route

__all__ = [
    "ADMIN_ALLOWED_ROLES",
    "ADMIN_API_KEY",
    "ADMIN_RATE_LIMIT_PER_MINUTE",
    "AnalyticsResponse",
    "ArticleResponse",
    "ConnectorToggleRequest",
    "DefaultFiltersPayload",
    "EmailAlertsPayload",
    "IngestTriggerRequest",
    "SourceConfig",
    "SourceUpsertRequest",
    "SourceValidationRequest",
    "UserAlertRulePayload",
    "UserAlertsPayload",
    "UserSettingsPayload",
    "VisualizationPayload",
    "analyze_article_sentiment",
    "analyze_sentiment",
    "analyze_sentiment_route",
    "app",
    "check_article_saved_status",
    "continuous_runner",
    "disable_source",
    "generate_demo_alerts",
    "get_analytics",
    "get_article",
    "get_articles",
    "get_articles_count",
    "get_continuous_ingest_status",
    "get_ingest_run",
    "get_ingest_status",
    "get_ingest_telemetry",
    "get_ingestion_health",
    "get_saved_articles",
    "get_saved_articles_endpoint",
    "get_settings",
    "get_source_health_by_id",
    "get_sources",
    "get_topics",
    "get_user_alerts",
    "get_user_settings",
    "health_check",
    "health_live",
    "health_ready",
    "ingester",
    "initialize_schema",
    "is_article_saved",
    "notification_manager",
    "put_user_alerts",
    "put_user_settings",
    "request_id_middleware",
    "require_admin_access",
    "root",
    "run_admin_ingest",
    "run_ingest_sync",
    "run_ingest_trigger",
    "run_startup_ingest",
    "save_article",
    "save_article_endpoint",
    "send_notification",
    "set_continuous_connector_state",
    "shutdown_event",
    "source_repo",
    "startup_event",
    "trigger_continuous_ingest",
    "unsave_article",
    "unsave_article_endpoint",
    "upsert_source",
    "user_websocket_endpoint",
    "validate_source",
    "websocket_canonical_endpoint",
    "websocket_endpoint",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api.host, port=settings.api.port)
