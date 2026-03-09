"""Article and analytics routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query

from financial_news.api.schemas import AnalyticsResponse, ArticleResponse

router = APIRouter()


def _api() -> Any:
    from financial_news.api import main as api_main

    return api_main


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
) -> list[ArticleResponse]:
    api_main = _api()
    parsed_published_since = api_main._parse_published_since(published_since)
    parsed_published_until = api_main._parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    if api_main.FEED_RANKING_V2_ENABLED and sort_by == "relevance":
        articles = await api_main._load_ranked_articles_v2(
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
        articles = await api_main._load_articles_from_db(
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
) -> dict[str, int]:
    api_main = _api()
    parsed_published_since = api_main._parse_published_since(published_since)
    parsed_published_until = api_main._parse_published_until(published_until)
    if days is not None:
        since_days = datetime.now(UTC) - timedelta(days=days)
        if parsed_published_since is None or since_days > parsed_published_since:
            parsed_published_since = since_days

    total = await api_main._count_articles_from_db(
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
) -> ArticleResponse:
    api_main = _api()
    article_data = api_main._normalize_article_payload(
        await api_main.ingester.get_article_payload(article_id) or {}
    )
    if not article_data.get("id"):
        raise HTTPException(status_code=404, detail="Article not found")
    if user_id:
        article_data["is_saved"] = await api_main.is_article_saved(user_id, article_id)
    return ArticleResponse(**article_data)


@router.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics() -> dict[str, Any]:
    api_main = _api()
    articles = await api_main._load_articles_from_db(
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
    return cast(dict[str, Any], await api_main._build_analytics_payload(articles))
