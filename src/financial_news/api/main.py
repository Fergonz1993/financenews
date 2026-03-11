#!/usr/bin/env python3
# mypy: disable-error-code=no-untyped-def
"""Financial News API compatibility module and app entrypoint."""

from __future__ import annotations

import os
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request

from financial_news.api import helpers as api_helpers
from financial_news.api import ingest_state
from financial_news.api.app_factory import create_app
from financial_news.api.container import get_app_container
from financial_news.api.dependencies import require_admin_access
from financial_news.api.lifecycle import (
    run_startup_ingest,
    shutdown_services,
    startup_services,
)
from financial_news.api.middleware import request_id_middleware
from financial_news.api.routes.articles import (
    get_analytics as route_get_analytics,
)
from financial_news.api.routes.articles import (
    get_article as route_get_article,
)
from financial_news.api.routes.articles import (
    get_articles_count as route_get_articles_count,
)
from financial_news.api.routes.ingest import (
    get_continuous_ingest_status as route_get_continuous_ingest_status,
)
from financial_news.api.routes.ingest import (
    get_ingest_run as route_get_ingest_run,
)
from financial_news.api.routes.ingest import (
    get_ingest_telemetry as route_get_ingest_telemetry,
)
from financial_news.api.routes.ingest import (
    get_ingestion_health as route_get_ingestion_health,
)
from financial_news.api.routes.ingest import (
    run_admin_ingest as route_run_admin_ingest,
)
from financial_news.api.routes.ingest import (
    run_ingest_sync as route_run_ingest_sync,
)
from financial_news.api.routes.ingest import (
    run_ingest_trigger as route_run_ingest_trigger,
)
from financial_news.api.routes.ingest import (
    set_continuous_connector_state as route_set_continuous_connector_state,
)
from financial_news.api.routes.ingest import (
    trigger_continuous_ingest as route_trigger_continuous_ingest,
)
from financial_news.api.routes.notifications import (
    send_notification as route_send_notification,
)
from financial_news.api.routes.notifications import (
    user_websocket_endpoint as route_user_websocket_endpoint,
)
from financial_news.api.routes.notifications import (
    websocket_canonical_endpoint as route_websocket_canonical_endpoint,
)
from financial_news.api.routes.notifications import (
    websocket_endpoint as route_websocket_endpoint,
)
from financial_news.api.routes.sources import (
    disable_source as route_disable_source,
)
from financial_news.api.routes.sources import (
    get_source_health_by_id as route_get_source_health_by_id,
)
from financial_news.api.routes.sources import (
    get_sources as route_get_sources,
)
from financial_news.api.routes.sources import (
    upsert_source as route_upsert_source,
)
from financial_news.api.routes.sources import (
    validate_source as route_validate_source,
)
from financial_news.api.routes.system import (
    analyze_sentiment as analyze_sentiment_route,
)
from financial_news.api.routes.system import (
    get_topics as route_get_topics,
)
from financial_news.api.routes.system import (
    health_check as route_health_check,
)
from financial_news.api.routes.system import (
    health_live as route_health_live,
)
from financial_news.api.routes.system import (
    health_ready as route_health_ready,
)
from financial_news.api.routes.system import (
    root as route_root,
)
from financial_news.api.routes.users import (
    check_article_saved_status as route_check_article_saved_status,
)
from financial_news.api.routes.users import (
    get_saved_articles_endpoint as route_get_saved_articles_endpoint,
)
from financial_news.api.routes.users import (
    get_user_alerts as route_get_user_alerts,
)
from financial_news.api.routes.users import (
    get_user_settings as route_get_user_settings,
)
from financial_news.api.routes.users import (
    put_user_alerts as route_put_user_alerts,
)
from financial_news.api.routes.users import (
    put_user_settings as route_put_user_settings,
)
from financial_news.api.routes.users import (
    save_article_endpoint as route_save_article_endpoint,
)
from financial_news.api.routes.users import (
    unsave_article_endpoint as route_unsave_article_endpoint,
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
from financial_news.storage import initialize_schema
from financial_news.storage.repositories import SourceConfig

settings = get_settings()
ADMIN_API_KEY = settings.admin.api_key.strip()
ADMIN_ALLOWED_ROLES = settings.admin.allowed_roles
ADMIN_RATE_LIMIT_PER_MINUTE = settings.admin.rate_limit_per_minute
_ADMIN_REQUEST_WINDOW_SECONDS = 60
_ADMIN_REQUEST_HISTORY: dict[str, list[float]] = {}
ingest_state.set_idempotency_ttl(settings.ingest.idempotency_ttl_seconds)

_build_freshness_snapshot = api_helpers._build_freshness_snapshot
_coerce_float = api_helpers._coerce_float
_coerce_list = api_helpers._coerce_list
_default_user_alerts = api_helpers._default_user_alerts
_default_user_settings = api_helpers._default_user_settings
_is_valid_entity_name = api_helpers._is_valid_entity_name
_load_articles_from_db = api_helpers._load_articles_from_db
_load_ranked_articles_v2 = api_helpers._load_ranked_articles_v2
_normalize_article_payload = api_helpers._normalize_article_payload
_normalize_filter_list = api_helpers._normalize_filter_list
_normalize_search_text = api_helpers._normalize_search_text
_normalize_user_alerts = api_helpers._normalize_user_alerts
_normalize_user_settings = api_helpers._normalize_user_settings
_parse_csv_filters = api_helpers._parse_csv_filters
_parse_csv_source_ids = api_helpers._parse_csv_source_ids
_parse_csv_source_urls = api_helpers._parse_csv_source_urls
_parse_datetime = api_helpers._parse_datetime
_parse_optional_datetime_param = api_helpers._parse_optional_datetime_param
_parse_published_since = api_helpers._parse_published_since
_parse_published_until = api_helpers._parse_published_until
_search_matches_article = api_helpers._search_matches_article
_slugify_filter_value = api_helpers._slugify_filter_value
_validate_source_url_or_raise = api_helpers._validate_source_url_or_raise
_get_existing_run_for_idempotency = ingest_state._get_existing_run_for_idempotency
_prune_ingest_idempotency_cache = ingest_state._prune_ingest_idempotency_cache
_remember_ingest_idempotency = ingest_state._remember_ingest_idempotency
_INGEST_IDEMPOTENCY_CACHE = ingest_state._INGEST_IDEMPOTENCY_CACHE

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

def _request_actor_from_headers(request: Request, *, trusted: bool = True) -> str:
    actor = request.headers.get("x-admin-user") or request.headers.get("x-admin-actor")
    if actor:
        return str(actor).strip()
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

    admin_user = request.headers.get("x-admin-user", role or "admin")
    return str(admin_user)
async def startup_event():
    container = get_app_container(app)
    await startup_services(app.state, container)


async def shutdown_event():
    container = get_app_container(app)
    await shutdown_services(app.state, container)

app = create_app()
container = get_app_container(app)
logger = container.logger
session_factory = container.session_factory
ingester = container.ingester
source_repo = container.source_repo
user_settings_repo = container.user_settings_repo
user_alerts_repo = container.user_alerts_repo
continuous_runner = container.continuous_runner
AUTO_INGEST_INTERVAL_SECONDS = max(0, settings.ingest.auto_ingest_interval_seconds)
analyze_sentiment = analyze_sentiment_route


def _source_key_from_request(payload: SourceUpsertRequest) -> str:
    candidate = payload.id or payload.name
    slug = _slugify_filter_value(candidate)
    if slug:
        return slug
    return f"source-{uuid.uuid4().hex[:8]}"


async def _build_analytics_payload(articles: list[dict[str, Any]]) -> dict[str, Any]:
    return await api_helpers._build_analytics_payload(ingester, articles)


async def get_articles(**kwargs: Any) -> list[ArticleResponse]:
    limit = kwargs.get("limit", 10)
    offset = kwargs.get("offset", 0)
    source = kwargs.get("source")
    sentiment = kwargs.get("sentiment")
    topic = kwargs.get("topic")
    search = kwargs.get("search")
    published_since = kwargs.get("published_since")
    published_until = kwargs.get("published_until")
    days = kwargs.get("days")
    sort_by = kwargs.get("sort_by")
    sort_order = kwargs.get("sort_order", "desc")

    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    if FEED_RANKING_V2_ENABLED and sort_by == "relevance":
        articles = await _load_ranked_articles_v2(
            ingester=ingester,
            logger=logger,
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=parsed_published_since,
            published_until=parsed_published_until,
            offset=offset,
            limit=limit,
            candidate_multiplier=FEED_RANKING_V2_CANDIDATE_MULTIPLIER,
            max_candidates=FEED_RANKING_V2_MAX_CANDIDATES,
            dedup_enabled=FEED_RANKING_V2_DEDUP_ENABLED,
        )
    else:
        articles = await _load_articles_from_db(
            ingester=ingester,
            logger=logger,
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=parsed_published_since,
            published_until=parsed_published_until,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    return [ArticleResponse(**article) for article in articles]


async def get_ingest_status() -> dict[str, Any]:
    payload = (await ingester.get_last_run()).as_dict()
    try:
        payload["stored_article_count"] = await ingester.count_articles()
    except Exception as exc:
        logger.warning(
            "DB read failed in get_ingest_status; using 0 stored_article_count: %s",
            exc,
        )
        payload["stored_article_count"] = 0
    runner_status = continuous_runner.get_status()
    freshness = await _build_freshness_snapshot(
        ingester=ingester,
        runner_status=runner_status,
    )
    payload["scheduled_refresh_seconds"] = AUTO_INGEST_INTERVAL_SECONDS
    payload["continuous_runner"] = runner_status
    payload.update(freshness)
    return payload


get_analytics = route_get_analytics
get_article = route_get_article
get_articles_count = route_get_articles_count
get_continuous_ingest_status = route_get_continuous_ingest_status
get_ingest_run = route_get_ingest_run
get_ingest_telemetry = route_get_ingest_telemetry
get_ingestion_health = route_get_ingestion_health
run_admin_ingest = route_run_admin_ingest
run_ingest_sync = route_run_ingest_sync
run_ingest_trigger = route_run_ingest_trigger
set_continuous_connector_state = route_set_continuous_connector_state
trigger_continuous_ingest = route_trigger_continuous_ingest
send_notification = route_send_notification
user_websocket_endpoint = route_user_websocket_endpoint
websocket_canonical_endpoint = route_websocket_canonical_endpoint
websocket_endpoint = route_websocket_endpoint
disable_source = route_disable_source
get_source_health_by_id = route_get_source_health_by_id
get_sources = route_get_sources
upsert_source = route_upsert_source
validate_source = route_validate_source
get_topics = route_get_topics
health_check = route_health_check
health_live = route_health_live
health_ready = route_health_ready
root = route_root
check_article_saved_status = route_check_article_saved_status
get_saved_articles_endpoint = route_get_saved_articles_endpoint
get_user_alerts = route_get_user_alerts
get_user_settings = route_get_user_settings
put_user_alerts = route_put_user_alerts
put_user_settings = route_put_user_settings
save_article_endpoint = route_save_article_endpoint
unsave_article_endpoint = route_unsave_article_endpoint

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
