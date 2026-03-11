"""Application container for shared API services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from fastapi import FastAPI, Request

from financial_news.api.websockets import NotificationManager, manager
from financial_news.config import get_settings
from financial_news.core.summarizer_config import setup_logging
from financial_news.services.continuous_runner import (
    ContinuousIngestRunner,
    get_runner,
)
from financial_news.services.news_ingest import NewsIngestor
from financial_news.storage import get_session_factory
from financial_news.storage.repositories import (
    SourceRepository,
    UserAlertPreferencesRepository,
    UserSettingsRepository,
)


@dataclass(slots=True)
class AppContainer:
    """Shared application services for request handlers and lifecycle hooks."""

    settings: Any
    logger: Any
    session_factory: Any
    ingester: NewsIngestor
    source_repo: SourceRepository
    user_settings_repo: UserSettingsRepository
    user_alerts_repo: UserAlertPreferencesRepository
    continuous_runner: ContinuousIngestRunner
    notification_manager: NotificationManager


def build_container(*, session_factory: Any | None = None) -> AppContainer:
    """Create the canonical shared services container."""
    settings = get_settings()
    logger = setup_logging()
    resolved_session_factory = session_factory or get_session_factory()
    repo_session_factory = cast("Any", resolved_session_factory)
    return AppContainer(
        settings=settings,
        logger=logger,
        session_factory=resolved_session_factory,
        ingester=NewsIngestor(session_factory=resolved_session_factory),
        source_repo=SourceRepository(session_factory=repo_session_factory),
        user_settings_repo=UserSettingsRepository(session_factory=repo_session_factory),
        user_alerts_repo=UserAlertPreferencesRepository(
            session_factory=repo_session_factory
        ),
        continuous_runner=get_runner(session_factory=resolved_session_factory),
        notification_manager=manager,
    )


def attach_container(app: FastAPI, container: AppContainer) -> AppContainer:
    """Attach the shared container to FastAPI app state."""
    app.state.container = container
    return container


def get_app_container(app: FastAPI) -> AppContainer:
    """Fetch the shared services container from app state."""
    return cast(AppContainer, app.state.container)


def get_request_container(request: Request) -> AppContainer:
    """Resolve the shared services container from a request."""
    return get_app_container(request.app)
