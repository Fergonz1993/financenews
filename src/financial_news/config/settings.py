"""Typed application settings backed by ``pydantic-settings``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _config_file_candidates(config_path: str | None = None) -> list[Path]:
    if config_path:
        return [Path(config_path)]
    return [
        Path("pyproject.toml"),
        Path("config/development.toml"),
        Path("config/production.toml"),
    ]


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge nested dictionaries while preserving base defaults."""
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


class _SettingsGroup(BaseSettings):
    """Base class for settings groups loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


class DatabaseConfig(_SettingsGroup):
    """Database configuration settings."""

    host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("DB_HOST"),
    )
    port: int = Field(
        default=5432,
        validation_alias=AliasChoices("DB_PORT"),
    )
    name: str = Field(
        default="financial_news",
        validation_alias=AliasChoices("DB_NAME"),
    )
    user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("DB_USER"),
    )
    password: str = Field(
        default="",
        validation_alias=AliasChoices("DB_PASSWORD"),
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "DB_URL"),
    )
    echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("DB_ECHO"),
    )
    bootstrap_strategy: Literal["migrate", "create_all"] = Field(
        default="migrate",
        validation_alias=AliasChoices("DATABASE_BOOTSTRAP_STRATEGY"),
    )

    @property
    def url(self) -> str:
        """Get the preferred configured database URL."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        """Get the async SQLAlchemy URL."""
        raw_url = self.url
        if raw_url.startswith("postgresql+asyncpg://"):
            return raw_url
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://"):
            return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "://" not in raw_url:
            return f"postgresql+asyncpg://{raw_url}"
        return raw_url


class APIConfig(_SettingsGroup):
    """HTTP API configuration settings."""

    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("API_HOST"))
    port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("API_DEBUG"))
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("API_CORS_ORIGINS"),
    )
    rate_limit: str = Field(
        default="100/minute",
        validation_alias=AliasChoices("API_RATE_LIMIT"),
    )


class NewsSourcesConfig(_SettingsGroup):
    """External news source credentials and refresh configuration."""

    alpha_vantage_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ALPHA_VANTAGE_API_KEY"),
    )
    finnhub_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("FINNHUB_API_KEY"),
    )
    news_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("NEWS_API_KEY"),
    )
    polygon_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("POLYGON_API_KEY"),
    )
    refresh_interval: int = Field(
        default=300,
        validation_alias=AliasChoices("NEWS_REFRESH_INTERVAL"),
    )


class MLConfig(_SettingsGroup):
    """Machine learning configuration."""

    model_cache_dir: str = Field(
        default="./models",
        validation_alias=AliasChoices("MODEL_CACHE_DIR"),
    )
    sentiment_model: str = Field(
        default="finbert",
        validation_alias=AliasChoices("SENTIMENT_MODEL"),
    )
    summarization_model: str = Field(
        default="facebook/bart-large-cnn",
        validation_alias=AliasChoices("SUMMARIZATION_MODEL"),
    )
    max_sequence_length: int = 512
    batch_size: int = 16


class WebSocketConfig(_SettingsGroup):
    """Websocket server configuration."""

    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("WS_HOST"))
    port: int = Field(default=8001, validation_alias=AliasChoices("WS_PORT"))
    max_connections: int = 100
    heartbeat_interval: int = 30


class AdminConfig(_SettingsGroup):
    """Admin API protection and rate limiting."""

    api_key: str = Field(default="", validation_alias=AliasChoices("ADMIN_API_KEY"))
    allowed_roles_raw: str = Field(
        default="admin,ops",
        validation_alias=AliasChoices("ADMIN_ALLOWED_ROLES"),
    )
    rate_limit_per_minute: int = Field(
        default=30,
        validation_alias=AliasChoices("ADMIN_RATE_LIMIT_PER_MINUTE"),
    )

    @property
    def allowed_roles(self) -> set[str]:
        return {
            role.strip().lower()
            for role in self.allowed_roles_raw.split(",")
            if role.strip()
        }


class IngestConfig(_SettingsGroup):
    """Ingestion triggers, feature flags, and scoring toggles."""

    auto_ingest_interval_seconds: int = Field(
        default=0,
        validation_alias=AliasChoices("NEWS_INGEST_INTERVAL_SECONDS"),
    )
    idempotency_ttl_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices("INGEST_IDEMPOTENCY_TTL_SECONDS"),
    )
    feed_ranking_v2_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("FEED_RANKING_V2_ENABLED"),
    )
    feed_ranking_v2_candidate_multiplier: int = Field(
        default=5,
        validation_alias=AliasChoices("FEED_RANKING_V2_CANDIDATE_MULTIPLIER"),
    )
    feed_ranking_v2_max_candidates: int = Field(
        default=500,
        validation_alias=AliasChoices("FEED_RANKING_V2_MAX_CANDIDATES"),
    )
    feed_ranking_v2_dedup_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("FEED_RANKING_V2_DEDUP_ENABLED"),
    )


class ContinuousIngestConfig(_SettingsGroup):
    """Continuous connector runner configuration."""

    enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CONTINUOUS_INGEST_ENABLED"),
    )
    interval_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("CONTINUOUS_INGEST_INTERVAL_SECONDS"),
    )
    gdelt_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("GDELT_ENABLED"),
    )
    sec_edgar_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("SEC_EDGAR_ENABLED"),
    )
    newsdata_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("NEWSDATA_ENABLED"),
    )
    reddit_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("REDDIT_ENABLED"),
    )
    stock_correlation_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "STOCK_CORRELATION_ENABLED",
            "STOCK_CORRELATOR_ENABLED",
        ),
    )
    near_dedup_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("FEED_NEAR_DEDUP_ENABLED"),
    )
    near_dedup_similarity_threshold: float = Field(
        default=0.92,
        validation_alias=AliasChoices("FEED_NEAR_DEDUP_SIMILARITY_THRESHOLD"),
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(
        default="Financial News",
        validation_alias=AliasChoices("APP_NAME"),
    )
    version: str = Field(
        default="1.0.0",
        validation_alias=AliasChoices("APP_VERSION"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT"),
    )
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG"))
    secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("SECRET_KEY"),
    )
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    news_sources: NewsSourcesConfig = Field(default_factory=NewsSourcesConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    continuous_ingest: ContinuousIngestConfig = Field(
        default_factory=ContinuousIngestConfig
    )

    @classmethod
    def from_env(cls) -> Settings:
        """Create settings from environment variables."""
        return cls()

    @classmethod
    def from_toml(cls, config_path: str | None = None) -> Settings:
        """Create settings from environment variables and optional TOML file."""
        settings = cls.from_env()
        config_data: dict[str, Any] = {}
        for candidate in _config_file_candidates(config_path):
            if not candidate.exists() or candidate.suffix != ".toml":
                continue
            import tomllib

            with candidate.open("rb") as config_file:
                loaded = tomllib.load(config_file)
            config_data = loaded.get("financial_news", loaded)
            break

        if not config_data:
            return settings
        merged = _deep_merge_dicts(settings.model_dump(), config_data)
        return cls.model_validate(merged)


_settings_override: Settings | None = None


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings.from_env()


def get_settings() -> Settings:
    """Get cached application settings."""
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def reload_settings(config_path: str | None = None) -> Settings:
    """Reload settings from environment and config file."""
    global _settings_override
    _load_settings.cache_clear()
    _settings_override = Settings.from_toml(config_path)
    return _settings_override
