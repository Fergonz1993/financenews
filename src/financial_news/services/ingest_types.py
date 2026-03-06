"""Typed ingestion contracts used across connectors, runner, and API status."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

ConnectorState = Literal["ready", "degraded", "error", "disabled"]


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        raw = value.strip()
        if raw:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                pass
    return datetime.now(UTC)


def _coerce_opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _validation_error_code(message: str) -> str:
    normalized = message.lower()
    if "title" in normalized:
        return "invalid_title"
    if "url" in normalized:
        return "invalid_url"
    if "source" in normalized:
        return "invalid_source"
    return "validation_error"


@dataclass(slots=True)
class ArticleIngestRecord:
    title: str
    url: str
    published_at: datetime
    source: str
    content: str = ""
    id: str | None = None
    source_name: str | None = None
    source_id: int | None = None
    source_item_id: str | None = None
    summarized_headline: str | None = None
    summary_bullets: list[str] = field(default_factory=list)
    sentiment: str | None = None
    sentiment_score: float | None = None
    market_impact_score: float | None = None
    key_entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> ArticleIngestRecord:
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(
        cls,
        payload: dict[str, Any],
        *,
        connector_name: str | None = None,
        source_id: int | None = None,
        default_source_id: int | None = None,
    ) -> ArticleIngestRecord:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")

        url = str(payload.get("url") or "").strip()
        if not url:
            raise ValueError("url is required")

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be absolute http(s)")

        resolved_source = str(
            payload.get("source") or payload.get("source_name") or connector_name or ""
        ).strip()
        if not resolved_source:
            raise ValueError("source is required")

        published_at = _coerce_datetime(payload.get("published_at"))
        resolved_source_id = payload.get("source_id")
        if not isinstance(resolved_source_id, int):
            resolved_source_id = source_id
        if not isinstance(resolved_source_id, int):
            resolved_source_id = default_source_id

        identifier = _coerce_opt_str(payload.get("id"))
        if not identifier:
            identifier = _hash(
                f"{resolved_source.lower()}|{url}|{published_at.isoformat()}|{title}"
            )

        return cls(
            id=identifier,
            source=resolved_source,
            source_name=_coerce_opt_str(payload.get("source_name")) or resolved_source,
            source_id=resolved_source_id,
            source_item_id=_coerce_opt_str(payload.get("source_item_id")),
            title=title,
            url=url,
            content=str(payload.get("content") or "").strip(),
            published_at=published_at,
            summarized_headline=_coerce_opt_str(payload.get("summarized_headline")),
            summary_bullets=_coerce_list(payload.get("summary_bullets")),
            sentiment=_coerce_opt_str(payload.get("sentiment")),
            sentiment_score=_coerce_opt_float(payload.get("sentiment_score")),
            market_impact_score=_coerce_opt_float(payload.get("market_impact_score")),
            key_entities=_coerce_list(payload.get("key_entities")),
            topics=_coerce_list(payload.get("topics")),
        )

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        connector_name: str,
        source_id: int | None = None,
    ) -> ArticleIngestRecord:
        return cls.from_mapping(payload, connector_name=connector_name, source_id=source_id)

    def model_dump(self) -> dict[str, Any]:
        return self.as_storage_payload()

    def as_storage_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "source_item_id": self.source_item_id,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "published_at": self.published_at,
            "summarized_headline": self.summarized_headline,
            "summary_bullets": self.summary_bullets,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "market_impact_score": self.market_impact_score,
            "key_entities": self.key_entities,
            "topics": self.topics,
        }

    def to_repository_payload(self) -> dict[str, Any]:
        return self.as_storage_payload()


@dataclass(slots=True)
class SourceHealthRecord:
    state: ConnectorState
    source_key: str | None = None
    connector: str | None = None
    enabled: bool = True
    last_fetch_at: str | None = None
    last_success_at: str | None = None
    last_articles_fetched: int = 0
    last_articles_validated: int = 0
    last_articles_rejected: int = 0
    last_articles_stored: int = 0
    last_fetch_latency_ms: int | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    consecutive_failures: int = 0
    success_count_24h: int = 0
    error_count_24h: int = 0
    success_rate_24h: float = 1.0
    freshness_lag_seconds: int | None = None

    def __post_init__(self) -> None:
        source_key = _coerce_opt_str(self.source_key)
        connector = _coerce_opt_str(self.connector)

        if source_key is None and connector is not None:
            source_key = f"connector-{connector}"
        if connector is None and source_key is not None:
            connector = source_key.removeprefix("connector-")
        if source_key is None or connector is None:
            raise ValueError("source_key or connector is required")

        canonical_error_code = _coerce_opt_str(self.last_error_code) or _coerce_opt_str(
            self.error_code
        )
        canonical_error = _coerce_opt_str(self.last_error) or _coerce_opt_str(
            self.error_message
        )

        object.__setattr__(self, "source_key", source_key)
        object.__setattr__(self, "connector", connector)
        object.__setattr__(self, "last_error_code", canonical_error_code)
        object.__setattr__(self, "last_error", canonical_error)
        object.__setattr__(self, "error_code", canonical_error_code)
        object.__setattr__(self, "error_message", canonical_error)

    def model_dump(self) -> dict[str, Any]:
        payload = {
            "source_key": self.source_key,
            "connector": self.connector,
            "enabled": self.enabled,
            "state": self.state,
            "status": self.state,
            "last_fetch_at": self.last_fetch_at,
            "last_success_at": self.last_success_at,
            "last_articles_fetched": self.last_articles_fetched,
            "last_articles_validated": self.last_articles_validated,
            "last_articles_rejected": self.last_articles_rejected,
            "last_articles_stored": self.last_articles_stored,
            "last_fetch_latency_ms": self.last_fetch_latency_ms,
            "last_error_code": self.last_error_code,
            "last_error": self.last_error,
            "error_code": self.last_error_code,
            "error_message": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "success_count_24h": self.success_count_24h,
            "error_count_24h": self.error_count_24h,
            "success_rate_24h": self.success_rate_24h,
            "freshness_lag_seconds": self.freshness_lag_seconds,
        }
        return payload

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(slots=True)
class IngestRunSummary:
    run_id: str
    cycle: int
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    status: str
    articles_stored: int
    results: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return self.as_dict()

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "cycle": self.cycle,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
            "status": self.status,
            "articles_stored": self.articles_stored,
            "results": self.results,
            "error_code": self.error_code,
        }


def validate_connector_items(
    connector_name: str,
    items: list[dict[str, Any]],
    *,
    default_source_id: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate and normalize connector payloads."""

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        try:
            record = ArticleIngestRecord.from_mapping(
                item,
                connector_name=connector_name,
                default_source_id=default_source_id,
            )
        except ValueError as exc:
            message = str(exc)
            errors.append(
                {
                    "connector": connector_name,
                    "index": index,
                    "error": message,
                    "error_code": _validation_error_code(message),
                    "item_id": str(item.get("id") or ""),
                }
            )
            continue
        valid.append(record.as_storage_payload())

    return valid, errors
