"""Saved articles service for the Financial News API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from financial_news.storage import UserArticleStateRepository, get_session_factory

logger = logging.getLogger(__name__)

_REPO = UserArticleStateRepository(session_factory=get_session_factory())


async def save_article(
    user_id: str,
    article_id: str,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a saved article for a user."""
    try:
        await _REPO.save_article(
            user_id=user_id,
            article_id=article_id,
            snapshot=snapshot or {"id": article_id, "saved_at": datetime.now().isoformat()},
        )
        return {"status": "success", "message": "Article saved successfully", "article_id": article_id}
    except Exception as exc:
        logger.error("Error saving article user=%s article=%s err=%s", user_id, article_id, exc)
        return {"status": "error", "message": f"Failed to save article: {str(exc)}"}


async def unsave_article(user_id: str, article_id: str) -> dict[str, Any]:
    """Remove a saved article for a user."""
    try:
        deleted = await _REPO.unsave_article(user_id=user_id, article_id=article_id)
        if deleted:
            return {"status": "success", "message": "Article removed from saved articles"}
        return {
            "status": "error",
            "message": "Article not found in saved articles",
        }
    except Exception as exc:
        logger.error("Error unsaving article user=%s article=%s err=%s", user_id, article_id, exc)
        return {"status": "error", "message": f"Failed to remove article: {str(exc)}"}


async def get_saved_articles(user_id: str) -> list[dict[str, Any]]:
    """Return all saved articles for a user."""
    try:
        return await _REPO.list_saved(user_id=user_id)
    except Exception as exc:
        logger.error("Error reading saved articles user=%s err=%s", user_id, exc)
        return []


async def is_article_saved(user_id: str, article_id: str) -> bool:
    """Check whether a given article is saved by the user."""
    try:
        return await _REPO.is_saved(user_id=user_id, article_id=article_id)
    except Exception as exc:
        logger.error("Error checking saved status user=%s article=%s err=%s", user_id, article_id, exc)
        return False
