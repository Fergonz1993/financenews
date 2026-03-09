"""Application lifespan helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Delegate lifecycle hooks to the compatibility module."""
    from financial_news.api import main as api_main

    await api_main.startup_event()
    try:
        yield
    finally:
        await api_main.shutdown_event()
