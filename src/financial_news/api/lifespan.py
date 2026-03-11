"""Application lifespan helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from financial_news.api.container import get_app_container
from financial_news.api.lifecycle import shutdown_services, startup_services


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown hooks using the shared app container."""
    container = get_app_container(app)
    await startup_services(app.state, container)
    try:
        yield
    finally:
        await shutdown_services(app.state, container)
