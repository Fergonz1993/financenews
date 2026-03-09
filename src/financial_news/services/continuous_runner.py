"""Continuous ingestion runner — background async loop for periodic news fetching.

Runs both the existing RSS/feed-based ingestion AND public source
connectors (GDELT, SEC EDGAR, Newsdata.io, optional Reddit) on a
configurable interval.

Environment variables:
    CONTINUOUS_INGEST_ENABLED           - "true" to enable (default: true)
    CONTINUOUS_INGEST_INTERVAL_SECONDS  - seconds between cycles (default: 300)
    GDELT_ENABLED                       - include GDELT connector (default: true)
    SEC_EDGAR_ENABLED                   - include SEC EDGAR connector (default: true)
    NEWSDATA_ENABLED                    - include Newsdata.io connector (default: true)
    REDDIT_ENABLED                      - include Reddit connector (default: false)
    STOCK_CORRELATION_ENABLED           - enrich connector results with stock correlation (default: false)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Literal, cast

from financial_news.config import get_settings
from financial_news.services.connectors.gdelt import GDELTConnector
from financial_news.services.connectors.newsdata import NewsdataConnector
from financial_news.services.connectors.reddit import RedditFinanceConnector
from financial_news.services.connectors.sec_edgar import SECEdgarConnector
from financial_news.services.feed_ranking import suppress_near_duplicates
from financial_news.services.ingest_types import (
    ArticleIngestRecord,
    IngestRunSummary,
    SourceHealthRecord,
    validate_connector_items,
)
from financial_news.services.stock_correlator import StockCorrelator
from financial_news.storage import (
    ArticleRepository,
    SourceConfig,
    SourceRepository,
    get_session_factory,
    initialize_schema,
)

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (ValueError, TypeError):
        return default


def _classify_error(error: Exception | str) -> str:
    message = str(error).lower()
    if "timeout" in message:
        return "timeout"
    if "429" in message or "rate limit" in message:
        return "rate_limited"
    if "connection" in message or "connect" in message:
        return "connection_error"
    if "auth" in message or "401" in message or "403" in message:
        return "authentication_error"
    if "validation" in message:
        return "validation_error"
    return "unknown_error"


class ContinuousIngestRunner:
    """Background async loop that periodically fetches news from all sources."""

    _CONNECTOR_FACTORIES: ClassVar[dict[str, tuple[str, type[Any]]]] = {
        "gdelt": ("GDELT Project", GDELTConnector),
        "sec_edgar": ("SEC EDGAR", SECEdgarConnector),
        "newsdata": ("Newsdata.io", NewsdataConnector),
        "reddit": ("Reddit Finance", RedditFinanceConnector),
    }

    def __init__(self, *, session_factory: Any | None = None) -> None:
        continuous_settings = get_settings().continuous_ingest
        self._session_factory = session_factory or get_session_factory()
        repo_session_factory = cast("Any", self._session_factory)
        self._article_repo = ArticleRepository(session_factory=repo_session_factory)
        self._source_repo = SourceRepository(session_factory=repo_session_factory)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._cycle_count = 0
        self._last_cycle_at: datetime | None = None
        self._last_cycle_articles: int = 0
        self._total_articles_ingested: int = 0
        self._errors: list[dict[str, Any]] = []
        self._connector_status: dict[str, dict[str, Any]] = {}
        self._connector_events: dict[str, list[dict[str, Any]]] | list[dict[str, Any]] = {
            key: [] for key in self._CONNECTOR_FACTORIES
        }
        self._connector_runtime_overrides: dict[str, bool] = {}

        # Configuration
        self.enabled = continuous_settings.enabled
        self.interval_seconds = max(1, continuous_settings.interval_seconds)

        # Backward-compatible flags used in tests and status responses.
        self.gdelt_enabled = continuous_settings.gdelt_enabled
        self.sec_edgar_enabled = continuous_settings.sec_edgar_enabled
        self.newsdata_enabled = continuous_settings.newsdata_enabled
        self.reddit_enabled = continuous_settings.reddit_enabled

        self._configured_connector_enabled: dict[str, bool] = {
            "gdelt": self.gdelt_enabled,
            "sec_edgar": self.sec_edgar_enabled,
            "newsdata": self.newsdata_enabled,
            "reddit": self.reddit_enabled,
        }

        self.stock_correlation_enabled = continuous_settings.stock_correlation_enabled
        self._stock_correlator_enabled = self.stock_correlation_enabled
        self._stock_correlator = (
            StockCorrelator() if self._stock_correlator_enabled else None
        )
        self._near_dedup_enabled = continuous_settings.near_dedup_enabled
        configured_threshold = continuous_settings.near_dedup_similarity_threshold
        self._near_dedup_similarity_threshold = max(
            0.5,
            min(0.99, configured_threshold),
        )

    @property
    def is_running(self) -> bool:
        return self._running

    def _is_connector_enabled(self, connector_name: str) -> bool:
        if connector_name in self._connector_runtime_overrides:
            return self._connector_runtime_overrides[connector_name]
        return self._configured_connector_enabled.get(connector_name, False)

    def _ensure_event_store(self) -> dict[str, list[dict[str, Any]]]:
        if isinstance(self._connector_events, dict):
            return self._connector_events

        migrated: dict[str, list[dict[str, Any]]] = {
            key: [] for key in self._CONNECTOR_FACTORIES
        }
        if isinstance(self._connector_events, list):
            for event in self._connector_events:
                connector = event.get("connector")
                if connector in migrated:
                    event_at = event.get("at")
                    migrated[connector].append(
                        {
                            "time": (
                                event.get("time")
                                or (
                                    event_at.isoformat()
                                    if isinstance(event_at, datetime)
                                    else None
                                )
                                or datetime.now(UTC).isoformat()
                            ),
                            "state": "ready" if event.get("ok", False) else "error",
                            "fetched": int(event.get("fetched", 0) or 0),
                            "validated": int(event.get("fetched", 0) or 0),
                            "rejected": 0,
                            "stored": int(event.get("stored", 0) or 0),
                            "latency_ms": int(event.get("latency_ms", 0) or 0),
                            "error_code": event.get("error_code"),
                            "success": bool(event.get("ok", False)),
                        }
                    )
        self._connector_events = migrated
        return migrated

    def _iter_connector_events(self, connector_name: str) -> list[dict[str, Any]]:
        events_by_connector = self._ensure_event_store()
        return events_by_connector.get(connector_name, [])

    def _build_connector_instances(self) -> list[tuple[str, Any]]:
        instances: list[tuple[str, Any]] = []
        for connector_name, (_, connector_factory) in self._CONNECTOR_FACTORIES.items():
            if not self._is_connector_enabled(connector_name):
                continue
            instances.append((connector_name, connector_factory()))
        return instances

    def set_connector_enabled(
        self,
        connector_name: str,
        enabled: bool,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        if connector_name not in self._CONNECTOR_FACTORIES:
            raise KeyError(connector_name)

        self._connector_runtime_overrides[connector_name] = bool(enabled)
        now = datetime.now(UTC)
        self._connector_status.setdefault(
            connector_name,
            SourceHealthRecord(
                source_key=f"connector-{connector_name}",
                enabled=bool(enabled),
                state="disabled" if not enabled else "ready",
                last_fetch_at=now.isoformat(),
            ).as_dict(),
        )
        self._connector_status[connector_name]["state"] = (
            "disabled" if not enabled else self._connector_status[connector_name].get("state", "ready")
        )
        return {
            "connector": connector_name,
            "configured_enabled": self._configured_connector_enabled.get(connector_name, False),
            "runtime_override": self._connector_runtime_overrides.get(connector_name),
            "effective_enabled": self._is_connector_enabled(connector_name),
            "actor": actor,
            "updated_at": now.isoformat(),
        }

    def clear_connector_override(
        self,
        connector_name: str,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        if connector_name not in self._CONNECTOR_FACTORIES:
            raise KeyError(connector_name)
        self._connector_runtime_overrides.pop(connector_name, None)
        return {
            "connector": connector_name,
            "configured_enabled": self._configured_connector_enabled.get(connector_name, False),
            "runtime_override": None,
            "effective_enabled": self._is_connector_enabled(connector_name),
            "actor": actor,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    def _record_connector_event(
        self,
        connector_name: str,
        *,
        state: str,
        fetched: int,
        validated: int,
        rejected: int,
        stored: int,
        latency_ms: int,
        error_code: str | None = None,
    ) -> None:
        events_by_connector = self._ensure_event_store()
        events = events_by_connector.setdefault(connector_name, [])
        now = datetime.now(UTC)
        events.append(
            {
                "time": now.isoformat(),
                "state": state,
                "fetched": fetched,
                "validated": validated,
                "rejected": rejected,
                "stored": stored,
                "latency_ms": latency_ms,
                "error_code": error_code,
                "success": state in {"ready", "degraded"},
            }
        )

        cutoff = now - timedelta(hours=24)
        events_by_connector[connector_name] = [
            item
            for item in events[-1000:]
            if datetime.fromisoformat(item["time"]) >= cutoff
        ]

    def _build_connector_slo(self, connector_name: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=24)

        events = [
            item
            for item in self._iter_connector_events(connector_name)
            if datetime.fromisoformat(item["time"]) >= cutoff
        ]

        if not events:
            return {
                "window_hours": 24,
                "events": 0,
                "success_rate_pct": None,
                "avg_latency_ms": None,
                "articles_stored": 0,
                "freshness_lag_seconds": None,
            }

        success_events = [item for item in events if item.get("success")]
        latencies = [item["latency_ms"] for item in events if item.get("latency_ms") is not None]
        stored_total = sum(int(item.get("stored", 0) or 0) for item in events)

        status = self._connector_status.get(connector_name, {})
        last_success_at_raw = status.get("last_success_at")
        freshness_lag_seconds: int | None = None
        if isinstance(last_success_at_raw, str):
            try:
                freshness_lag_seconds = int(
                    (now - datetime.fromisoformat(last_success_at_raw)).total_seconds()
                )
            except Exception:  # pragma: no cover - defensive
                freshness_lag_seconds = None

        return {
            "window_hours": 24,
            "events": len(events),
            "success_rate_pct": round((len(success_events) / len(events)) * 100, 2),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "articles_stored": stored_total,
            "freshness_lag_seconds": freshness_lag_seconds,
        }

    def get_status(self) -> dict[str, Any]:
        """Return current runner status for the API."""
        next_cycle = None
        if self._running and self._last_cycle_at:
            next_cycle = (
                self._last_cycle_at + timedelta(seconds=self.interval_seconds)
            ).isoformat()

        connectors_payload: dict[str, dict[str, Any]] = {}
        for connector_name in self._CONNECTOR_FACTORIES:
            enabled = self._is_connector_enabled(connector_name)
            default_status = SourceHealthRecord(
                source_key=f"connector-{connector_name}",
                enabled=enabled,
                state="ready" if enabled else "disabled",
            ).as_dict()
            status = {**default_status, **self._connector_status.get(connector_name, {})}
            connectors_payload[connector_name] = {
                "configured_enabled": self._configured_connector_enabled.get(connector_name, False),
                "runtime_override": self._connector_runtime_overrides.get(connector_name),
                "enabled": enabled,
                **status,
                "slo_24h": self._build_connector_slo(connector_name),
            }

        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_seconds": self.interval_seconds,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "next_cycle_at": next_cycle,
            "last_cycle_articles": self._last_cycle_articles,
            "total_articles_ingested": self._total_articles_ingested,
            "stock_correlation_enabled": self._stock_correlator_enabled,
            "near_dedup_enabled": getattr(self, "_near_dedup_enabled", False),
            "near_dedup_similarity_threshold": getattr(
                self,
                "_near_dedup_similarity_threshold",
                0.92,
            ),
            "connectors": connectors_payload,
            "recent_errors": self._errors[-8:],
        }

    async def start(self) -> None:
        """Start the continuous ingestion loop as a background task."""
        if not self.enabled:
            logger.info("Continuous ingest is disabled (CONTINUOUS_INGEST_ENABLED=false)")
            return

        if self._running:
            logger.warning("Continuous ingest runner already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Continuous ingest runner started — interval=%ds, gdelt=%s, sec=%s, newsdata=%s, reddit=%s",
            self.interval_seconds,
            self.gdelt_enabled,
            self.sec_edgar_enabled,
            self.newsdata_enabled,
            self.reddit_enabled,
        )

    async def stop(self) -> None:
        """Gracefully stop the continuous runner."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("Continuous ingest runner stopped")

    async def trigger_immediate(self) -> dict[str, Any]:
        """Run one ingest cycle immediately (called from API endpoint)."""
        return await self._run_cycle()

    async def _run_loop(self) -> None:
        """Main loop — runs ingest cycle, sleeps, repeat."""
        await asyncio.sleep(5)

        while True:
            if not self._running:
                return
            try:
                await self._run_cycle()
            except Exception as exc:
                logger.exception("Continuous ingest cycle failed: %s", exc)
                self._errors.append(
                    {
                        "time": datetime.now(UTC).isoformat(),
                        "error": str(exc),
                        "error_code": _classify_error(exc),
                        "type": "cycle_failure",
                    }
                )
                self._errors = self._errors[-20:]

            for _ in range(self.interval_seconds):
                if self._should_stop():
                    return
                await asyncio.sleep(1)

    def _should_stop(self) -> bool:
        return not self._running

    async def _resolve_source_id(self, source_key: str) -> int | None:
        sources = await self._source_repo.list_sources(enabled_only=False)
        for source in sources:
            if source.source_key == source_key:
                return source.id
        return None

    async def _run_cycle(self) -> dict[str, Any]:
        """Execute one complete ingestion cycle."""
        cycle_start = datetime.now(UTC)
        self._cycle_count += 1
        cycle_articles = 0
        cycle_errors = 0
        cycle_results: dict[str, Any] = {}
        cycle_run_id = f"continuous-{self._cycle_count}-{uuid.uuid4().hex[:8]}"

        logger.info("Ingest cycle #%d starting", self._cycle_count)

        await initialize_schema()

        enabled_connectors: list[str] = []
        for connector_name, (display_name, _) in self._CONNECTOR_FACTORIES.items():
            if not self._is_connector_enabled(connector_name):
                self._connector_status[connector_name] = SourceHealthRecord(
                    source_key=f"connector-{connector_name}",
                    enabled=False,
                    state="disabled",
                ).as_dict()
                continue
            await self._source_repo.upsert_sources(
                [
                    SourceConfig(
                        source_key=f"connector-{connector_name}",
                        name=display_name,
                        url=f"https://{connector_name}.source",
                        source_type="api",
                        source_category="finance",
                        connector_type=connector_name,
                        enabled=True,
                        crawl_interval_minutes=max(1, self.interval_seconds // 60),
                    )
                ]
            )
            enabled_connectors.append(connector_name)

        connector_instances = [
            (name, connector)
            for name, connector in self._build_connector_instances()
            if name in enabled_connectors
        ]

        for connector_name, connector in connector_instances:
            source_key = f"connector-{connector_name}"
            source_id = await self._resolve_source_id(source_key)
            started_at = datetime.now(UTC)

            try:
                raw_items = await connector.fetch_articles(source_id=source_id)
                normalized_input: list[dict[str, Any]] = []
                for item in raw_items:
                    if isinstance(item, ArticleIngestRecord):
                        normalized_input.append(item.as_storage_payload())
                    elif isinstance(item, dict):
                        normalized_input.append(item)

                valid_items, rejected = validate_connector_items(
                    connector_name, normalized_input
                )

                if (
                    self._stock_correlator_enabled
                    and self._stock_correlator
                    and valid_items
                ):
                    try:
                        valid_items = self._stock_correlator.enrich_articles(valid_items)
                    except Exception as exc:  # pragma: no cover - defensive fail-open
                        logger.warning(
                            "Connector %s enrichment failed (fail-open): %s",
                            connector_name,
                            exc,
                        )
                        self._errors.append(
                            {
                                "time": datetime.now(UTC).isoformat(),
                                "error": str(exc),
                                "error_code": "enrichment_error",
                                "type": f"connector_{connector_name}_enrichment",
                            }
                        )

                near_dedup_suppressed = 0
                if getattr(self, "_near_dedup_enabled", False) and valid_items:
                    valid_items, near_dedup_suppressed = suppress_near_duplicates(
                        valid_items,
                        similarity_threshold=getattr(
                            self,
                            "_near_dedup_similarity_threshold",
                            0.92,
                        ),
                    )
                    if near_dedup_suppressed:
                        logger.info(
                            "Connector %s near-dedup suppressed=%d",
                            connector_name,
                            near_dedup_suppressed,
                        )

                stored = 0
                if valid_items:
                    write_result = await self._article_repo.upsert_deduplicated(
                        run_id=cycle_run_id,
                        items=valid_items,
                    )
                    stored = int(write_result.items_stored)
                    cycle_articles += stored

                if rejected:
                    for issue in rejected[:5]:
                        self._errors.append(
                            {
                                "time": datetime.now(UTC).isoformat(),
                                "error": issue.get("error"),
                                "error_code": issue.get("error_code", "validation_error"),
                                "type": f"connector_{connector_name}",
                            }
                        )

                now = datetime.now(UTC)
                latency_ms = int((now - started_at).total_seconds() * 1000)
                state: Literal["ready", "degraded"] = "ready"
                if not valid_items or rejected:
                    state = "degraded"

                status = SourceHealthRecord(
                    source_key=source_key,
                    enabled=True,
                    state=state,
                    last_fetch_at=now.isoformat(),
                    last_success_at=now.isoformat() if stored > 0 else None,
                    last_articles_fetched=len(normalized_input),
                    last_articles_validated=len(valid_items),
                    last_articles_rejected=len(rejected),
                    last_articles_stored=stored,
                    last_fetch_latency_ms=latency_ms,
                    last_error_code=None if not rejected else "validation_error",
                    last_error=None
                    if not rejected
                    else f"{len(rejected)} payload(s) rejected",
                    consecutive_failures=0,
                )
                self._connector_status[connector_name] = status.as_dict()
                self._record_connector_event(
                    connector_name,
                    state=state,
                    fetched=len(normalized_input),
                    validated=len(valid_items),
                    rejected=len(rejected),
                    stored=stored,
                    latency_ms=latency_ms,
                    error_code="validation_error" if rejected else None,
                )

                cycle_results[connector_name] = {
                    "state": state,
                    "articles_fetched": len(normalized_input),
                    "articles_validated": len(valid_items),
                    "articles_rejected": len(rejected),
                    "articles_near_dedup_suppressed": near_dedup_suppressed,
                    "articles_stored": stored,
                    "latency_ms": latency_ms,
                }

                logger.info(
                    "Connector %s: fetched=%d validated=%d rejected=%d near_dedup=%d stored=%d latency_ms=%d",
                    connector_name,
                    len(normalized_input),
                    len(valid_items),
                    len(rejected),
                    near_dedup_suppressed,
                    stored,
                    latency_ms,
                )
            except Exception as exc:
                cycle_errors += 1
                now = datetime.now(UTC)
                latency_ms = int((now - started_at).total_seconds() * 1000)
                error_code = _classify_error(exc)

                previous_failures = int(
                    self._connector_status.get(connector_name, {}).get(
                        "consecutive_failures", 0
                    )
                    or 0
                )
                status = SourceHealthRecord(
                    source_key=source_key,
                    enabled=True,
                    state="error",
                    last_fetch_at=now.isoformat(),
                    last_articles_fetched=0,
                    last_articles_validated=0,
                    last_articles_rejected=0,
                    last_articles_stored=0,
                    last_fetch_latency_ms=latency_ms,
                    last_error_code=error_code,
                    last_error=str(exc),
                    consecutive_failures=previous_failures + 1,
                )
                self._connector_status[connector_name] = status.as_dict()
                self._record_connector_event(
                    connector_name,
                    state="error",
                    fetched=0,
                    validated=0,
                    rejected=0,
                    stored=0,
                    latency_ms=latency_ms,
                    error_code=error_code,
                )

                self._errors.append(
                    {
                        "time": now.isoformat(),
                        "error": str(exc),
                        "error_code": error_code,
                        "type": f"connector_{connector_name}",
                    }
                )
                cycle_results[connector_name] = {
                    "state": "error",
                    "error": str(exc),
                    "error_code": error_code,
                    "latency_ms": latency_ms,
                }
                logger.warning("Connector %s failed: %s", connector_name, exc)

        # --- Run RSS feed ingestion path as well ---
        try:
            from financial_news.services.news_ingest import NewsIngestor

            ingester = NewsIngestor(session_factory=self._session_factory)
            rss_result = await ingester.run_ingest()
            rss_stored = int(rss_result.items_stored)
            cycle_articles += rss_stored
            cycle_results["rss_feeds"] = {
                "state": "ready",
                "articles_fetched": int(rss_result.items_seen),
                "articles_stored": rss_stored,
                "sources_processed": int(rss_result.sources_processed),
            }
            logger.info(
                "RSS feeds: seen=%d stored=%d",
                rss_result.items_seen,
                rss_stored,
            )
        except Exception as exc:
            cycle_errors += 1
            error_code = _classify_error(exc)
            cycle_results["rss_feeds"] = {
                "state": "error",
                "error": str(exc),
                "error_code": error_code,
            }
            self._errors.append(
                {
                    "time": datetime.now(UTC).isoformat(),
                    "error": str(exc),
                    "error_code": error_code,
                    "type": "rss_feeds",
                }
            )
            logger.warning("RSS feed ingestion failed: %s", exc)

        self._errors = self._errors[-20:]
        self._last_cycle_at = datetime.now(UTC)
        self._last_cycle_articles = cycle_articles
        self._total_articles_ingested += cycle_articles

        elapsed = (datetime.now(UTC) - cycle_start).total_seconds()
        summary = IngestRunSummary(
            run_id=cycle_run_id,
            cycle=self._cycle_count,
            started_at=cycle_start,
            finished_at=datetime.now(UTC),
            elapsed_seconds=round(elapsed, 3),
            status="completed" if cycle_errors == 0 else "partial",
            articles_stored=cycle_articles,
            results=cycle_results,
            error_code=None if cycle_errors == 0 else "partial_failure",
        )

        logger.info(
            "Ingest cycle #%d completed in %.1fs — %d new articles (errors=%d)",
            self._cycle_count,
            elapsed,
            cycle_articles,
            cycle_errors,
        )

        return summary.as_dict()


# Module-level singleton
_runner: ContinuousIngestRunner | None = None


def get_runner(*, session_factory: Any | None = None) -> ContinuousIngestRunner:
    """Get or create the singleton runner instance."""
    global _runner
    if _runner is None:
        _runner = ContinuousIngestRunner(session_factory=session_factory)
    return _runner
