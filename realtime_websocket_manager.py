"""Compatibility shim for legacy imports."""

from financial_news.services.websocket import (  # noqa: F401
    NewsAlertSystem,
    RealTimeStreamManager,
    StreamConfig,
    StreamEvent,
    main,
)

__all__ = [
    "NewsAlertSystem",
    "RealTimeStreamManager",
    "StreamConfig",
    "StreamEvent",
    "main",
]
