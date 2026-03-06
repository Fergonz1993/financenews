"""API helper behavior tests for filter parsing and payload normalization."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import financial_news.api.main as api_main


def test_parse_optional_datetime_param_accepts_iso_and_naive() -> None:
    parsed_z = api_main._parse_optional_datetime_param(
        "2026-02-28T00:00:00Z",
        param_name="published_since",
    )
    assert parsed_z == datetime(2026, 2, 28, 0, 0, tzinfo=UTC)

    parsed_naive = api_main._parse_optional_datetime_param(
        "2026-02-28T12:30:00",
        param_name="published_until",
    )
    assert parsed_naive == datetime(2026, 2, 28, 12, 30, tzinfo=UTC)


def test_parse_optional_datetime_param_rejects_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        api_main._parse_optional_datetime_param("not-a-date", param_name="published_since")
    assert exc.value.status_code == 400
    assert "published_since" in str(exc.value.detail)


def test_parse_datetime_falls_back_to_epoch() -> None:
    assert api_main._parse_datetime(None) == datetime(1970, 1, 1, tzinfo=UTC)
    assert api_main._parse_datetime("invalid") == datetime(1970, 1, 1, tzinfo=UTC)


def test_search_matches_article_in_topics_and_entities() -> None:
    article = {
        "title": "Market wrap",
        "content": "Large cap stocks were mixed.",
        "source": "Example",
        "topics": ["Capital Markets"],
        "key_entities": ["NVIDIA"],
    }
    assert api_main._search_matches_article(article, "capital markets")
    assert api_main._search_matches_article(article, "nvidia")
    assert not api_main._search_matches_article(article, "federal reserve")


def test_normalize_article_payload_coerces_types() -> None:
    payload = api_main._normalize_article_payload(
        {
            "id": 123,
            "title": "Rate Decision",
            "url": "https://example.com/rate",
            "source": "Reuters",
            "published_at": "2026-02-20T00:00:00Z",
            "summary_bullets": "single",
            "sentiment_score": "0.8",
            "market_impact_score": "0.55",
            "key_entities": "Federal Reserve",
            "topics": ["Policy"],
        }
    )

    assert payload["id"] == 123
    assert payload["summary_bullets"] == ["single"]
    assert payload["sentiment_score"] == 0.8
    assert payload["market_impact_score"] == 0.55
    assert payload["key_entities"] == ["Federal Reserve"]
    assert payload["topics"] == ["Policy"]


def test_source_key_from_request_prefers_id_then_name(monkeypatch: pytest.MonkeyPatch) -> None:
    request_with_id = api_main.SourceUpsertRequest(
        id="source-id",
        name="Name",
        url="https://example.com",
    )
    assert api_main._source_key_from_request(request_with_id) == "source-id"

    request_with_name = api_main.SourceUpsertRequest(
        id=None,
        name="SEC Feed",
        url="https://sec.gov/feed",
    )
    assert api_main._source_key_from_request(request_with_name) == "sec-feed"

    class _FakeUuid:
        hex = "1234567890abcdef"

    monkeypatch.setattr(api_main.uuid, "uuid4", lambda: _FakeUuid())
    request_empty = api_main.SourceUpsertRequest(
        id="",
        name="",
        url="https://example.com/fallback",
    )
    assert api_main._source_key_from_request(request_empty) == "source-12345678"


def test_validate_source_url_or_raise() -> None:
    api_main._validate_source_url_or_raise("https://example.com/feed")

    with pytest.raises(HTTPException) as exc:
        api_main._validate_source_url_or_raise("ftp://example.com")
    assert exc.value.status_code == 400
