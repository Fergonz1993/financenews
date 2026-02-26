"""Compatibility shim for internal imports."""

from financial_news.core.summarizer import (  # noqa: F401
    Article,
    CacheManager,
    Config,
    EnhancedNewsSummarizer,
)

__all__ = [
    "Article",
    "CacheManager",
    "Config",
    "EnhancedNewsSummarizer",
]
