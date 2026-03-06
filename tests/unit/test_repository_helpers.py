"""Repository helper tests for deterministic normalization behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from financial_news.storage import repositories as repo


def test_slugify_and_topic_match() -> None:
    assert repo._slugify("  Federal Reserve / Policy ") == "federal-reserve-policy"
    assert repo._topic_matches({"topics": ["Capital Markets", "AI"]}, "capital-markets")
    assert not repo._topic_matches({"topics": ["AI"]}, "policy")


def test_coerce_datetime_handles_iso_and_invalid_values() -> None:
    parsed = repo._coerce_datetime("2026-02-28T12:00:00Z")
    assert parsed == datetime(2026, 2, 28, 12, 0, tzinfo=UTC)

    before = datetime.now(UTC)
    fallback = repo._coerce_datetime("not-a-date")
    after = datetime.now(UTC)
    assert before <= fallback <= after


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    value = "https://Example.com/path/item/?utm_source=newsletter&v=1#section"
    assert repo._canonicalize_url(value) == "https://example.com/path/item/?v=1"


def test_collect_aliases_and_search_match() -> None:
    article = {
        "title": "Portfolio gains from machine learning investment",
        "content": "",
        "summarized_headline": "",
        "source": "Example",
        "topics": ["AI"],
        "key_entities": ["NVIDIA"],
    }
    aliases = repo._collect_aliases("ai")
    assert repo._search_match(article, aliases)


def test_extract_single_column_ignores_none() -> None:
    rows = [("a", 1), (None, 2), ("b", 3)]
    assert repo._extract_single_column(rows, 0) == {"a", "b"}


def test_normalize_for_db_generates_deterministic_hashes() -> None:
    item = {
        "title": "  Fed Signals   Rate Pause ",
        "source": "Reuters",
        "published_at": "2026-02-20T10:00:00Z",
        "url": "https://www.reuters.com/markets/fed?utm_source=mail&x=1",
        "summary_bullets": ["One", "Two"],
        "topics": ["Markets"],
    }

    normalized = repo.ArticleRepository._normalize_for_db(item)

    assert normalized is not None
    assert normalized["title"] == "Fed Signals Rate Pause"
    assert normalized["source_key"] == "reuters"
    assert normalized["url"] == "https://www.reuters.com/markets/fed?x=1"
    assert normalized["summary_bullets"] == ["One", "Two"]
    assert normalized["topics"] == ["Markets"]
    assert len(normalized["url_hash"]) == 64
    assert len(normalized["dedupe_key"]) == 64


def test_normalize_for_db_requires_non_empty_title() -> None:
    assert repo.ArticleRepository._normalize_for_db({"title": "   "}) is None


def test_ingest_result_initializes_errors_list() -> None:
    payload = repo.IngestResult()
    assert payload.errors == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("  Reuters  ", "Reuters"),
    ],
)
def test_coerce_opt_str(value: object, expected: str | None) -> None:
    assert repo._coerce_opt_str(value) == expected
