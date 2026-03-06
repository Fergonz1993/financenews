"""API contract and admin-auth unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import financial_news.api.main as api_main


async def _empty_receive() -> dict[str, object]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _build_request(headers: dict[str, str] | None = None) -> Request:
    normalized = headers or {}
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/mock",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in normalized.items()
        ],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope, _empty_receive)


@pytest.mark.asyncio
async def test_articles_contract_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_main,
        "_load_articles_from_db",
        AsyncMock(
            return_value=[
                {
                    "id": "a1",
                    "title": "Test Article",
                    "url": "https://example.com/a1",
                    "source": "Example Source",
                    "published_at": "2026-02-28T00:00:00+00:00",
                    "summarized_headline": "Summary",
                    "summary_bullets": ["One", "Two"],
                    "sentiment": "neutral",
                    "sentiment_score": 0.5,
                    "market_impact_score": 0.2,
                    "key_entities": ["Federal Reserve"],
                    "topics": ["Markets"],
                }
            ]
        ),
    )

    payload = await api_main.get_articles(
        limit=1,
        offset=0,
        source=None,
        sentiment=None,
        topic=None,
        search=None,
        published_since=None,
        published_until=None,
        days=None,
        sort_by="date",
        sort_order="desc",
    )

    assert len(payload) == 1
    row = payload[0].model_dump()
    expected_keys = {
        "id",
        "title",
        "url",
        "source",
        "published_at",
        "summarized_headline",
        "summary_bullets",
        "sentiment",
        "sentiment_score",
        "market_impact_score",
        "key_entities",
        "topics",
    }
    assert expected_keys.issubset(row.keys())


@pytest.mark.asyncio
async def test_articles_relevance_v2_uses_ranked_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_main, "FEED_RANKING_V2_ENABLED", True)
    monkeypatch.setattr(
        api_main,
        "_load_ranked_articles_v2",
        AsyncMock(
            return_value=[
                {
                    "id": "ranked-1",
                    "title": "Ranked article",
                    "url": "https://example.com/ranked-1",
                    "source": "Rank Source",
                    "published_at": "2026-02-28T00:00:00+00:00",
                    "summarized_headline": None,
                    "summary_bullets": [],
                    "sentiment": "neutral",
                    "sentiment_score": 0.5,
                    "market_impact_score": 0.7,
                    "key_entities": ["AAPL"],
                    "topics": ["Markets"],
                }
            ]
        ),
    )

    payload = await api_main.get_articles(
        limit=1,
        offset=0,
        source=None,
        sentiment=None,
        topic=None,
        search=None,
        published_since=None,
        published_until=None,
        days=None,
        sort_by="relevance",
        sort_order="desc",
    )

    assert len(payload) == 1
    assert payload[0].id == "ranked-1"


@pytest.mark.asyncio
async def test_ingest_status_contract_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run = SimpleNamespace(as_dict=lambda: {"run_id": "run-1", "status": "completed"})

    monkeypatch.setattr(api_main.ingester, "get_last_run", AsyncMock(return_value=fake_run))
    monkeypatch.setattr(api_main.ingester, "count_articles", AsyncMock(return_value=42))
    monkeypatch.setattr(
        api_main.continuous_runner,
        "get_status",
        lambda: {"running": False, "connectors": {}},
    )

    payload = await api_main.get_ingest_status()

    assert payload["run_id"] == "run-1"
    assert payload["status"] == "completed"
    assert payload["stored_article_count"] == 42
    assert "scheduled_refresh_seconds" in payload
    assert "continuous_runner" in payload


def test_admin_auth_requires_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "secret")
    monkeypatch.setattr(api_main, "ADMIN_ALLOWED_ROLES", {"admin", "ops"})
    api_main._ADMIN_REQUEST_HISTORY.clear()

    req_missing = _build_request()
    with pytest.raises(HTTPException) as missing_exc:
        api_main._require_admin_access(req_missing)
    assert missing_exc.value.status_code == 401

    req_invalid = _build_request({"x-admin-key": "wrong", "x-admin-role": "admin"})
    with pytest.raises(HTTPException) as invalid_exc:
        api_main._require_admin_access(req_invalid)
    assert invalid_exc.value.status_code == 403

    req_valid = _build_request(
        {
            "x-admin-key": "secret",
            "x-admin-role": "admin",
            "x-admin-user": "ci-bot",
        }
    )
    actor = api_main._require_admin_access(req_valid)
    assert actor == "ci-bot"


def test_admin_auth_relaxed_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "ADMIN_API_KEY", "")
    api_main._ADMIN_REQUEST_HISTORY.clear()

    req = _build_request({"x-admin-actor": "local-dev"})
    actor = api_main._require_admin_access(req)
    assert actor == "local-dev"


def test_parse_optional_datetime_param_invalid_raises_http_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        api_main._parse_optional_datetime_param(
            "not-a-date",
            param_name="published_since",
        )

    assert exc_info.value.status_code == 400
    assert "Invalid published_since value" in str(exc_info.value.detail)


def test_search_match_helpers_cover_topics_entities_and_headline() -> None:
    article = {
        "title": "Macro Roundup",
        "content": "Central bank commentary",
        "summarized_headline": "Fed keeps rates unchanged",
        "source": "Example News",
        "topics": ["Policy", "Rates"],
        "key_entities": ["Federal Reserve"],
    }

    assert api_main._search_matches_article(article, "federal reserve")
    assert api_main._search_matches_article(article, "rates")
    assert not api_main._search_matches_article(article, "cryptocurrency")


def test_source_key_generation_and_url_validation() -> None:
    payload = api_main.SourceUpsertRequest(
        id=None,
        name="SEC Press Releases",
        url="https://www.sec.gov/news/pressreleases.rss",
    )
    key = api_main._source_key_from_request(payload)
    assert key == "sec-press-releases"

    api_main._validate_source_url_or_raise("https://example.com/feed")
    with pytest.raises(HTTPException):
        api_main._validate_source_url_or_raise("/relative/path")
