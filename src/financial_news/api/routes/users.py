"""User preferences, alerts, and saved-article routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from financial_news.api.dependencies import (
    get_ingester,
    get_user_alerts_repo,
    get_user_settings_repo,
    initialize_schema_if_needed,
)
from financial_news.api.helpers import (
    _normalize_article_payload,
    _normalize_user_alerts,
    _normalize_user_settings,
    _resolve_user_id,
)
from financial_news.api.schemas import UserAlertsPayload, UserSettingsPayload

router = APIRouter()


@router.get("/api/user/settings")
async def get_user_settings(
    request: Request,
    user_id: str | None = Query(None),
    user_settings_repo: Any = Depends(get_user_settings_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_settings_repo.get(resolved_user_id)
    return _normalize_user_settings(persisted)


@router.put("/api/user/settings")
async def put_user_settings(
    payload: UserSettingsPayload,
    request: Request,
    user_id: str | None = Query(None),
    user_settings_repo: Any = Depends(get_user_settings_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_settings_repo.upsert(
        resolved_user_id,
        payload.model_dump(),
    )
    return _normalize_user_settings(persisted)


@router.post("/api/user/settings")
async def update_user_settings(
    settings: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
    user_settings_repo: Any = Depends(get_user_settings_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_settings(settings)
    persisted = await user_settings_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "settings": _normalize_user_settings(persisted),
    }


@router.get("/api/user/alerts")
async def get_user_alerts(
    request: Request,
    user_id: str | None = Query(None),
    user_alerts_repo: Any = Depends(get_user_alerts_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    persisted = await user_alerts_repo.get(resolved_user_id)
    return _normalize_user_alerts(persisted)


@router.put("/api/user/alerts")
async def put_user_alerts(
    payload: UserAlertsPayload,
    request: Request,
    user_id: str | None = Query(None),
    user_alerts_repo: Any = Depends(get_user_alerts_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_alerts(payload.model_dump())
    persisted = await user_alerts_repo.upsert(resolved_user_id, normalized)
    return _normalize_user_alerts(persisted)


@router.post("/api/user/alerts")
async def update_user_alerts(
    payload: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
    user_alerts_repo: Any = Depends(get_user_alerts_repo),
) -> dict[str, Any]:
    await initialize_schema_if_needed()
    resolved_user_id = _resolve_user_id(request, user_id)
    normalized = _normalize_user_alerts(payload)
    persisted = await user_alerts_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Alerts updated successfully",
        "alerts": _normalize_user_alerts(persisted),
    }


@router.post("/api/users/{user_id}/saved-articles/{article_id}")
async def save_article_endpoint(
    user_id: str,
    article_id: str,
    ingester: Any = Depends(get_ingester),
) -> dict[str, Any]:
    from financial_news.api.main import save_article

    raw_article = await ingester.get_article_payload(article_id)
    if raw_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article = _normalize_article_payload(raw_article)
    result = await save_article(
        user_id=user_id,
        article_id=article_id,
        snapshot=article,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.delete("/api/users/{user_id}/saved-articles/{article_id}")
async def unsave_article_endpoint(user_id: str, article_id: str) -> dict[str, Any]:
    from financial_news.api.main import unsave_article

    result = await unsave_article(user_id=user_id, article_id=article_id)
    if result["status"] == "error" and "not found" in result["message"]:
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.get("/api/users/{user_id}/saved-articles")
async def get_saved_articles_endpoint(user_id: str) -> list[dict[str, Any]]:
    from financial_news.api.main import get_saved_articles

    return await get_saved_articles(user_id=user_id)


@router.get("/api/users/{user_id}/saved-articles/{article_id}/status")
async def check_article_saved_status(
    user_id: str,
    article_id: str,
) -> dict[str, bool]:
    from financial_news.api.main import is_article_saved

    is_saved = await is_article_saved(user_id=user_id, article_id=article_id)
    return {"is_saved": is_saved}
