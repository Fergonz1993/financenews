"""Direct tests for shared normalization helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from financial_news.utils.normalization import (
    canonicalize_url,
    coerce_datetime_utc,
    coerce_string_list,
    normalize_search_text,
    slugify_value,
)


def test_coerce_string_list_strips_blanks_and_supports_tuples() -> None:
    assert coerce_string_list(("  Fed  ", "", "Rates ")) == ["Fed", "Rates"]
    assert coerce_string_list([" one ", " ", "two"], max_items=1) == ["one"]


def test_normalize_search_text_accepts_iterables() -> None:
    assert normalize_search_text(("Fed", "Rate Cut")) == "fed rate cut"


def test_canonicalize_url_removes_tracking_params_and_fragment() -> None:
    url = (
        "https://Example.com/path/item/?utm_source=newsletter&session=abc&v=1#headline"
    )
    assert canonicalize_url(url) == "https://example.com/path/item/?v=1"


def test_coerce_datetime_utc_uses_default_for_invalid_values() -> None:
    fallback = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    assert coerce_datetime_utc("not-a-date", default=fallback) == fallback


def test_slugify_value_returns_stable_slug() -> None:
    assert slugify_value("  Federal Reserve / Policy ") == "federal-reserve-policy"
