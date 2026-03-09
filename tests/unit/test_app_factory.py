"""Tests for FastAPI application assembly."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from financial_news.api import app_factory
from financial_news.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


def test_create_app_uses_settings_for_version_and_cors(monkeypatch) -> None:
    monkeypatch.setattr(
        app_factory,
        "get_settings",
        lambda: SimpleNamespace(
            version="9.9.9",
            api=SimpleNamespace(cors_origins=["https://ui.example"]),
        ),
    )

    app = app_factory.create_app()

    assert app.version == "9.9.9"
    cors = next(mw for mw in app.user_middleware if mw.cls is CORSMiddleware)
    assert cors.kwargs["allow_origins"] == ["https://ui.example"]


def test_create_app_registers_exception_handlers_and_core_routes(monkeypatch) -> None:
    monkeypatch.setattr(
        app_factory,
        "get_settings",
        lambda: SimpleNamespace(
            version="1.0.0",
            api=SimpleNamespace(cors_origins=["http://localhost:3000"]),
        ),
    )

    app = app_factory.create_app()
    routes = {route.path for route in app.routes}

    assert "/" in routes
    assert "/health" in routes
    assert "/api/articles" in routes
    assert app.exception_handlers[RequestValidationError] is validation_exception_handler
    assert app.exception_handlers[Exception] is unhandled_exception_handler
    assert app.exception_handlers[HTTPException] is http_exception_handler
