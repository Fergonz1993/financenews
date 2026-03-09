#!/usr/bin/env python3
"""Tests for news_ingest helper functions — raises backend coverage for critical helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import financial_news.services.news_ingest as ingest


# ---------------------------------------------------------------------------
# _canonicalize_url
# ---------------------------------------------------------------------------
class TestCanonicalizeUrl:
    def test_strips_utm_params(self) -> None:
        url = "https://ex.com/article?utm_source=twitter&id=42"
        result = ingest._canonicalize_url(url)
        assert "utm_source" not in result
        assert "id=42" in result

    def test_strips_tracking_clid(self) -> None:
        url = "https://ex.com/page?fbclid=abc123&real=yes"
        result = ingest._canonicalize_url(url)
        assert "fbclid" not in result
        assert "real=yes" in result

    def test_strips_fragment(self) -> None:
        result = ingest._canonicalize_url("https://ex.com/page#section")
        assert "#" not in result

    def test_empty_url(self) -> None:
        assert ingest._canonicalize_url("") == ""

    def test_trailing_slash_stripped(self) -> None:
        result = ingest._canonicalize_url("https://ex.com/page/")
        assert not result.endswith("/")


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------
class TestExtractEntities:
    def test_extracts_proper_nouns(self) -> None:
        text = "Federal Reserve Chair Jerome Powell spoke at the Goldman Sachs event."
        entities = ingest._extract_entities(text)
        # Should find multi-word proper nouns
        flat = " ".join(entities).lower()
        assert "federal reserve" in flat or "jerome powell" in flat or "goldman sachs" in flat

    def test_ignores_stop_words(self) -> None:
        text = "The Federal Reserve met on Thursday."
        entities = ingest._extract_entities(text)
        entity_lower = [e.lower() for e in entities]
        assert "the" not in entity_lower
        assert "thursday" not in entity_lower

    def test_ignores_noise_tokens(self) -> None:
        # Blocklisted tokens that match the entity regex (uppercase first letter)
        text = "AfY8Hf said DpimGf announced EP1ykd results"
        entities = ingest._extract_entities(text)
        blocked = {"AfY8Hf", "DpimGf", "EP1ykd"}
        assert not any(e in blocked for e in entities)

    def test_max_six_entities(self) -> None:
        text = " ".join(f"Entity{chr(65 + i)} Corp" for i in range(10))
        entities = ingest._extract_entities(text)
        assert len(entities) <= 6

    def test_empty_text(self) -> None:
        assert ingest._extract_entities("") == []


# ---------------------------------------------------------------------------
# _extract_topics
# ---------------------------------------------------------------------------
class TestExtractTopics:
    def test_detects_finance_topic(self) -> None:
        topics = ingest._extract_topics("The stock market saw heavy trading in financial instruments.")
        assert "Finance" in topics or "Markets" in topics

    def test_detects_ai_topic(self) -> None:
        topics = ingest._extract_topics("Artificial intelligence is transforming deep learning.")
        assert "AI" in topics

    def test_detects_policy(self) -> None:
        topics = ingest._extract_topics("The federal reserve raised the interest rate.")
        assert "Policy" in topics

    def test_detects_earnings(self) -> None:
        topics = ingest._extract_topics("Quarterly earnings beat revenue expectations with strong guidance.")
        assert "Earnings" in topics

    def test_detects_economy(self) -> None:
        topics = ingest._extract_topics("GDP growth exceeded estimates amid recession fears.")
        assert "Economy" in topics

    def test_default_to_markets(self) -> None:
        topics = ingest._extract_topics("The weather was nice today for a walk.")
        assert topics == ["Markets"]

    def test_max_three_topics(self) -> None:
        text = "Stock market earnings revenue federal reserve GDP economy artificial intelligence"
        topics = ingest._extract_topics(text)
        assert len(topics) <= 3


# ---------------------------------------------------------------------------
# _bullets_from_text
# ---------------------------------------------------------------------------
class TestBulletsFromText:
    def test_splits_on_sentence_boundaries(self) -> None:
        text = "First sentence about the Federal Reserve and its policy. Second sentence about market impacts and trading volumes. Third one about crypto."
        bullets = ingest._bullets_from_text(text)
        assert len(bullets) >= 2

    def test_max_three_bullets(self) -> None:
        text = ". ".join(f"Sentence number {i} with enough characters to pass the length filter" for i in range(10))
        bullets = ingest._bullets_from_text(text)
        assert len(bullets) <= 3

    def test_empty_text(self) -> None:
        assert ingest._bullets_from_text("") == []

    def test_filters_short_chunks(self) -> None:
        text = "Hi. This is a longer sentence about financial markets and their performance."
        bullets = ingest._bullets_from_text(text)
        # "Hi" should be filtered out
        assert all(len(b) > 24 for b in bullets)


# ---------------------------------------------------------------------------
# _normalize_title
# ---------------------------------------------------------------------------
class TestNormalizeTitle:
    def test_collapses_whitespace(self) -> None:
        assert ingest._normalize_title("  Federal   Reserve   ") == "Federal Reserve"

    def test_empty(self) -> None:
        assert ingest._normalize_title("") == ""


# ---------------------------------------------------------------------------
# _hash_value
# ---------------------------------------------------------------------------
class TestHashValue:
    def test_deterministic(self) -> None:
        assert ingest._hash_value("hello") == ingest._hash_value("hello")

    def test_case_insensitive(self) -> None:
        assert ingest._hash_value("Hello") == ingest._hash_value("hello")

    def test_strips_whitespace(self) -> None:
        assert ingest._hash_value("  hello  ") == ingest._hash_value("hello")


# ---------------------------------------------------------------------------
# _is_noise_entity_token
# ---------------------------------------------------------------------------
class TestIsNoiseEntityToken:
    def test_empty_is_noise(self) -> None:
        assert ingest._is_noise_entity_token("") is True

    def test_blocklisted_is_noise(self) -> None:
        assert ingest._is_noise_entity_token("AfY8Hf") is True
        assert ingest._is_noise_entity_token("Dftppe") is True

    def test_marker_is_noise(self) -> None:
        assert ingest._is_noise_entity_token("dotssplash-config") is True

    def test_normal_entity_not_noise(self) -> None:
        assert ingest._is_noise_entity_token("Goldman Sachs") is False
        assert ingest._is_noise_entity_token("Federal Reserve") is False

    def test_camelcase_fragment_is_noise(self) -> None:
        # Short alphanumeric mixed-case fragments like JS variable names
        assert ingest._is_noise_entity_token("FdrFJe") is True


# ---------------------------------------------------------------------------
# _looks_like_script_payload
# ---------------------------------------------------------------------------
class TestLooksLikeScriptPayload:
    def test_empty_not_script(self) -> None:
        assert ingest._looks_like_script_payload("") is False

    def test_detects_wiz_global(self) -> None:
        assert ingest._looks_like_script_payload("window.wiz_global_data = {}") is True

    def test_detects_dotssplash(self) -> None:
        assert ingest._looks_like_script_payload("/_/dotssplashui/thing") is True

    def test_normal_text_not_script(self) -> None:
        assert ingest._looks_like_script_payload("The Federal Reserve raised interest rates.") is False


# ---------------------------------------------------------------------------
# _is_google_news_wrapper_url
# ---------------------------------------------------------------------------
class TestIsGoogleNewsWrapperUrl:
    def test_positive(self) -> None:
        assert ingest._is_google_news_wrapper_url(
            "https://news.google.com/rss/articles/CBMiXmh0..."
        ) is True

    def test_negative(self) -> None:
        assert ingest._is_google_news_wrapper_url("https://example.com/article") is False

    def test_empty(self) -> None:
        assert ingest._is_google_news_wrapper_url("") is False


# ---------------------------------------------------------------------------
# _coerce_datetime
# ---------------------------------------------------------------------------
class TestCoerceDatetime:
    def test_passes_through_datetime(self) -> None:
        now = datetime.now(UTC)
        assert ingest._coerce_datetime(now) == now

    def test_parses_iso_string(self) -> None:
        result = ingest._coerce_datetime("2026-01-15T12:00:00Z")
        assert result.year == 2026
        assert result.month == 1

    def test_invalid_returns_now(self) -> None:
        result = ingest._coerce_datetime("not-a-date")
        assert isinstance(result, datetime)
        assert (datetime.now(UTC) - result).total_seconds() < 2

    def test_none_returns_now(self) -> None:
        result = ingest._coerce_datetime(None)
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# _coerce_int, _coerce_float, _coerce_list
# ---------------------------------------------------------------------------
class TestCoercions:
    def test_coerce_int_valid(self) -> None:
        assert ingest._coerce_int("42", 0) == 42

    def test_coerce_int_invalid(self) -> None:
        assert ingest._coerce_int("abc", 7) == 7

    def test_coerce_int_none(self) -> None:
        assert ingest._coerce_int(None, 5) == 5

    def test_coerce_int_negative_clamps_to_zero(self) -> None:
        assert ingest._coerce_int("-5", 0) == 0

    def test_coerce_float_valid(self) -> None:
        assert ingest._coerce_float("3.14") == pytest.approx(3.14)

    def test_coerce_float_none(self) -> None:
        assert ingest._coerce_float(None) is None

    def test_coerce_float_invalid(self) -> None:
        assert ingest._coerce_float("nope") is None

    def test_coerce_list_from_list(self) -> None:
        assert ingest._coerce_list(["a", "b"]) == ["a", "b"]

    def test_coerce_list_from_string(self) -> None:
        assert ingest._coerce_list("solo") == ["solo"]

    def test_coerce_list_empty(self) -> None:
        assert ingest._coerce_list(None) == []

    def test_coerce_list_max_items(self) -> None:
        values = [f"item{i}" for i in range(50)]
        result = ingest._coerce_list(values, max_items=5)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# _to_text / _extract_text
# ---------------------------------------------------------------------------
class TestTextExtraction:
    def test_to_text_string(self) -> None:
        assert ingest._to_text("hello") == "hello"

    def test_to_text_list_of_dicts(self) -> None:
        assert ingest._to_text([{"value": "content"}]) == "content"

    def test_to_text_empty(self) -> None:
        assert ingest._to_text("") == ""

    def test_extract_text_strips_html(self) -> None:
        assert "World" in ingest._extract_text("<b>World</b>")
        assert "<b>" not in ingest._extract_text("<b>World</b>")

    def test_extract_text_unescapes_entities(self) -> None:
        assert "&" in ingest._extract_text("AT&amp;T")


# ---------------------------------------------------------------------------
# _slugify_filter
# ---------------------------------------------------------------------------
class TestSlugifyFilter:
    def test_basic(self) -> None:
        assert ingest._slugify_filter("SEC Newsroom") == "sec-newsroom"

    def test_strips_special(self) -> None:
        result = ingest._slugify_filter("Financial Times / Markets")
        assert "/" not in result

    def test_empty(self) -> None:
        assert ingest._slugify_filter("") == ""


# ---------------------------------------------------------------------------
# _parse_bool, _coalesce_bool
# ---------------------------------------------------------------------------
class TestBoolParsing:
    def test_parse_bool_true_variants(self) -> None:
        for val in ("true", "yes", "1", "on", "TRUE", "Yes"):
            assert ingest._parse_bool(val) is True

    def test_parse_bool_false_variants(self) -> None:
        for val in ("false", "no", "0", "off"):
            assert ingest._parse_bool(val) is False

    def test_parse_bool_none(self) -> None:
        assert ingest._parse_bool(None, True) is True

    def test_coalesce_bool_same(self) -> None:
        assert ingest._coalesce_bool("true") is True
        assert ingest._coalesce_bool(None, True) is True


# ---------------------------------------------------------------------------
# _parse_published_time
# ---------------------------------------------------------------------------
class TestParsePublishedTime:
    def test_iso_string(self) -> None:
        result = ingest._parse_published_time({"published": "2026-01-15T12:00:00Z"})
        assert result.year == 2026

    def test_rfc2822(self) -> None:
        result = ingest._parse_published_time(
            {"published": "Wed, 15 Jan 2026 12:00:00 GMT"}
        )
        assert result.year == 2026

    def test_falls_back_to_updated(self) -> None:
        result = ingest._parse_published_time(
            {"updated": "2026-06-01T00:00:00Z"}
        )
        assert result.year == 2026

    def test_non_dict_returns_now(self) -> None:
        result = ingest._parse_published_time("not a dict")
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# SourceResult / IngestRunResult dataclasses
# ---------------------------------------------------------------------------
class TestResultDataclasses:
    def test_source_result_as_dict(self) -> None:
        sr = ingest.SourceResult(source_id=1, source_key="reuters", source_name="Reuters")
        d = sr.as_dict
        assert d["source_id"] == 1
        assert d["source_key"] == "reuters"
        assert d["status"] == "queued"

    def test_ingest_run_result_lifecycle(self) -> None:
        run = ingest.IngestRunResult(run_id="test-run", requested_sources=3)
        assert run.status == "running"
        assert run.duration_seconds >= 0

        run.finish("completed")
        assert run.status == "completed"
        assert run.finished_at is not None

        d = run.as_dict()
        assert d["run_id"] == "test-run"
        assert d["status"] == "completed"
        assert d["requested_sources"] == 3
