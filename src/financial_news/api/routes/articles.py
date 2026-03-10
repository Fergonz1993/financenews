"""Article and analytics routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from financial_news.api.dependencies import get_ingester, get_logger, get_settings
from financial_news.api.helpers import (
    _build_analytics_payload,
    _count_articles_from_db,
    _load_articles_from_db,
    _load_ranked_articles_v2,
    _normalize_article_payload,
    _parse_published_since,
    _parse_published_until,
)
from financial_news.api.schemas import AnalyticsResponse, ArticleResponse

router = APIRouter()

@router.get("/api/articles", response_model=list[ArticleResponse])
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
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
    settings: Any = Depends(get_settings),
) -> list[ArticleResponse]:
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    ingest_settings = settings.ingest
    if ingest_settings.feed_ranking_v2_enabled and sort_by == "relevance":
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
            candidate_multiplier=max(
                2,
                int(ingest_settings.feed_ranking_v2_candidate_multiplier),
            ),
            max_candidates=max(
                50,
                int(ingest_settings.feed_ranking_v2_max_candidates),
            ),
            dedup_enabled=bool(ingest_settings.feed_ranking_v2_dedup_enabled),
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
            sort_order=sort_order or "desc",
        )
    return [ArticleResponse(**article) for article in articles]


@router.get("/api/articles/count")
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
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> dict[str, int]:
    parsed_published_since = _parse_published_since(published_since)
    parsed_published_until = _parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    total = await _count_articles_from_db(
        ingester=ingester,
        logger=logger,
        source=source,
        sentiment=sentiment,
        topic=topic,
        search=search,
        published_since=parsed_published_since,
        published_until=parsed_published_until,
    )
    return {"total": total}


@router.get("/api/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    user_id: str | None = None,
    ingester: Any = Depends(get_ingester),
) -> ArticleResponse:
    from financial_news.api.main import is_article_saved

    article_data = _normalize_article_payload(
        await ingester.get_article_payload(article_id) or {}
    )
    if not article_data.get("id"):
        raise HTTPException(status_code=404, detail="Article not found")
    if user_id:
        article_data["is_saved"] = await is_article_saved(user_id, article_id)
    return ArticleResponse(**article_data)


@router.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
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
    return await _build_analytics_payload(ingester, articles)
