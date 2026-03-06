#!/usr/bin/env python3
"""News ingestion services with PostgreSQL-backed storage and resilience controls."""

from __future__ import annotations

import asyncio
import calendar
import hashlib
import html
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import aiohttp
import feedparser

from financial_news.core.sentiment import (
    analyze_article_sentiment,
    get_sentiment_analyzer,
)
from financial_news.core.summarizer import Article
from financial_news.storage import (
    ArticleRepository,
    IngestionRunRepository,
    IngestionStateRepository,
    SourceConfig,
    SourceRepository,
    get_session_factory,
    initialize_schema,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

DEFAULT_RSS_FEEDS: tuple[tuple[str, str], ...] = (
    # --- Major financial wire services ---
    ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    # --- Market-focused outlets ---
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("MarketWatch Markets", "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ("Investing.com", "https://www.investing.com/rss/news.rss"),
    ("Nasdaq News", "https://www.nasdaq.com/feed/rssoutbound?category=Markets"),
    # --- Broadsheet / macro ---
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("WSJ Business", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"),
    ("Financial Times", "https://www.ft.com/rss/home"),
    ("The Economist Finance", "https://www.economist.com/finance-and-economics/rss.xml"),
    ("Bloomberg via Google", "https://news.google.com/rss/search?q=site:bloomberg.com+finance&hl=en-US&gl=US&ceid=US:en"),
    # --- Google News aggregated queries ---
    (
        "Google News Finance",
        "https://news.google.com/rss/search?q=financial+news&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Google News Capital Markets",
        "https://news.google.com/rss/search?q=capital+markets&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Google News AI Finance",
        "https://news.google.com/rss/search?q=artificial+intelligence+finance+markets&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Google News Earnings",
        "https://news.google.com/rss/search?q=earnings+report+quarterly+results&hl=en-US&gl=US&ceid=US:en",
    ),
)
DEFAULT_SEC_RSS_FEEDS: tuple[tuple[str, str], ...] = (
    ("SEC Newsroom", "https://www.sec.gov/newsroom/press-releases/rss?output=atom"),
)

DEFAULT_MAX_ARTICLES_PER_SOURCE = 25
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_MIN_ENTRY_CONTENT_CHARS = 240
DEFAULT_MAX_FULL_TEXT_CHARS = 5000
DEFAULT_ENABLE_FULL_TEXT_FETCH = False
DEFAULT_BACKOFF_BASE_SECONDS = 15
DEFAULT_BACKOFF_MAX_SECONDS = 600
DEFAULT_DUALSETAL_BACKOFF_JITTER_MS = 250
DEFAULT_LEGACY_STORAGE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "ingested_articles.json"
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_P_TAG_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_FILTER_RE = re.compile(r"[^a-z0-9]+")
_GOOGLE_NEWS_WRAPPER_PATH = "/rss/articles/"
_SCRIPT_NOISE_MARKERS = (
    "window.wiz_global_data",
    "/_/dotssplashui",
    "boq_dotssplashserver",
    "setprefs?cs=",
)
_ENTITY_NOISE_MARKERS = (
    "wiz",
    "dotssplash",
    "boq",
    "setprefs",
)
_ENTITY_EXPLICIT_BLOCKLIST = {
    "AfY8Hf",
    "Dftppe",
    "DpimGf",
    "EP1ykd",
    "FL1an",
    "FdrFJe",
    "Fwhl2e",
    "Document Format Files",
    "EIN",
    "Filer",
    "Incorp",
}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_csv_feeds(raw: Any) -> list[tuple[str, str]]:
    if not raw:
        return []
    raw_value = str(raw).strip()
    if not raw_value:
        return []

    entries: list[tuple[str, str]] = []
    for value in raw_value.split(","):
        item = value.strip()
        if not item:
            continue
        parsed = urlparse(item)
        entries.append((parsed.netloc or "Custom feed", item))
    return entries


def _dedup_feeds(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for name, url in items:
        canonical = url.strip()
        if canonical in seen:
            continue
        seen.add(canonical)
        deduped.append((name.strip(), canonical))
    return deduped


def _env_or_default_sources() -> list[tuple[str, str]]:
    user_feeds = _coerce_csv_feeds(os.getenv("NEWS_INGEST_FEEDS"))
    if user_feeds:
        sec_feeds = _coerce_csv_feeds(os.getenv("SEC_PRESS_RELEASE_FEEDS"))
        if sec_feeds:
            return _dedup_feeds(list(sec_feeds) + list(user_feeds))
        return _dedup_feeds(list(DEFAULT_SEC_RSS_FEEDS) + list(user_feeds))

    sec_feeds = _coerce_csv_feeds(os.getenv("SEC_PRESS_RELEASE_FEEDS"))
    if sec_feeds:
        return _dedup_feeds(list(sec_feeds) + list(DEFAULT_RSS_FEEDS))
    return _dedup_feeds(list(DEFAULT_SEC_RSS_FEEDS) + list(DEFAULT_RSS_FEEDS))


def _infer_source_category(source_name: str, source_url: str, source_type: str) -> str:
    lowered_name = str(source_name).lower()
    lowered_url = str(source_url).lower()
    if source_type == "sec" or "sec.gov" in lowered_url:
        return "regulatory"
    if "federalreserve" in lowered_url or "federal reserve" in lowered_name:
        return "policy"
    if "blog" in lowered_url or "medium.com" in lowered_url or "substack.com" in lowered_url:
        return "research"
    if "google.com" in lowered_url:
        return "aggregator"
    return "news"


def _infer_source_metadata(source_name: str, source_url: str, source_type: str) -> dict[str, Any]:
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    source_category = _infer_source_category(source_name, source_url, source_type)
    requires_user_agent = source_type == "sec" or "sec.gov" in host

    terms_url = None
    if host == "www.sec.gov" or host.endswith(".sec.gov"):
        terms_url = "https://www.sec.gov/os/accessing-edgar-data"

    rate_profile = "standard"
    if source_type == "sec":
        rate_profile = "sec-conservative"
    elif source_category == "aggregator":
        rate_profile = "feed-light"

    legal_basis = "public_web_feed"
    if source_type == "sec":
        legal_basis = "public_regulatory_disclosure"

    return {
        "source_category": source_category,
        "connector_type": source_type,
        "terms_url": terms_url,
        "legal_basis": legal_basis,
        "provider_domain": host or None,
        "rate_profile": rate_profile,
        "requires_api_key": False,
        "requires_user_agent": requires_user_agent,
    }


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _slugify_filter(value: str) -> str:
    return _FILTER_RE.sub("-", str(value).strip().lower()).strip("-")


def _canonicalize_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
    cleaned_query = "&".join(
        [
            f"{name}={value}"
            for name, value in query_pairs
            if not name.lower().startswith(("utm_", "ref_", "source", "session"))
            and not name.lower().endswith("clid")
        ]
    )
    rebuilt = parsed._replace(query=cleaned_query, fragment="")
    canonical = urlunparse(rebuilt).rstrip("/")
    return canonical


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return datetime.now(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


def _parse_published_time(entry: Any) -> datetime:
    if not isinstance(entry, dict):
        return datetime.now(UTC)
    published_parsed = entry.get("published_parsed")
    candidate = entry.get("published")
    if candidate and isinstance(candidate, str):
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed
    if isinstance(published_parsed, tuple):
        try:
            return datetime.fromtimestamp(calendar.timegm(published_parsed), tz=UTC)
        except (TypeError, ValueError):
            pass
    updated = entry.get("updated")
    if updated and isinstance(updated, str):
        parsed = _parse_datetime(updated)
        if parsed is not None:
            return parsed
    return datetime.now(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            return None


def _coalesce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any, *, max_items: int = 20) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return values[:max_items]
    return [str(value).strip()] if str(value).strip() else []


def _to_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list) and value:
        first = value[0]
        value = first.get("value", "") if isinstance(first, dict) else str(first)
    return str(value).strip()


def _extract_text(value: Any) -> str:
    if not value:
        return ""
    text = _to_text(value)
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(text))).strip()


def _is_google_news_wrapper_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    return host.endswith("news.google.com") and parsed.path.startswith(_GOOGLE_NEWS_WRAPPER_PATH)


def _looks_like_script_payload(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    marker_hits = sum(1 for marker in _SCRIPT_NOISE_MARKERS if marker in lowered)
    return marker_hits >= 1


def _is_noise_entity_token(candidate: str) -> bool:
    token = candidate.strip()
    if not token:
        return True
    if token in _ENTITY_EXPLICIT_BLOCKLIST:
        return True

    lowered = token.lower()
    if any(marker in lowered for marker in _ENTITY_NOISE_MARKERS):
        return True

    # Script/config keys tend to be short alphanumeric mixed-case fragments (e.g., AfY8Hf).
    if " " not in token and token.isalnum() and 5 <= len(token) <= 12:
        has_upper_after_first = any(char.isupper() for char in token[1:])
        has_lower_after_first = any(char.islower() for char in token[1:])
        if has_upper_after_first and has_lower_after_first:
            return True

    return False


def _extract_entities(text: str) -> list[str]:
    if not text:
        return []
    matches = re.findall(r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,2}\b", text)
    stop_words = {
        "The",
        "This",
        "There",
        "Your",
        "About",
        "After",
        "Since",
        "That",
        "But",
        "Friday",
        "Thursday",
        "Wednesday",
        "Tuesday",
        "Monday",
        "State",
    }
    items: list[str] = []
    seen: set[str] = set()
    for token in matches:
        candidate = token.strip()
        if candidate in stop_words or len(candidate) < 3 or _is_noise_entity_token(candidate):
            continue
        normalized = candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(candidate)
        if len(items) >= 6:
            break
    return items


def _extract_topics(text: str) -> list[str]:
    lowered = text.lower()
    mapping = {
        "Finance": ["finance", "financial", "funds", "stock", "stocks", "market", "inflation"],
        "Capital Markets": [
            "capital markets",
            "capital market",
            "debt market",
            "fixed income",
            "equity market",
            "bond market",
            "ipo",
            "initial public offering",
        ],
        "AI": [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "generative ai",
            "large language model",
        ],
        "Earnings": ["earnings", "revenue", "profit", "profitability", "guidance"],
        "Policy": ["fed", "federal reserve", "interest rate", "inflation", "policy", "regulation"],
        "Markets": ["market", "equity", "stock", "exchange", "dow", "nasdaq", "sp500", "s&p"],
        "Economy": ["economy", "gdp", "recession", "growth", "unemployment"],
    }
    topics: list[str] = []
    for topic, needles in mapping.items():
        if any(term in lowered for term in needles):
            topics.append(topic)
    return topics[:3] if topics else ["Markets"]


def _bullets_from_text(text: str) -> list[str]:
    if not text:
        return []
    normalized = _WS_RE.sub(" ", text).strip()
    chunks = re.split(r"[.!?]", normalized)
    bullets = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 24]
    return bullets[:3]


def _normalize_title(value: str) -> str:
    return " ".join((value or "").split())


def _hash_value(value: str) -> str:
    normalized = (value or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _elapsed_ms(start_at: datetime) -> int:
    return int((datetime.now(UTC) - start_at).total_seconds() * 1000)


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normalize_source_url(url: str) -> str:
    parsed = urlparse(url)
    canonical = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return canonical.rstrip("/")


def _build_source_url(source_url: str, *, supports_since: bool, cursor_value: str | None) -> str:
    if not supports_since or not cursor_value:
        return source_url

    parsed = urlparse(source_url)
    query = dict(parse_qsl(parsed.query))
    query["from"] = cursor_value
    rebuilt = parsed._replace(query=urlencode(query, doseq=True))
    return urlunparse(rebuilt)


def _dedupe_hashes(article_id: str | None, url_hash: str, dedupe_key: str) -> tuple[str, str, str]:
    item_id = article_id or _hash_value(f"{url_hash}|{dedupe_key}")
    return item_id, url_hash, dedupe_key


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


@dataclass(slots=True)
class SourceResult:
    source_id: int
    source_key: str
    source_name: str
    status: str = "queued"
    items_seen: int = 0
    items_stored: int = 0
    items_skipped: int = 0
    error: str | None = None
    latency_ms: int = 0
    latest_cursor: str | None = None

    @property
    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_key": self.source_key,
            "source_name": self.source_name,
            "status": self.status,
            "items_seen": self.items_seen,
            "items_stored": self.items_stored,
            "items_skipped": self.items_skipped,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "latest_cursor": self.latest_cursor,
        }


@dataclass(slots=True)
class IngestRunResult:
    run_id: str
    requested_sources: int
    status: str = "running"
    sources_processed: int = 0
    items_seen: int = 0
    items_stored: int = 0
    items_skipped: int = 0
    failed_sources: int = 0
    source_errors: int = 0
    errors: list[str] = field(default_factory=list)
    source_results: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        finished = self.finished_at or datetime.now(UTC)
        return (finished - self.started_at).total_seconds()

    def finish(self, status: str) -> None:
        self.status = status
        self.finished_at = datetime.now(UTC)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "requested_sources": self.requested_sources,
            "sources_processed": self.sources_processed,
            "items_seen": self.items_seen,
            "items_stored": self.items_stored,
            "items_skipped": self.items_skipped,
            "failed_sources": self.failed_sources,
            "source_errors": self.source_errors,
            "errors": self.errors,
            "source_results": self.source_results,
            "started_at": self.started_at.isoformat(),
            "finished_at": (self.finished_at or datetime.now(UTC)).isoformat(),
            "duration_seconds": self.duration_seconds,
        }


class NewsIngestor:
    """Async source ingestor with source-level backoff and checkpoint state."""

    def __init__(
        self,
        max_items_per_source: int = DEFAULT_MAX_ARTICLES_PER_SOURCE,
        request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        enable_full_text_fetch: bool | None = None,
        min_entry_content_chars: int = DEFAULT_MIN_ENTRY_CONTENT_CHARS,
        max_full_text_chars: int = DEFAULT_MAX_FULL_TEXT_CHARS,
        legacy_json_path: Path | str | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        if session_factory is None:
            session_factory = get_session_factory()

        self._article_repo = ArticleRepository(session_factory=session_factory)
        self._source_repo = SourceRepository(session_factory=session_factory)
        self._state_repo = IngestionStateRepository(session_factory=session_factory)
        self._run_repo = IngestionRunRepository(session_factory=session_factory)
        self._analyzer = get_sentiment_analyzer()
        self._run_lock = asyncio.Lock()
        self._run_tasks: dict[str, asyncio.Task[IngestRunResult]] = {}
        self._max_items_per_source = max_items_per_source
        self._request_timeout_seconds = request_timeout_seconds
        self._min_entry_content_chars = max(1, min_entry_content_chars)
        self._full_text_max_chars = max(1200, max_full_text_chars)
        self._enable_full_text_fetch = _env_flag(
            "NEWS_INGEST_ENABLE_FULL_TEXT_FETCH",
            default=DEFAULT_ENABLE_FULL_TEXT_FETCH
            if enable_full_text_fetch is None
            else enable_full_text_fetch,
        )
        self._dual_write_legacy = (
            _coalesce_bool(os.getenv("LEGACY_INGEST_FALLBACK", "0"), False)
            and os.getenv("ENVIRONMENT", "development").strip().lower() != "production"
        )
        self._legacy_storage_path = Path(
            legacy_json_path
            or os.getenv("LEGACY_ARTICLES_PATH")
            or str(DEFAULT_LEGACY_STORAGE_PATH)
        )
        self._last_run = IngestRunResult(run_id="init", requested_sources=0, status="initialized")
        self._last_run.finish("stopped")
        self._legacy_storage_path.parent.mkdir(parents=True, exist_ok=True)

    async def run_ingest(
        self,
        sources: list[tuple[str, str]] | None = None,
        source_filters: list[str] | None = None,
        source_ids: list[int] | None = None,
        run_id: str | None = None,
    ) -> IngestRunResult:
        async with self._run_lock:
            await initialize_schema()

            seed_configs = self._build_default_source_configs()
            active_sources = await self._source_repo.upsert_sources(seed_configs)
            active_sources = [source for source in active_sources if source.enabled]

            if source_ids:
                ids = set(source_ids)
                active_sources = [source for source in active_sources if source.id in ids]

            if sources is not None:
                requested = [
                    (name, url)
                    for name, url in sources
                    if name and url and urlparse(url).scheme
                ]
                if requested:
                    source_configs: list[SourceConfig] = []
                    for name, url in requested:
                        metadata = _infer_source_metadata(name, url, "rss")
                        source_configs.append(
                            SourceConfig(
                                source_key=f"manual-{_hash_value(url)[:12]}",
                                name=name,
                                url=url,
                                source_type="rss",
                                enabled=True,
                                crawl_interval_minutes=30,
                                source_category=metadata["source_category"],
                                connector_type="rss",
                                terms_url=metadata["terms_url"],
                                legal_basis=metadata["legal_basis"],
                                provider_domain=metadata["provider_domain"],
                                rate_profile=metadata["rate_profile"],
                                requires_api_key=False,
                                requires_user_agent=metadata["requires_user_agent"],
                            )
                        )
                    active_sources = await self._source_repo.upsert_sources(source_configs)
                else:
                    active_sources = []

            if source_filters:
                requested_keys = {_slugify_filter(value) for value in source_filters}
                active_sources = [
                    source
                    for source in active_sources
                    if _slugify_filter(source.source_key) in requested_keys
                    or _slugify_filter(source.name) in requested_keys
                ]

            run_id = run_id or uuid4().hex[:24]
            result = IngestRunResult(
                run_id=run_id,
                requested_sources=len(active_sources),
            )
            await self._run_repo.create_run(run_id, requested_sources=len(active_sources))

            source_tasks = [
                self._run_source(source, run_id=run_id)
                for source in active_sources
            ]
            source_results = await asyncio.gather(*source_tasks, return_exceptions=True)

            parsed: list[SourceResult] = []
            for source_result in source_results:
                if isinstance(source_result, SourceResult):
                    parsed.append(source_result)
                else:
                    parsed.append(
                        SourceResult(
                            source_id=0,
                            source_key="unknown",
                            source_name="unknown",
                            status="failed",
                            error=str(source_result),
                        )
                    )

            for source_result in parsed:
                result.source_results.append(source_result.as_dict)
                result.items_seen += source_result.items_seen
                result.items_stored += source_result.items_stored
                result.items_skipped += source_result.items_skipped
                if source_result.status in {"failed", "skipped", "error"}:
                    result.failed_sources += 1
                if source_result.error:
                    result.errors.append(source_result.error)
                    result.source_errors += 1

            result.sources_processed = len(parsed)
            status = "completed" if result.failed_sources == 0 else "partial"
            result.finish(status)

            await self._run_repo.finish_run(
                run_id=result.run_id,
                items_seen=result.items_seen,
                items_stored=result.items_stored,
                items_skipped=result.items_skipped,
                failed_sources=result.failed_sources,
                source_errors=result.source_errors,
                error_summary=result.errors,
                source_results=result.source_results,
                status=result.status,
            )

            self._last_run = result

        if self._dual_write_legacy and result.requested_sources > 0:
            await self._write_legacy_store()

        return result

    def _build_default_source_configs(self) -> list[SourceConfig]:
        parser_contract = {
            "supports_since": False,
        }
        retry_policy = {
            "base_delay_seconds": DEFAULT_BACKOFF_BASE_SECONDS,
            "max_delay_seconds": DEFAULT_BACKOFF_MAX_SECONDS,
            "max_attempts": 3,
            "jitter_ms": DEFAULT_DUALSETAL_BACKOFF_JITTER_MS,
        }

        crawl_interval_minutes = max(
            1,
            _coerce_int(
                os.getenv("NEWS_INGEST_CRAWL_INTERVAL_MINUTES"),
                30,
            ),
        )
        rate_limit_per_minute = max(
            1,
            _coerce_int(
                os.getenv("NEWS_INGEST_RATE_LIMIT_PER_MINUTE"),
                60,
            ),
        )

        configs: list[SourceConfig] = []
        default_user_agent = os.getenv(
            "NEWS_INGEST_USER_AGENT",
            "finnews-ingest/1.0 (+https://example.com/finnews)",
        )
        for name, source_url in _env_or_default_sources():
            source_key = _slugify_filter(name)
            if not source_key:
                source_key = _slugify_filter(_normalize_source_url(source_url))

            parsed_source_url = urlparse(source_url)
            parsed_host = parsed_source_url.netloc.lower()
            source_type = "sec" if "sec.gov" in parsed_host else "rss"
            metadata = _infer_source_metadata(name, source_url, source_type)
            contract: dict[str, Any] = dict(parser_contract)
            if source_type == "sec":
                contract.update(
                    {
                        "supports_since": True,
                        "supports_after": True,
                        "since_param": "from",
                    }
                )

            configs.append(
                SourceConfig(
                    source_key=source_key,
                    name=name,
                    url=source_url,
                    source_type=source_type,
                    source_category=metadata["source_category"],
                    connector_type=metadata["connector_type"],
                    terms_url=metadata["terms_url"],
                    legal_basis=metadata["legal_basis"],
                    provider_domain=metadata["provider_domain"],
                    rate_profile=metadata["rate_profile"],
                    requires_api_key=metadata["requires_api_key"],
                    requires_user_agent=metadata["requires_user_agent"],
                    user_agent=default_user_agent if metadata["requires_user_agent"] else None,
                    enabled=None,
                    crawl_interval_minutes=crawl_interval_minutes,
                    rate_limit_per_minute=rate_limit_per_minute,
                    retry_policy=retry_policy,
                    parser_contract=contract,
                )
            )

        return configs

    async def start_async_ingest(
        self,
        *,
        sources: list[tuple[str, str]] | None = None,
        source_filters: list[str] | None = None,
        source_ids: list[int] | None = None,
    ) -> str:
        if self._run_lock.locked():
            raise RuntimeError("Ingestion already running")
        await initialize_schema()
        run_id = uuid4().hex[:24]
        task = asyncio.create_task(
            self.run_ingest(
                sources=sources,
                source_filters=source_filters,
                source_ids=source_ids,
                run_id=run_id,
            )
        )
        self._run_tasks[run_id] = task
        task.add_done_callback(self._on_run_complete)
        return run_id

    def is_running(self) -> bool:
        return self._run_lock.locked()

    def active_run_ids(self) -> list[str]:
        return list(self._run_tasks.keys())

    def _on_run_complete(self, task: asyncio.Task[IngestRunResult]) -> None:
        run_id = None
        for key, value in list(self._run_tasks.items()):
            if value is task:
                run_id = key
                break
        if run_id is not None:
            self._run_tasks.pop(run_id, None)
        try:
            task.result()
        except Exception as exc:
            logger.warning("Ingest background task failed run_id=%s err=%s", run_id, exc)

    async def _run_source(self, source: Any, run_id: str) -> SourceResult:
        if not source.id:
            return SourceResult(
                source_id=0,
                source_key=getattr(source, "source_key", "unknown"),
                source_name=getattr(source, "name", "Unknown"),
                status="failed",
                error="Source row not persisted",
            )

        result = SourceResult(
            source_id=source.id,
            source_key=source.source_key,
            source_name=source.name,
        )

        if not source.enabled:
            result.status = "skipped"
            result.error = "Source is disabled"
            return result

        state = await self._state_repo.get_for_source(source.id)
        now = datetime.now(UTC)
        if (
            state
            and state.disabled_by_failure
            and state.next_retry_at
            and state.next_retry_at > now
        ):
            result.status = "skipped"
            result.error = "Source paused by backoff"
            return result

        source_start = datetime.now(UTC)
        configured_user_agent = str(
            getattr(source, "user_agent", None)
            or os.getenv(
                "NEWS_INGEST_USER_AGENT",
                "finnews-ingest/1.0 (+https://example.com/finnews)",
            )
        )
        headers: dict[str, str] = {"User-Agent": configured_user_agent}
        parser_contract = source.parser_contract_json or {}
        if getattr(source, "requires_api_key", False):
            api_key_env = str(parser_contract.get("api_key_env") or "").strip()
            if api_key_env and not os.getenv(api_key_env):
                raise RuntimeError(
                    f"Source requires API key env var `{api_key_env}` but it is not configured"
                )
        if getattr(source, "requires_user_agent", False) and not configured_user_agent:
            raise RuntimeError("Source requires explicit user-agent configuration")

        retry_policy = source.retry_policy_json or {}
        base_delay = _coerce_int(
            retry_policy.get("base_delay_seconds"),
            DEFAULT_BACKOFF_BASE_SECONDS,
        )
        max_delay = _coerce_int(
            retry_policy.get("max_delay_seconds"),
            DEFAULT_BACKOFF_MAX_SECONDS,
        )

        if state and state.etag:
            headers["If-None-Match"] = state.etag

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._request_timeout_seconds),
                headers=headers,
            ) as session:
                parsed_items, etag = await self._fetch_and_parse_source(
                    session=session,
                    source=source,
                    state=state,
                    parser_contract=parser_contract,
                )
                result.items_seen = len(parsed_items)
                result.latest_cursor = None
                if parsed_items:
                    published_datetimes = [
                        published
                        for item in parsed_items
                        if isinstance((published := item.get("published_at")), datetime)
                    ]
                    if published_datetimes:
                        result.latest_cursor = max(published_datetimes).isoformat()

                write_result = await self._article_repo.upsert_deduplicated(
                    run_id=run_id,
                    items=parsed_items,
                )
                result.items_stored = write_result.items_stored
                result.items_skipped = write_result.items_skipped

                if write_result.items_stored or write_result.items_seen:
                    result.status = "stored" if write_result.items_stored > 0 else "completed_empty"
                else:
                    result.status = "completed_empty"

                latest = None
                if parsed_items:
                    dates = [
                        published
                        for item in parsed_items
                        if isinstance((published := item.get("published_at")), datetime)
                    ]
                    if dates:
                        latest = max(dates)
                cursor_value = (
                    latest.isoformat() if latest else (state.cursor_value if state else None)
                )
                await self._state_repo.mark_source_success(
                    source.id,
                    cursor_type="published_at",
                    cursor_value=cursor_value,
                    last_published_at=latest,
                    latency_ms=_elapsed_ms(source_start),
                    etag=etag,
                )
                result.latency_ms = _elapsed_ms(source_start)
                return result
        except Exception as exc:
            logger.exception("Source ingest failure source=%s", source.id)
            cursor_value = state.cursor_value if state else None
            await self._state_repo.mark_source_failure(
                source.id,
                error=str(exc),
                cursor_type="published_at",
                cursor_value=cursor_value,
                latency_ms=_elapsed_ms(source_start),
                base_delay_seconds=base_delay,
                max_delay_seconds=max_delay,
                jitter_ms=DEFAULT_DUALSETAL_BACKOFF_JITTER_MS,
            )
            result.status = "failed"
            result.error = str(exc)
            result.latency_ms = _elapsed_ms(source_start)
            return result

    async def _fetch_and_parse_source(
        self,
        *,
        session: aiohttp.ClientSession,
        source: Any,
        state: Any,
        parser_contract: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str | None]:
        supports_since = bool(parser_contract.get("supports_since", False))
        since_param = parser_contract.get("since_param") or "from"
        source_url = source.url
        cursor_value = state.cursor_value if state else None

        if supports_since and cursor_value:
            parsed = urlparse(source.url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query[since_param] = str(cursor_value)
            source_url = urlunparse(parsed._replace(query=urlencode(query)))

        feed_entries, etag = await _fetch_feed(
            session=session,
            source_url=source_url,
            source_name=source.name,
            max_entries=self._max_items_per_source,
        )

        cursor_dt = _coerce_datetime(cursor_value) if cursor_value else None
        parsed_items: list[dict[str, Any]] = []
        parser_failures = 0
        for entry in feed_entries:
            try:
                parsed = await _entry_to_record(
                    source_name=source.name,
                    entry=entry,
                    session=session,
                    source_id=source.id,
                    fetch_full_text=self._enable_full_text_fetch,
                    min_full_text_chars=self._min_entry_content_chars,
                    max_full_text_chars=self._full_text_max_chars,
                )
                if not parsed:
                    continue
                published = _parse_published_time(entry)
                if cursor_dt and published <= cursor_dt:
                    continue
                parsed["published_at"] = published
                parsed["source_id"] = source.id
                parsed_items.append(parsed)
                if len(parsed_items) >= self._max_items_per_source:
                    break
            except Exception as exc:
                parser_failures += 1
                if parser_failures <= 3:
                    logger.warning("Parser failure source=%s err=%s", source.id, exc)
                continue
        return parsed_items[: self._max_items_per_source], etag

    async def _write_legacy_store(self) -> None:
        articles = await self._article_repo.list_for_api(limit=self._max_items_per_source)
        payload = [dict(article) for article in articles]
        self._legacy_storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._legacy_storage_path.write_text(json_dumps(payload), encoding="utf-8")

    async def get_last_run(self) -> IngestRunResult:
        return self._last_run

    async def get_source_health(self) -> list[dict[str, Any]]:
        states = await self._state_repo.get_all()
        state_by_source_id = {state.source_id: state for state in states}
        sources = await self._source_repo.list_sources(enabled_only=False)
        health: list[dict[str, Any]] = []
        for source in sources:
            state = state_by_source_id.get(source.id)
            if state is None:
                health.append(
                    {
                        "source_id": source.id,
                        "source_key": source.source_key,
                        "source_name": source.name,
                        "source_type": source.source_type,
                        "source_category": getattr(source, "source_category", None),
                        "connector_type": getattr(source, "connector_type", None),
                        "provider_domain": getattr(source, "provider_domain", None),
                        "rate_profile": getattr(source, "rate_profile", None),
                        "requires_api_key": bool(
                            getattr(source, "requires_api_key", False)
                        ),
                        "requires_user_agent": bool(
                            getattr(source, "requires_user_agent", False)
                        ),
                        "cursor_type": None,
                        "cursor_value": None,
                        "last_success_at": None,
                        "consecutive_failures": 0,
                        "next_retry_at": None,
                        "last_latency_ms": None,
                        "last_failure_at": None,
                        "disabled_by_failure": False,
                        "last_error": None,
                        "updated_at": _iso_or_none(getattr(source, "updated_at", None)),
                    }
                )
                continue

            health.append(
                {
                    "source_id": source.id,
                    "source_key": source.source_key,
                    "source_name": source.name,
                    "source_type": source.source_type,
                    "source_category": getattr(source, "source_category", None),
                    "connector_type": getattr(source, "connector_type", None),
                    "provider_domain": getattr(source, "provider_domain", None),
                    "rate_profile": getattr(source, "rate_profile", None),
                    "requires_api_key": bool(
                        getattr(source, "requires_api_key", False)
                    ),
                    "requires_user_agent": bool(
                        getattr(source, "requires_user_agent", False)
                    ),
                    "cursor_type": state.cursor_type,
                    "cursor_value": state.cursor_value,
                    "last_success_at": _iso_or_none(state.last_success_at),
                    "consecutive_failures": state.consecutive_failures,
                    "next_retry_at": _iso_or_none(state.next_retry_at),
                    "last_latency_ms": state.last_latency_ms,
                    "last_failure_at": _iso_or_none(state.last_failure_at),
                    "disabled_by_failure": state.disabled_by_failure,
                    "last_error": state.last_error,
                    "updated_at": _iso_or_none(
                        state.last_success_at or state.last_failure_at
                    ),
                }
            )
        return health

    async def get_run(self, run_id: str) -> IngestRunResult | None:
        run = await self._run_repo.get(run_id)
        if run is None:
            return None
        payload = IngestRunResult(
            run_id=run.run_id,
            requested_sources=run.requested_sources,
            status=run.status,
        )
        payload.items_seen = run.items_seen
        payload.items_stored = run.items_stored
        payload.items_skipped = run.items_skipped
        payload.failed_sources = run.failed_sources
        payload.source_errors = run.source_errors
        payload.errors = run.error_summary or []
        payload.source_results = _normalize_json_list(run.source_results)
        payload.started_at = run.started_at or datetime.now(UTC)
        payload.finished_at = run.finished_at
        return payload

    async def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        # Lightweight compatibility helper.
        recent = self._last_run
        return [recent.as_dict()]

    async def run_status(self) -> IngestRunResult:
        return self._last_run

    async def count_articles(self) -> int:
        return await self._article_repo.count()

    async def get_sources(self) -> list[dict[str, Any]]:
        sources = await self._source_repo.list_sources(enabled_only=True)
        return [
            {
                "id": source.id,
                "source_key": source.source_key,
                "name": source.name,
                "enabled": source.enabled,
                "url": source.url,
                "source_type": source.source_type,
                "source_category": source.source_category,
                "connector_type": source.connector_type,
                "terms_url": source.terms_url,
                "legal_basis": source.legal_basis,
                "provider_domain": source.provider_domain,
                "rate_profile": source.rate_profile,
                "requires_api_key": source.requires_api_key,
                "requires_user_agent": source.requires_user_agent,
                "user_agent": source.user_agent,
                "crawl_interval_minutes": source.crawl_interval_minutes,
                "rate_limit_per_minute": source.rate_limit_per_minute,
            }
            for source in sources
        ]

    async def get_topics(self) -> list[str]:
        return await self._article_repo.get_topics_from_articles()

    async def get_articles(
        self,
        *,
        source: str | None = None,
        sentiment: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        published_since: datetime | None = None,
        published_until: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        return await self._article_repo.list_for_api(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=published_since,
            published_until=published_until,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def count_articles_for_filters(
        self,
        *,
        source: str | None = None,
        sentiment: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        published_since: datetime | None = None,
        published_until: datetime | None = None,
    ) -> int:
        return await self._article_repo.count_for_api(
            source=source,
            sentiment=sentiment,
            topic=topic,
            search=search,
            published_since=published_since,
            published_until=published_until,
        )

    async def get_article_payload(self, article_id: str) -> dict[str, Any] | None:
        article = await self._article_repo.get_by_id(article_id)
        if article is None:
            return None
        return self._article_repo._to_payload(article)

    def __hash__(self) -> int:
        return hash(id(self))


async def _entry_to_record(
    source_name: str,
    entry: Any,
    *,
    session: aiohttp.ClientSession | None = None,
    source_id: int | None = None,
    fetch_full_text: bool = False,
    min_full_text_chars: int = DEFAULT_MIN_ENTRY_CONTENT_CHARS,
    max_full_text_chars: int = DEFAULT_MAX_FULL_TEXT_CHARS,
) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None

    title = _normalize_title(str(entry.get("title") or "").strip())
    link = str(entry.get("link") or "").strip()
    if not title:
        return None

    source = str(source_name or "").strip() or "Unknown"
    published_at = _parse_published_time(entry)
    content = _extract_text(
        entry.get("summary") or entry.get("description") or entry.get("content") or ""
    )

    should_fetch_full_text = (
        fetch_full_text
        and session is not None
        and link
        and len(content) < min_full_text_chars
        and not _is_google_news_wrapper_url(link)
    )

    if should_fetch_full_text and session is not None:
        fallback = await _fetch_entry_full_text(
            session=session,
            source_url=link,
            max_full_text_chars=max_full_text_chars,
        )
        if fallback:
            content = fallback

    if _looks_like_script_payload(content):
        content = ""

    if not content:
        content = title

    article = Article(
        title=title,
        url=_canonicalize_url(link),
        source=source,
        published_at=published_at.isoformat(),
        content=content,
    )
    article.source_item_id = str(entry.get("id") or entry.get("guid") or link)
    article.summarized_headline = f"Summary: {title[:90]}" if title else None
    article.summary_bullets = [s.strip() for s in _bullets_from_text(content) if s.strip()][:3]
    sentiment = analyze_article_sentiment(f"{title} {content}")
    article.sentiment = sentiment.get("sentiment")
    article.sentiment_score = sentiment.get("sentiment_score")
    article.market_impact_score = min(
        1.0,
        abs((article.sentiment_score or 0.5) - 0.5) * 2,
    )
    article.key_entities = _extract_entities(f"{title} {content}")
    article.topics = _extract_topics(f"{title} {content}")
    article.processed_at = datetime.now(UTC)

    return {
        "id": article.id,
        "source": source,
        "source_name": source,
        "source_id": source_id,
        "source_item_id": article.source_item_id,
        "published_at": published_at,
        "title": article.title,
        "url": article.url,
        "content": article.content,
        "summarized_headline": article.summarized_headline,
        "summary_bullets": article.summary_bullets,
        "sentiment": article.sentiment,
        "sentiment_score": article.sentiment_score,
        "market_impact_score": article.market_impact_score,
        "key_entities": article.key_entities,
        "topics": article.topics,
    }


async def _fetch_feed(
    session: aiohttp.ClientSession,
    source_url: str,
    source_name: str,
    max_entries: int,
) -> tuple[list[Any], str | None]:
    async with session.get(source_url) as response:
        etag = response.headers.get("ETag")
        if response.status == 304:
            return [], etag
        if response.status != 200:
            raise RuntimeError(f"{source_name}: HTTP {response.status}")
        payload = await response.text()
        parsed = feedparser.parse(payload)
        if parsed.bozo:
            logger.warning("Feed parse warning source=%s", source_name)
        return list(parsed.entries)[: max_entries], etag


async def _fetch_entry_full_text(
    *,
    session: aiohttp.ClientSession,
    source_url: str,
    max_full_text_chars: int,
) -> str:
    try:
        response = await session.get(source_url)
        if response.status != 200:
            return ""
        payload = await response.text()
    except Exception:
        return ""

    paragraphs = _P_TAG_RE.findall(payload)
    if paragraphs:
        extracted = " ".join(_extract_text(paragraph) for paragraph in paragraphs)
    else:
        extracted = _extract_text(payload)
    return _WS_RE.sub(" ", extracted).strip()[:max_full_text_chars]


def _normalize_json_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []
