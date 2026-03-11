"""Source registry and validation routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from financial_news.api.dependencies import (
    get_ingester,
    get_logger,
    get_source_repo,
    require_admin_access,
)
from financial_news.api.helpers import (
    _load_articles_from_db,
    _request_id_from_request,
    _serialize_source,
    _slugify_filter_value,
    _source_key_from_request,
    _validate_source_url_or_raise,
    _with_request_id,
)
from financial_news.api.schemas import SourceUpsertRequest, SourceValidationRequest
from financial_news.storage.repositories import SourceConfig

router = APIRouter()

@router.get("/api/sources")
async def get_sources(
    source_category: str | None = Query(None, description="Filter by source category."),
    connector_type: str | None = Query(None, description="Filter by connector type."),
    include_disabled: bool = Query(False, description="Include disabled sources."),
    source_repo: Any = Depends(get_source_repo),
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> list[dict[str, Any]]:
    try:
        sources = await source_repo.list_sources(
            enabled_only=not include_disabled,
            source_category=source_category,
            connector_type=connector_type,
        )
    except Exception as exc:
        logger.warning(
            "DB read failed in get_sources; using article-derived fallback: %s",
            exc,
        )
        sources = []
    if not sources:
        articles = await _load_articles_from_db(
            ingester=ingester,
            logger=logger,
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
            {
                str(article.get("source", ""))
                for article in articles
                if article.get("source")
            }
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


@router.post("/api/sources")
async def upsert_source(
    source: SourceUpsertRequest,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin")),
    source_repo: Any = Depends(get_source_repo),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
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
    return _with_request_id(
        _serialize_source(persisted[0]),
        request_id=request_id,
    )


@router.delete("/api/sources/{source_identifier}")
async def disable_source(
    source_identifier: str,
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin")),
    source_repo: Any = Depends(get_source_repo),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
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
    return _with_request_id(
        {"status": "disabled", "source": _serialize_source(source)},
        request_id=request_id,
    )


@router.get("/api/sources/{source_identifier}/health")
async def get_source_health_by_id(
    source_identifier: str,
    source_repo: Any = Depends(get_source_repo),
    ingester: Any = Depends(get_ingester),
) -> dict[str, Any]:
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
    crawl_interval_minutes = max(1, crawl_interval_minutes)
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
            parsed_last_success = datetime.fromisoformat(
                last_success_at.replace("Z", "+00:00")
            )
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
            parsed_next_retry = datetime.fromisoformat(
                next_retry_at.replace("Z", "+00:00")
            )
            if parsed_next_retry.tzinfo is None:
                parsed_next_retry = parsed_next_retry.replace(tzinfo=UTC)
            status = "retrying" if parsed_next_retry > now else "stale"
        except ValueError:
            status = "degraded"
    elif isinstance(last_success_at, str) and last_success_at.strip():
        try:
            parsed_last_success = datetime.fromisoformat(
                last_success_at.replace("Z", "+00:00")
            )
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
    return {"source": _serialize_source(source), "health": matched}


@router.get("/api/admin/sources/{source_identifier}/health")
async def get_admin_source_health_by_id(
    source_identifier: str,
    _admin_actor: str = Depends(require_admin_access("admin", "ops")),
) -> dict[str, Any]:
    return await get_source_health_by_id(source_identifier)


@router.post("/api/sources/validate")
async def validate_source(payload: SourceValidationRequest) -> dict[str, Any]:
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
