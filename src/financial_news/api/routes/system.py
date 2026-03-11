"""System, health, and shared metadata routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from financial_news.api.dependencies import (
    get_continuous_runner,
    get_ingester,
    get_logger,
    get_settings,
)
from financial_news.api.helpers import (
    _build_freshness_snapshot,
    _slugify_filter_value,
)
from financial_news.storage.db import get_db_health_check

router = APIRouter()

@router.get("/")
async def root(settings: Any = Depends(get_settings)) -> dict[str, str]:
    return {"message": "Financial News API", "version": settings.version}


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/ready")
async def health_ready(
    ingester: Any = Depends(get_ingester),
    continuous_runner: Any = Depends(get_continuous_runner),
) -> JSONResponse:
    db_ok = await get_db_health_check()()
    runner_status = continuous_runner.get_status()
    freshness = await _build_freshness_snapshot(
        ingester=ingester,
        runner_status=cast(dict[str, Any], runner_status),
    )
    freshness_ok = freshness.get("freshness_state") != "stale"
    checks = {
        "database": db_ok,
        "continuous_ingest": bool(
            runner_status.get("running") or not continuous_runner.enabled
        ),
        "ingest_freshness": freshness_ok,
    }
    payload = {
        "status": "ready" if all(checks.values()) else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
        "freshness": freshness,
    }
    if all(checks.values()):
        return JSONResponse(status_code=200, content=payload)
    return JSONResponse(status_code=503, content=payload)


@router.get("/api/topics")
async def get_topics(
    ingester: Any = Depends(get_ingester),
    logger: Any = Depends(get_logger),
) -> list[dict[str, str]]:
    try:
        topics = await ingester.get_topics()
    except Exception as exc:
        logger.warning(
            "DB read failed in get_topics; returning empty list: %s",
            exc,
        )
        topics = []
    topics = topics or []
    topics = sorted({str(topic) for topic in topics if topic})
    return [
        {"id": _slugify_filter_value(topic), "name": topic}
        for topic in topics
    ]


@router.post("/api/analyze/sentiment")
async def analyze_sentiment(data: dict[str, Any]) -> Any:
    from financial_news.api.main import analyze_article_sentiment

    if "text" not in data:
        raise HTTPException(status_code=400, detail="Text field is required")
    return analyze_article_sentiment(data["text"])
