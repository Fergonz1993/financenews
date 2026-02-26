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
)
from .repositories import (
    ArticleRepository,
    IngestionRunRepository,
    IngestionStateRepository,
    SourceConfig,
    SourceRepository,
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
    "ArticleRepository",
    "SourceRepository",
    "SourceConfig",
    "IngestionStateRepository",
    "IngestionRunRepository",
    "UserArticleStateRepository",
    "get_engine",
    "get_session_factory",
    "initialize_schema",
]
