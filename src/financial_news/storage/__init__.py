"""Storage layer package for PostgreSQL repositories and bootstrap utilities."""

from .db import get_engine, get_session_factory, initialize_schema
from .models import (
    Article,
    ArticleDedupe,
    Base,
    IngestionRun,
    IngestionState,
    Source,
    UserAlertPreferences,
    UserSavedArticle,
    UserSettings,
)
from .repositories import (
    ArticleRepository,
    IngestionRunRepository,
    IngestionStateRepository,
    SourceConfig,
    SourceRepository,
    UserAlertPreferencesRepository,
    UserArticleStateRepository,
    UserSettingsRepository,
)

__all__ = [
    "Article",
    "ArticleDedupe",
    "ArticleRepository",
    "Base",
    "IngestionRun",
    "IngestionRunRepository",
    "IngestionState",
    "IngestionStateRepository",
    "Source",
    "SourceConfig",
    "SourceRepository",
    "UserAlertPreferences",
    "UserAlertPreferencesRepository",
    "UserArticleStateRepository",
    "UserSavedArticle",
    "UserSettings",
    "UserSettingsRepository",
    "get_engine",
    "get_session_factory",
    "initialize_schema",
]
