"""Pydantic request and response models for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str
    summarized_headline: str | None = None
    summary_bullets: list[str] = Field(default_factory=list)
    sentiment: str | None = None
    sentiment_score: float | None = None
    market_impact_score: float | None = None
    key_entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    sentiment_distribution: dict[str, int]
    source_distribution: dict[str, int]
    top_entities: list[dict[str, int | str]]
    top_topics: list[dict[str, int | str]]
    processing_stats: dict[str, float]


class SourceUpsertRequest(BaseModel):
    id: str | None = None
    name: str
    url: str
    source_type: str = "rss"
    source_category: str | None = None
    connector_type: str | None = None
    crawl_interval_minutes: int = 30
    rate_limit_per_minute: int = 60
    enabled: bool = True
    terms_url: str | None = None
    legal_basis: str | None = None
    provider_domain: str | None = None
    rate_profile: str | None = None
    requires_api_key: bool = False
    requires_user_agent: bool = False
    user_agent: str | None = None
    retry_policy: dict[str, Any] | None = None
    parser_contract: dict[str, Any] | None = None


class SourceValidationRequest(BaseModel):
    source_url: str
    source_type: str = "rss"


class ConnectorToggleRequest(BaseModel):
    enabled: bool | None = None
    reset_override: bool = False


class DefaultFiltersPayload(BaseModel):
    sources: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    sentiment: str | None = None


class EmailAlertsPayload(BaseModel):
    enabled: bool = False
    frequency: str = Field(default="daily")
    keywords: list[str] = Field(default_factory=list)


class VisualizationPayload(BaseModel):
    chartType: str = "bar"
    colorScheme: str = "default"


class UserSettingsPayload(BaseModel):
    darkMode: bool = True
    autoRefresh: bool = False
    refreshInterval: int = Field(default=5, ge=1, le=3600)
    defaultFilters: DefaultFiltersPayload = Field(default_factory=DefaultFiltersPayload)
    emailAlerts: EmailAlertsPayload = Field(default_factory=EmailAlertsPayload)
    visualization: VisualizationPayload = Field(default_factory=VisualizationPayload)


class UserAlertRulePayload(BaseModel):
    id: str | None = None
    source: str | None = None
    sentiment: str | None = None
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True


class UserAlertsPayload(BaseModel):
    enabled: bool = False
    deliveryMode: str = "digest"
    rules: list[UserAlertRulePayload] = Field(default_factory=list)


class IngestTriggerRequest(BaseModel):
    source_filters: list[str] | str | None = None
    source_urls: list[str] | str | None = None
    source_ids: list[int] | str | None = None
    idempotency_key: str | None = None
    reason: str | None = None
