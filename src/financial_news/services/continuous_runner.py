"""Continuous ingestion runner — background async loop for periodic news fetching.

Runs both the existing RSS/feed-based ingestion AND the new public source
connectors (GDELT, SEC EDGAR, Newsdata.io) on a configurable interval.

Environment variables:
    CONTINUOUS_INGEST_ENABLED      - "true" to enable (default: true)
    CONTINUOUS_INGEST_INTERVAL_SECONDS - seconds between cycles (default: 300)
    GDELT_ENABLED                  - "true" to include GDELT (default: true)
    SEC_EDGAR_ENABLED              - "true" to include SEC EDGAR (default: true)
    NEWSDATA_ENABLED               - "true" to include Newsdata.io (default: true)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Any

from financial_news.services.connectors.gdelt import GDELTConnector
from financial_news.services.connectors.sec_edgar import SECEdgarConnector
from financial_news.services.connectors.newsdata import NewsdataConnector
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


class ContinuousIngestRunner:
    """Background async loop that periodically fetches news from all sources."""

    def __init__(self, *, session_factory=None) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._article_repo = ArticleRepository(session_factory=self._session_factory)
        self._source_repo = SourceRepository(session_factory=self._session_factory)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._cycle_count = 0
        self._last_cycle_at: datetime | None = None
        self._last_cycle_articles: int = 0
        self._total_articles_ingested: int = 0
        self._errors: list[dict[str, Any]] = []
        self._connector_status: dict[str, dict[str, Any]] = {}

        # Configuration
        self.enabled = _env_bool("CONTINUOUS_INGEST_ENABLED", default=True)
        self.interval_seconds = _env_int("CONTINUOUS_INGEST_INTERVAL_SECONDS", 300)
        self.gdelt_enabled = _env_bool("GDELT_ENABLED", default=True)
        self.sec_edgar_enabled = _env_bool("SEC_EDGAR_ENABLED", default=True)
        self.newsdata_enabled = _env_bool("NEWSDATA_ENABLED", default=True)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Return current runner status for the API."""
        next_cycle = None
        if self._running and self._last_cycle_at:
            from datetime import timedelta
            next_cycle = (
                self._last_cycle_at + timedelta(seconds=self.interval_seconds)
            ).isoformat()

        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_seconds": self.interval_seconds,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "next_cycle_at": next_cycle,
            "last_cycle_articles": self._last_cycle_articles,
            "total_articles_ingested": self._total_articles_ingested,
            "connectors": {
                "gdelt": {"enabled": self.gdelt_enabled, **self._connector_status.get("gdelt", {})},
                "sec_edgar": {"enabled": self.sec_edgar_enabled, **self._connector_status.get("sec_edgar", {})},
                "newsdata": {"enabled": self.newsdata_enabled, **self._connector_status.get("newsdata", {})},
            },
            "recent_errors": self._errors[-5:],
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
            "Continuous ingest runner started — interval=%ds, gdelt=%s, sec=%s, newsdata=%s",
            self.interval_seconds,
            self.gdelt_enabled,
            self.sec_edgar_enabled,
            self.newsdata_enabled,
        )

    async def stop(self) -> None:
        """Gracefully stop the continuous runner."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Continuous ingest runner stopped")

    async def trigger_immediate(self) -> dict[str, Any]:
        """Run one ingest cycle immediately (called from API endpoint)."""
        return await self._run_cycle()

    async def _run_loop(self) -> None:
        """Main loop — runs ingest cycle, sleeps, repeat."""
        # Initial delay to let the app finish starting up
        await asyncio.sleep(5)

        while self._running:
            try:
                await self._run_cycle()
            except Exception as exc:
                logger.exception("Continuous ingest cycle failed: %s", exc)
                self._errors.append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                    "type": "cycle_failure",
                })
                # Keep only last 20 errors
                self._errors = self._errors[-20:]

            # Sleep in small increments so we can respond to stop() quickly
            for _ in range(self.interval_seconds):
                if not self._running:
                    return
                await asyncio.sleep(1)

    async def _run_cycle(self) -> dict[str, Any]:
        """Execute one complete ingestion cycle."""
        cycle_start = datetime.now(timezone.utc)
        self._cycle_count += 1
        cycle_articles = 0
        cycle_results: dict[str, Any] = {}

        logger.info("Ingest cycle #%d starting", self._cycle_count)

        await initialize_schema()

        # --- Run connector-based ingestion (GDELT, SEC, Newsdata) ---
        connector_tasks: list[tuple[str, Any]] = []

        if self.gdelt_enabled:
            connector_tasks.append(("gdelt", GDELTConnector()))

        if self.sec_edgar_enabled:
            connector_tasks.append(("sec_edgar", SECEdgarConnector()))

        if self.newsdata_enabled:
            connector_tasks.append(("newsdata", NewsdataConnector()))

        # Ensure connector sources exist in DB
        for name, connector in connector_tasks:
            source_key = f"connector-{name}"
            source_name = {
                "gdelt": "GDELT Project",
                "sec_edgar": "SEC EDGAR",
                "newsdata": "Newsdata.io",
            }.get(name, name)

            await self._source_repo.upsert_sources([
                SourceConfig(
                    source_key=source_key,
                    name=source_name,
                    url=f"https://{name}.source",
                    source_type="api",
                    source_category="finance",
                    connector_type=name,
                    enabled=True,
                    crawl_interval_minutes=max(1, self.interval_seconds // 60),
                )
            ])

        # Fetch from all connectors concurrently
        for name, connector in connector_tasks:
            try:
                # Get source ID from DB
                sources = await self._source_repo.list_sources(enabled_only=True)
                source_id = None
                for src in sources:
                    if src.source_key == f"connector-{name}":
                        source_id = src.id
                        break

                articles = await connector.fetch_articles(source_id=source_id)

                if articles:
                    write_result = await self._article_repo.upsert_deduplicated(
                        run_id=f"continuous-{self._cycle_count}",
                        items=articles,
                    )
                    stored = write_result.items_stored
                    cycle_articles += stored
                    self._connector_status[name] = {
                        "last_fetch_at": datetime.now(timezone.utc).isoformat(),
                        "last_articles_fetched": len(articles),
                        "last_articles_stored": stored,
                        "status": "ok",
                    }
                    cycle_results[name] = {
                        "articles_fetched": len(articles),
                        "articles_stored": stored,
                    }
                    logger.info(
                        "Connector %s: fetched=%d stored=%d",
                        name, len(articles), stored,
                    )
                else:
                    self._connector_status[name] = {
                        "last_fetch_at": datetime.now(timezone.utc).isoformat(),
                        "last_articles_fetched": 0,
                        "last_articles_stored": 0,
                        "status": "empty",
                    }

            except Exception as exc:
                logger.warning("Connector %s failed: %s", name, exc)
                self._connector_status[name] = {
                    "last_fetch_at": datetime.now(timezone.utc).isoformat(),
                    "status": "error",
                    "error": str(exc),
                }
                self._errors.append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                    "type": f"connector_{name}",
                })

        # --- Also run existing RSS feed ingestion ---
        try:
            from financial_news.services.news_ingest import NewsIngestor

            ingester = NewsIngestor(session_factory=self._session_factory)
            rss_result = await ingester.run_ingest()
            rss_stored = rss_result.items_stored
            cycle_articles += rss_stored
            cycle_results["rss_feeds"] = {
                "articles_fetched": rss_result.items_seen,
                "articles_stored": rss_stored,
                "sources_processed": rss_result.sources_processed,
            }
            logger.info(
                "RSS feeds: seen=%d stored=%d",
                rss_result.items_seen, rss_stored,
            )
        except Exception as exc:
            logger.warning("RSS feed ingestion failed: %s", exc)
            self._errors.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "type": "rss_feeds",
            })

        # Update stats
        self._last_cycle_at = datetime.now(timezone.utc)
        self._last_cycle_articles = cycle_articles
        self._total_articles_ingested += cycle_articles

        elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
        logger.info(
            "Ingest cycle #%d completed in %.1fs — %d new articles",
            self._cycle_count, elapsed, cycle_articles,
        )

        return {
            "cycle": self._cycle_count,
            "elapsed_seconds": round(elapsed, 1),
            "articles_stored": cycle_articles,
            "results": cycle_results,
        }


# Module-level singleton
_runner: ContinuousIngestRunner | None = None


def get_runner(*, session_factory=None) -> ContinuousIngestRunner:
    """Get or create the singleton runner instance."""
    global _runner
    if _runner is None:
        _runner = ContinuousIngestRunner(session_factory=session_factory)
    return _runner
