#!/usr/bin/env python3
"""Financial News API"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse

from financial_news.api.websockets import (
    manager as notification_manager,
    generate_demo_alerts,
)
from financial_news.services.news_ingest import NewsIngestor
from financial_news.services.continuous_runner import get_runner as get_continuous_runner
from financial_news.core.sentiment import analyze_article_sentiment
from financial_news.core.summarizer_config import setup_logging
from financial_news.storage import get_session_factory
from financial_news.storage.repositories import SourceConfig, SourceRepository
from financial_news.api.saved_articles import (
    get_saved_articles,
    is_article_saved,
    save_article,
    unsave_article,
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


class ArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str
    summarized_headline: Optional[str] = None
    summary_bullets: List[str] = []
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    market_impact_score: Optional[float] = None
    key_entities: List[str] = []
    topics: List[str] = []


class AnalyticsResponse(BaseModel):
    sentiment_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    top_entities: List[Dict[str, int]]
    top_topics: List[Dict[str, int]]
    processing_stats: Dict[str, float]


class SourceUpsertRequest(BaseModel):
    id: Optional[str] = None
    name: str
    url: str
    source_type: str = "rss"
    source_category: Optional[str] = None
    connector_type: Optional[str] = None
    crawl_interval_minutes: int = 30
    rate_limit_per_minute: int = 60
    enabled: bool = True
    terms_url: Optional[str] = None
    legal_basis: Optional[str] = None
    provider_domain: Optional[str] = None
    rate_profile: Optional[str] = None
    requires_api_key: bool = False
    requires_user_agent: bool = False
    user_agent: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    parser_contract: Optional[Dict[str, Any]] = None


class SourceValidationRequest(BaseModel):
    source_url: str
    source_type: str = "rss"


session_factory = get_session_factory()
ingester = NewsIngestor(session_factory=session_factory)
source_repo = SourceRepository(session_factory=session_factory)
continuous_runner = get_continuous_runner(session_factory=session_factory)
LAST_INGEST_RUN = None
AUTO_INGEST_INTERVAL_SECONDS = int(
    os.getenv("NEWS_INGEST_INTERVAL_SECONDS", "0") or "0"
)
_BACKGROUND_TASKS: list[asyncio.Task[Any]] = []

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
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_optional_datetime_param(
    value: Optional[str],
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
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_published_since(value: Optional[str]) -> datetime | None:
    return _parse_optional_datetime_param(value, param_name="published_since")


def _parse_published_until(value: Optional[str]) -> datetime | None:
    return _parse_optional_datetime_param(value, param_name="published_until")


def _normalize_search_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value)
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _search_matches_article(article: Dict[str, Any], search: Optional[str]) -> bool:
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


def _normalize_article_payload(article: Dict[str, Any]) -> Dict[str, Any]:
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


def _slug_like(source: Optional[str], candidate: str) -> bool:
    return _slugify_filter_value(source) == _slugify_filter_value(candidate)


def _serialize_source(source: Any) -> Dict[str, Any]:
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
) -> list[Dict[str, Any]]:
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


async def _build_analytics_payload(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    sentiment_count: Dict[str, int] = {}
    source_count: Dict[str, int] = {}
    entity_count: Dict[str, int] = {}
    topic_count: Dict[str, int] = {}

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
        key=lambda row: row["count"],
        reverse=True,
    )[:5]
    top_topics = sorted(
        [{"name": name, "count": count} for name, count in topic_count.items()],
        key=lambda row: row["count"],
        reverse=True,
    )[:5]

    latest_run = await ingester.get_last_run()
    last_update = latest_run.finished_at.timestamp() if latest_run else datetime.now().timestamp()

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


@app.get("/api/articles", response_model=List[ArticleResponse])
async def get_articles(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    published_since: Optional[str] = Query(
        None,
        description="ISO-8601 timestamp used as lower bound for published_at.",
    ),
    published_until: Optional[str] = Query(
        None,
        description="ISO-8601 timestamp used as upper bound for published_at.",
    ),
    days: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Only articles published in the last N days.",
    ),
    sort_by: Optional[str] = Query(None, enum=["date", "relevance", "sentiment"]),
    sort_order: Optional[str] = Query("desc", enum=["asc", "desc"]),
):
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(timezone.utc) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

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
        sort_order=sort_order,
    )
    return [ArticleResponse(**article) for article in articles]


@app.get("/api/articles/count")
async def get_articles_count(
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    published_since: Optional[str] = Query(
        None,
        description="ISO-8601 timestamp used as lower bound for published_at.",
    ),
    published_until: Optional[str] = Query(
        None,
        description="ISO-8601 timestamp used as upper bound for published_at.",
    ),
    days: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Only articles published in the last N days.",
    ),
):
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(timezone.utc) - timedelta(days=days)
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
async def get_article(article_id: str, user_id: Optional[str] = None):
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
    source_category: Optional[str] = Query(
        None, description="Filter by source category."
    ),
    connector_type: Optional[str] = Query(
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
async def upsert_source(source: SourceUpsertRequest):
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
async def disable_source(source_identifier: str):
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
    return {
        "source": _serialize_source(source),
        "health": matched,
    }


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
async def analyze_sentiment(data: Dict):
    if "text" not in data:
        raise HTTPException(status_code=400, detail="Text field is required")
    text = data["text"]
    return analyze_article_sentiment(text)


@app.get("/api/user/settings")
async def get_user_settings():
    settings = {
        "darkMode": True,
        "autoRefresh": False,
        "refreshInterval": 5,
        "defaultFilters": {
            "sources": [],
            "topics": [],
            "sentiment": "",
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
    return settings


@app.post("/api/user/settings")
async def update_user_settings(settings: Dict):
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "settings": settings,
    }


@app.post("/api/ingest")
async def run_ingest_sync(source_urls: Optional[str] = Query(None)):
    sources: list[tuple[str, str]] | None = None
    if source_urls:
        override_sources = [url.strip() for url in source_urls.split(",") if url.strip()]
        if not override_sources:
            raise HTTPException(status_code=400, detail="source_urls cannot be empty")
        sources = [(urlparse(url).netloc or f"Source {idx}", url) for idx, url in enumerate(override_sources, start=1)]

    try:
        result = await ingester.run_ingest(sources=sources)
        return result.as_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


@app.post("/api/ingest/trigger", status_code=202)
async def run_ingest_trigger(
    source_filters: Optional[str] = Query(None),
    source_urls: Optional[str] = Query(None),
):
    source_filter_values = [value.strip() for value in source_filters.split(",")] if source_filters else None
    sources = None
    if source_urls:
        override_sources = [url.strip() for url in source_urls.split(",") if url.strip()]
        if not override_sources:
            raise HTTPException(status_code=400, detail="source_urls cannot be empty")
        sources = [(urlparse(url).netloc or f"Source {idx}", url) for idx, url in enumerate(override_sources, start=1)]

    try:
        run_id = await ingester.start_async_ingest(
            source_filters=source_filter_values,
            sources=sources,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "queued",
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_filters": source_filter_values,
    }


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


@app.post("/api/ingest/continuous/trigger", status_code=200)
async def trigger_continuous_ingest():
    """Manually trigger one cycle of the continuous runner (all connectors + RSS)."""
    try:
        result = await continuous_runner.trigger_immediate()
        return {"status": "completed", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Continuous ingest failed: {exc}") from exc


@app.get("/api/ingest/continuous/status")
async def get_continuous_ingest_status():
    """Get detailed status of the continuous ingest runner and all connectors."""
    return continuous_runner.get_status()


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


@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = str(uuid.uuid4())
    await notification_manager.connect(websocket, connection_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(connection_id)


@app.websocket("/ws/notifications/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str):
    connection_id = str(uuid.uuid4())
    await notification_manager.connect(websocket, connection_id, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(connection_id, user_id)


@app.post("/api/notifications/send")
async def send_notification(data: Dict):
    if "type" not in data:
        raise HTTPException(status_code=400, detail="Notification type is required")
    if data["type"] == "market_alert" and "alert" in data:
        await notification_manager.broadcast_market_alert(data["alert"])
    elif data["type"] == "news_update" and "news" in data:
        await notification_manager.broadcast_news_update(data["news"])
    elif data["type"] == "user_notification" and "user_id" in data and "message" in data:
        await notification_manager.send_to_user(data["message"], data["user_id"])
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
    asyncio.create_task(generate_demo_alerts())
    asyncio.create_task(run_startup_ingest())
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
