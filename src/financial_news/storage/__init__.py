"""Storage layer package for PostgreSQL repositories and bootstrap utilities."""

from .db import get_engine, get_session_factory, initialize_schema
from .models import (
    Article,
    ArticleDedupe,
    Base,
    IngestionRun,
    IngestionState,
    Source,
    UserSavedArticle,
    UserSettings,
    UserAlertPreferences,
)
from .repositories import (
    ArticleRepository,
    IngestionRunRepository,
    IngestionStateRepository,
    SourceConfig,
    SourceRepository,
    UserSettingsRepository,
    UserAlertPreferencesRepository,
    UserArticleStateRepository,
)

__all__ = [
    "Base",
    "Article",
    "ArticleDedupe",
    "Source",
    "IngestionRun",
    "IngestionState",
    "UserSavedArticle",
    "UserSettings",
    "UserAlertPreferences",
    "ArticleRepository",
    "SourceRepository",
    "SourceConfig",
    "IngestionStateRepository",
    "IngestionRunRepository",
    "UserSettingsRepository",
    "UserAlertPreferencesRepository",
    "UserArticleStateRepository",
    "get_engine",
    "get_session_factory",
    "initialize_schema",
]
