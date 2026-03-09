"""FastAPI application factory."""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from financial_news.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from financial_news.api.lifespan import app_lifespan
from financial_news.api.middleware import request_id_middleware
from financial_news.api.routes.articles import router as articles_router
from financial_news.api.routes.ingest import router as ingest_router
from financial_news.api.routes.notifications import router as notifications_router
from financial_news.api.routes.sources import router as sources_router
from financial_news.api.routes.system import router as system_router
from financial_news.api.routes.users import router as users_router
from financial_news.config import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI application with shared middleware and routers."""
    settings = get_settings()
    app = FastAPI(
        title="Financial News API",
        description="API for Financial News Analysis Platform",
        version=settings.version,
        lifespan=app_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(request_id_middleware)

    # FastAPI's exception handler API expects broad `Exception` handler types.
    # These handlers are intentionally narrower for better local type checking.
    app.add_exception_handler(
        RequestValidationError,
        cast(Any, validation_exception_handler),
    )
    app.add_exception_handler(Exception, cast(Any, unhandled_exception_handler))
    app.add_exception_handler(HTTPException, cast(Any, http_exception_handler))

    app.include_router(system_router)
    app.include_router(articles_router)
    app.include_router(sources_router)
    app.include_router(users_router)
    app.include_router(ingest_router)
    app.include_router(notifications_router)
    return app
