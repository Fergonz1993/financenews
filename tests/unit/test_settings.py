"""Tests for typed settings loading and caching behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_news.config.settings import (
    APIConfig,
    DatabaseConfig,
    Settings,
    _load_settings,
    get_settings,
    reload_settings,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_database_async_url_normalizes_supported_postgres_formats() -> None:
    postgres = DatabaseConfig(database_url="postgres://user:pass@db.example:5432/app")
    assert postgres.async_url == "postgresql+asyncpg://user:pass@db.example:5432/app"

    postgresql = DatabaseConfig(
        database_url="postgresql://user:pass@db.example:5432/app"
    )
    assert postgresql.async_url == "postgresql+asyncpg://user:pass@db.example:5432/app"

    raw = DatabaseConfig(database_url="user:pass@db.example:5432/app")
    assert raw.async_url == "postgresql+asyncpg://user:pass@db.example:5432/app"


def test_from_toml_merges_nested_groups_and_validates_types(tmp_path: Path) -> None:
    baseline = Settings.from_env()
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        """
[financial_news]
version = "2.5.0"

[financial_news.database]
host = "db.internal"
port = 15432

[financial_news.api]
cors_origins = ["https://ui.example"]
""".strip(),
        encoding="utf-8",
    )

    settings = Settings.from_toml(str(config_path))

    assert settings.version == "2.5.0"
    assert isinstance(settings.database, DatabaseConfig)
    assert settings.database.host == "db.internal"
    assert settings.database.port == 15432
    assert settings.database.user == baseline.database.user
    assert isinstance(settings.api, APIConfig)
    assert settings.api.cors_origins == ["https://ui.example"]


def test_reload_settings_overrides_cached_env_settings(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        """
[financial_news]
version = "toml-version"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("APP_VERSION", "env-version")
    monkeypatch.setattr("financial_news.config.settings._settings_override", None)
    _load_settings.cache_clear()

    assert get_settings().version == "env-version"

    loaded = reload_settings(str(config_path))

    assert loaded.version == "toml-version"
    assert get_settings().version == "toml-version"

    monkeypatch.setattr("financial_news.config.settings._settings_override", None)
    _load_settings.cache_clear()
