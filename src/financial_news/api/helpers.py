"""Shared API helper functions used by routes and compatibility exports."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from logging import Logger
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from pydantic import ValidationError

from financial_news.api.schemas import (
    SourceUpsertRequest,
    UserAlertsPayload,
    UserSettingsPayload,
)
from financial_news.services.feed_ranking import rank_articles, suppress_near_duplicates
from financial_news.utils import (
    coerce_datetime_utc,
    coerce_string_list,
    normalize_search_text,
    slugify_value,
)

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


def _with_request_id(payload: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {"request_id": request_id, **payload}


def _request_id_from_request(request: Request | None) -> str:
    if request is None:
        return str(uuid.uuid4())
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


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
        return str(header_user_id).strip()
    query_user_id = request.query_params.get("user_id")
    if query_user_id and query_user_id.strip():
        return str(query_user_id).strip()
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


async def _load_articles_from_db(
    *,
    ingester: Any,
    logger: Logger,
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
    ingester: Any,
    logger: Logger,
    source: str | None,
    sentiment: str | None,
    topic: str | None,
    search: str | None,
    published_since: datetime | None,
    published_until: datetime | None,
    offset: int,
    limit: int,
    candidate_multiplier: int,
    max_candidates: int,
    dedup_enabled: bool,
    similarity_threshold: float = 0.92,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    candidate_size = min(
        max_candidates,
        max(limit + offset, limit * max(2, candidate_multiplier)),
    )
    candidates = await _load_articles_from_db(
        ingester=ingester,
        logger=logger,
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
    if dedup_enabled:
        ranked, suppressed = suppress_near_duplicates(
            ranked,
            similarity_threshold=similarity_threshold,
        )
    if suppressed:
        logger.info(
            "feed_ranking_v2 near_dedup_suppressed=%d candidates=%d",
            suppressed,
            len(candidates),
        )

    return ranked[offset : offset + limit]


async def _count_articles_from_db(
    *,
    ingester: Any,
    logger: Logger,
    source: str | None,
    sentiment: str | None,
    topic: str | None,
    search: str | None,
    published_since: datetime | None,
    published_until: datetime | None,
) -> int:
    try:
        count = await ingester.count_articles_for_filters(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=published_since,
            published_until=published_until,
        )
        return int(count)
    except Exception as exc:
        logger.warning("DB read failed in _count_articles_from_db; returning 0: %s", exc)
        return 0


async def _build_analytics_payload(
    ingester: Any,
    articles: list[dict[str, Any]],
) -> dict[str, Any]:
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


def _parse_datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _freshness_threshold_seconds(interval_seconds: int | None = None) -> int:
    interval = max(300, int(interval_seconds or 300))
    return max(172800, interval * 24)


async def _build_freshness_snapshot(
    *,
    ingester: Any,
    runner_status: dict[str, Any] | None = None,
    source_health: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    latest_success: datetime | None = None
    latest_failure: datetime | None = None

    if source_health is None:
        try:
            source_health = cast(list[dict[str, Any]], await ingester.get_source_health())
        except Exception:
            source_health = []

    for row in source_health:
        parsed_success = _parse_datetime_or_none(row.get("last_success_at"))
        if parsed_success is not None and (
            latest_success is None or parsed_success > latest_success
        ):
            latest_success = parsed_success

        parsed_failure = _parse_datetime_or_none(row.get("last_failure_at"))
        if parsed_failure is not None and (
            latest_failure is None or parsed_failure > latest_failure
        ):
            latest_failure = parsed_failure

    try:
        latest_run = await ingester.get_last_run()
    except Exception:
        latest_run = None
    latest_run_finished_at = getattr(latest_run, "finished_at", None)
    latest_run_items_stored = int(getattr(latest_run, "items_stored", 0) or 0)
    if (
        latest_run
        and latest_run_finished_at
        and latest_run_items_stored > 0
        and (latest_success is None or latest_run_finished_at > latest_success)
    ):
        latest_success = latest_run_finished_at

    lag_seconds = (
        max(0, int((datetime.now(UTC) - latest_success).total_seconds()))
        if latest_success is not None
        else None
    )
    threshold_seconds = _freshness_threshold_seconds(
        int((runner_status or {}).get("interval_seconds") or 0)
    )
    return {
        "last_success_at": latest_success.isoformat() if latest_success else None,
        "last_failure_at": latest_failure.isoformat() if latest_failure else None,
        "freshness_lag_seconds": lag_seconds,
        "freshness_threshold_seconds": threshold_seconds,
        "freshness_state": (
            "unknown"
            if lag_seconds is None
            else "fresh"
            if lag_seconds <= threshold_seconds
            else "stale"
        ),
        "source_of_truth": "postgres",
        "data_mode": "backend",
        "computed_at": datetime.now(UTC).isoformat(),
    }


def _ingest_telemetry_with_freshness(
    *,
    status_payload: dict[str, Any],
    source_health: list[dict[str, Any]],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    requested_sources = int(status_payload.get("requested_sources") or 0)
    failed_sources = int(status_payload.get("failed_sources") or 0)
    success_rate = None
    if requested_sources > 0:
        success_rate = max(
            0.0,
            (requested_sources - failed_sources) / requested_sources,
        )

    stale_cutoff = datetime.now(UTC).timestamp() - 120 * 60
    stale_sources = 0
    degraded_sources = 0
    for health_row in source_health:
        last_success_at = _parse_datetime_or_none(health_row.get("last_success_at"))
        if last_success_at is None or last_success_at.timestamp() < stale_cutoff:
            stale_sources += 1
        if int(health_row.get("consecutive_failures") or 0) > 0 or bool(
            health_row.get("disabled_by_failure")
        ):
            degraded_sources += 1

    return {
        "requested_sources": requested_sources,
        "failed_sources": failed_sources,
        "success_rate": success_rate,
        "stale_sources": stale_sources,
        "degraded_sources": degraded_sources,
        "source_health": source_health,
        **freshness,
    }


def _request_started_at() -> float:
    return time.monotonic()
