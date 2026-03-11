"""Lifecycle hooks for background services."""

from __future__ import annotations

import asyncio
from typing import Any

from financial_news.api.container import AppContainer


async def run_startup_ingest(container: AppContainer) -> None:
    try:
        try:
            count = await container.ingester.count_articles()
        except Exception as exc:
            container.logger.warning(
                "Startup count_articles failed; attempting bootstrap ingest: %s",
                exc,
            )
            await container.ingester.run_ingest()
            return

        if count == 0:
            await container.ingester.run_ingest()
    except Exception as exc:
        container.logger.warning("Startup ingest failed: %s", exc)


async def _run_periodic_ingest(
    container: AppContainer,
    interval_seconds: int,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            return
        try:
            run_id = await container.ingester.start_async_ingest()
            container.logger.info(
                "Scheduled ingest queued run_id=%s interval_seconds=%s",
                run_id,
                interval_seconds,
            )
        except RuntimeError as exc:
            container.logger.info("Scheduled ingest skipped: %s", exc)
        except Exception as exc:
            container.logger.warning("Scheduled ingest failed: %s", exc)


async def startup_services(app_state: Any, container: AppContainer) -> None:
    """Start background tasks and shared workers."""
    from financial_news.api import main as api_main

    tasks: list[asyncio.Task[Any]] = []
    tasks.append(asyncio.create_task(api_main.generate_demo_alerts()))
    tasks.append(asyncio.create_task(api_main.run_startup_ingest(container)))
    auto_ingest_interval = max(
        0,
        int(container.settings.ingest.auto_ingest_interval_seconds),
    )
    if auto_ingest_interval > 0:
        tasks.append(asyncio.create_task(_run_periodic_ingest(container, auto_ingest_interval)))
    await container.continuous_runner.start()
    app_state.background_tasks = tasks


async def shutdown_services(app_state: Any, container: AppContainer) -> None:
    """Stop shared workers and background tasks."""
    await container.continuous_runner.stop()
    tasks = list(getattr(app_state, "background_tasks", []))
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            container.logger.warning("Background task shutdown warning: %s", exc)
    app_state.background_tasks = []
