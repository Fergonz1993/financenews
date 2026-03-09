"""System, health, and shared metadata routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from financial_news.storage.db import get_db_health_check

router = APIRouter()


def _api() -> Any:
    from financial_news.api import main as api_main

    return api_main


@router.get("/")
async def root() -> dict[str, str]:
    api_main = _api()
    return {"message": "Financial News API", "version": api_main.get_settings().version}


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    api_main = _api()
    db_ok = await get_db_health_check()()
    runner_status = api_main.continuous_runner.get_status()
    checks = {
        "database": db_ok,
        "continuous_ingest": bool(runner_status.get("running") or not api_main.continuous_runner.enabled),
    }
    payload = {
        "status": "ready" if all(checks.values()) else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }
    if all(checks.values()):
        return JSONResponse(status_code=200, content=payload)
    return JSONResponse(status_code=503, content=payload)


@router.get("/api/topics")
async def get_topics() -> list[dict[str, str]]:
    api_main = _api()
    try:
        topics = await api_main.ingester.get_topics()
    except Exception as exc:
        api_main.logger.warning(
            "DB read failed in get_topics; returning empty list: %s",
            exc,
        )
        topics = []
    topics = topics or []
    topics = sorted({str(topic) for topic in topics if topic})
    return [
        {"id": api_main._slugify_filter_value(topic), "name": topic}
        for topic in topics
    ]


@router.post("/api/analyze/sentiment")
async def analyze_sentiment(data: dict[str, Any]) -> Any:
    api_main = _api()
    if "text" not in data:
        raise HTTPException(status_code=400, detail="Text field is required")
    return api_main.analyze_article_sentiment(data["text"])
