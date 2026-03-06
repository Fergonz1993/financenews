"""Unit tests for ingestion type contracts and validation helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from financial_news.services.ingest_types import (
    ArticleIngestRecord,
    SourceHealthRecord,
    validate_connector_items,
)


def test_article_ingest_record_from_payload_coerces_minimum_fields() -> None:
    payload = {
        "source": "GDELT",
        "title": "Stocks rally on softer CPI",
        "url": "https://example.com/stocks-rally",
        "published_at": "2026-02-28T10:00:00Z",
        "topics": "Markets",
    }
    record = ArticleIngestRecord.model_validate(payload)

    assert record.title == "Stocks rally on softer CPI"
    assert record.source == "GDELT"
    assert record.published_at.tzinfo is not None
    assert isinstance(record.topics, list)


def test_validate_connector_items_rejects_invalid_payloads() -> None:
    valid = {
        "id": "ok-1",
        "source": "Demo",
        "title": "Fed minutes released",
        "url": "https://example.com/fed-minutes",
        "source_id": 7,
        "published_at": datetime.now(UTC),
    }
    invalid_missing_title = {
        "id": "bad-1",
        "url": "https://example.com/bad",
        "source": "Demo",
    }
    invalid_missing_url = {
        "id": "bad-2",
        "title": "Missing URL",
        "source": "Demo",
    }

    normalized, errors = validate_connector_items("gdelt", [valid, invalid_missing_title, invalid_missing_url])

    assert len(normalized) == 1
    assert normalized[0]["source_id"] == 7
    assert len(errors) == 2
    assert errors[0]["error_code"] in {"invalid_title", "invalid_url", "validation_error"}


def test_source_health_record_as_dict_shape() -> None:
    health = SourceHealthRecord(
        source_key="connector-gdelt",
        state="ready",
        last_fetch_at="2026-02-28T12:00:00+00:00",
        last_articles_fetched=10,
        last_articles_validated=9,
        last_articles_rejected=1,
        last_articles_stored=7,
        last_fetch_latency_ms=88,
        last_error_code=None,
        last_error=None,
    )

    payload = health.model_dump()
    assert payload["source_key"] == "connector-gdelt"
    assert payload["state"] == "ready"
    assert payload["last_articles_validated"] == 9
