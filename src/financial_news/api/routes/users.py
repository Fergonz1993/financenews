"""User preferences, alerts, and saved-article routes."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from financial_news.api.schemas import UserAlertsPayload, UserSettingsPayload

router = APIRouter()


def _api() -> Any:
    from financial_news.api import main as api_main

    return api_main


@router.get("/api/user/settings")
async def get_user_settings(
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    persisted = await api_main.user_settings_repo.get(resolved_user_id)
    return cast(dict[str, Any], api_main._normalize_user_settings(persisted))


@router.put("/api/user/settings")
async def put_user_settings(
    payload: UserSettingsPayload,
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    persisted = await api_main.user_settings_repo.upsert(
        resolved_user_id,
        payload.model_dump(),
    )
    return cast(dict[str, Any], api_main._normalize_user_settings(persisted))


@router.post("/api/user/settings")
async def update_user_settings(
    settings: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    normalized = api_main._normalize_user_settings(settings)
    persisted = await api_main.user_settings_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Settings updated successfully",
            "settings": cast(dict[str, Any], api_main._normalize_user_settings(persisted)),
    }


@router.get("/api/user/alerts")
async def get_user_alerts(
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    persisted = await api_main.user_alerts_repo.get(resolved_user_id)
    return cast(dict[str, Any], api_main._normalize_user_alerts(persisted))


@router.put("/api/user/alerts")
async def put_user_alerts(
    payload: UserAlertsPayload,
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    normalized = api_main._normalize_user_alerts(payload.model_dump())
    persisted = await api_main.user_alerts_repo.upsert(resolved_user_id, normalized)
    return cast(dict[str, Any], api_main._normalize_user_alerts(persisted))


@router.post("/api/user/alerts")
async def update_user_alerts(
    payload: dict[str, Any],
    request: Request,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    api_main = _api()
    await api_main.initialize_schema()
    resolved_user_id = api_main._resolve_user_id(request, user_id)
    normalized = api_main._normalize_user_alerts(payload)
    persisted = await api_main.user_alerts_repo.upsert(resolved_user_id, normalized)
    return {
        "status": "success",
        "message": "Alerts updated successfully",
            "alerts": cast(dict[str, Any], api_main._normalize_user_alerts(persisted)),
    }


@router.post("/api/users/{user_id}/saved-articles/{article_id}")
async def save_article_endpoint(user_id: str, article_id: str) -> dict[str, Any]:
    api_main = _api()
    raw_article = await api_main.ingester.get_article_payload(article_id)
    if raw_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article = api_main._normalize_article_payload(raw_article)
    result = await api_main.save_article(
        user_id=user_id,
        article_id=article_id,
        snapshot=article,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return cast(dict[str, Any], result)


@router.delete("/api/users/{user_id}/saved-articles/{article_id}")
async def unsave_article_endpoint(user_id: str, article_id: str) -> dict[str, Any]:
    api_main = _api()
    result = await api_main.unsave_article(user_id=user_id, article_id=article_id)
    if result["status"] == "error" and "not found" in result["message"]:
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return cast(dict[str, Any], result)


@router.get("/api/users/{user_id}/saved-articles")
async def get_saved_articles_endpoint(user_id: str) -> list[dict[str, Any]]:
    api_main = _api()
    return cast(list[dict[str, Any]], await api_main.get_saved_articles(user_id=user_id))


@router.get("/api/users/{user_id}/saved-articles/{article_id}/status")
async def check_article_saved_status(
    user_id: str,
    article_id: str,
) -> dict[str, bool]:
    api_main = _api()
    is_saved = await api_main.is_article_saved(user_id=user_id, article_id=article_id)
    return {"is_saved": is_saved}
