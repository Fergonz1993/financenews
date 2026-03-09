"""SQLAlchemy models for PostgreSQL persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _default_list() -> list[str]:
    return []


def _default_dict() -> dict[str, Any]:
    return {}


class Base(DeclarativeBase):
    """Declarative base for persistence models."""


class Source(Base):
    """Canonical source registry."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32), default="rss")
    source_category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    connector_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    terms_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_basis: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rate_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    retry_policy_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=_default_dict,
    )
    parser_contract_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=_default_dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    articles: Mapped[list[Article]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    states: Mapped[list[IngestionState]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ux_sources_source_key", "source_key", unique=True),)


class Article(Base):
    """Normalized article artifact."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_key: Mapped[str] = mapped_column(String(128), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summarized_headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_bullets: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=_default_list
    )
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    market_impact_score: Mapped[float | None] = mapped_column(Float)
    key_entities: Mapped[list[str]] = mapped_column(ARRAY(Text), default=_default_list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), default=_default_list)
    content: Mapped[str] = mapped_column(Text)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    source: Mapped[Source | None] = relationship(back_populates="articles")

    __table_args__ = (
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source", "source_id"),
        Index("ix_articles_sentiment", "sentiment"),
        Index("ix_articles_topic", "topics", postgresql_using="gin"),
        Index("ix_articles_entities", "key_entities", postgresql_using="gin"),
        Index("ix_articles_source_name", "source_name"),
    )


class ArticleDedupe(Base):
    """Additional dedupe key store for traceability."""

    __tablename__ = "article_dedupe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    key_type: Mapped[str] = mapped_column(String(64))
    key_value: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("uq_article_dedupe_key", "key_type", "key_value", unique=True),
    )


class IngestionRun(Base):
    """Execution metadata for each ingest request."""

    __tablename__ = "ingestion_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    requested_sources: Mapped[int] = mapped_column(Integer, default=0)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_stored: Mapped[int] = mapped_column(Integer, default=0)
    items_skipped: Mapped[int] = mapped_column(Integer, default=0)
    failed_sources: Mapped[int] = mapped_column(Integer, default=0)
    source_errors: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[list[str]] = mapped_column(JSONB, default=_default_list)
    source_results: Mapped[list[dict[str, Any]] | dict[str, Any] | None] = mapped_column(
        JSONB, default=_default_list
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionState(Base):
    """Per-source checkpoint and backoff state."""

    __tablename__ = "ingestion_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), unique=True
    )
    cursor_type: Mapped[str] = mapped_column(String(64), default="published_at")
    cursor_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_by_failure: Mapped[bool] = mapped_column(Boolean, default=False)

    source: Mapped[Source] = relationship(back_populates="states")

    __table_args__ = (
        Index("ux_ingestion_state_source", "source_id", unique=True),
    )


class UserSavedArticle(Base):
    """User bookmark registry."""

    __tablename__ = "user_saved_articles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    article_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_user_saved_articles_article", "article_id"),)


class UserSettings(Base):
    """Persisted user preference settings."""

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    settings_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=_default_dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_user_settings_updated_at", "updated_at"),)


class UserAlertPreferences(Base):
    """Persisted per-user alert preferences and rules."""

    __tablename__ = "user_alert_preferences"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alerts_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=_default_dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_user_alert_preferences_updated_at", "updated_at"),)
