"""Strict typing boundaries for the ingestion layer.

Defines Pydantic models for validated connector output payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ParsedArticle(BaseModel):
    """Normalized, typed output from an ingestion connector."""

    id: str = Field(..., description="Unique deterministic hash ID for the article")
    source_name: str = Field(..., description="Name of the source")
    title: str = Field(..., description="Article title (cleaned)")
    url: str = Field(..., description="Canonical article URL")
    content: str = Field(..., description="Main content body or summary")
    published_at: datetime = Field(..., description="UTC publication time")
    
    source_id: int | None = Field(None, description="Database ID of the source")
    source_item_id: str | None = Field(None, description="Original item ID from the source")
    
    summarized_headline: str | None = Field(None, description="Short generated summary headline")
    summary_bullets: list[str] = Field(default_factory=list, description="Bullet point summary")
    
    sentiment: str | None = Field(None, description="'positive', 'negative', or 'neutral'")
    sentiment_score: float | None = Field(None, description="0.0 to 1.0 continuous sentiment score")
    market_impact_score: float | None = Field(None, description="0.0 to 1.0 expected market impact")
    
    key_entities: list[str] = Field(default_factory=list, description="Extracted ticker symbols or organizations")
    topics: list[str] = Field(default_factory=list, description="Categorical topics")
    
    relevance_precision: float | None = Field(None, description="Optional relevance confidence score")

    @field_validator("sentiment")
    @classmethod
    def _validate_sentiment(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in ("positive", "negative", "neutral"):
            return None
        return v

    @field_validator("sentiment_score", "market_impact_score", "relevance_precision")
    @classmethod
    def _validate_scores(cls, v: float | None) -> float | None:
        if v is None:
            return None
        # Clamp to 0.0 - 1.0 bounds loosely if needed, or just validate type
        return max(0.0, min(1.0, float(v)))

    @field_validator("key_entities", "topics", "summary_bullets")
    @classmethod
    def _validate_lists(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        return [str(item).strip() for item in v if str(item).strip()]

    def as_db_dict(self) -> dict[str, Any]:
        """Convert validated model into a dictionary suitable for db insertion."""
        return self.model_dump(exclude_none=False)
