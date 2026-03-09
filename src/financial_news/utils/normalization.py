"""Shared normalization helpers for API, ingestion, and persistence."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SEARCH_RE = re.compile(r"[^a-z0-9]+")


def slugify_value(value: Any) -> str:
    """Normalize a value for slug-style matching."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    return _SLUG_RE.sub("-", normalized).strip("-")


def coerce_string_list(value: Any, *, max_items: int | None = None) -> list[str]:
    """Normalize a list-like value into a list of strings."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        normalized = str(value).strip()
        items = [normalized] if normalized else []
    if max_items is not None:
        return items[:max_items]
    return items


def normalize_search_text(value: Any) -> str:
    """Normalize free-form text for case-insensitive search matching."""
    if not value:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return _SEARCH_RE.sub(" ", str(value).lower()).strip()


def canonicalize_url(value: str) -> str:
    """Canonicalize a URL for dedupe lookups."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    if "://" not in normalized:
        return normalized.rstrip("/")

    parsed = urlparse(normalized)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    cleaned_query = "&".join(
        [
            f"{name}={item_value}"
            for name, item_value in query_pairs
            if not name.startswith(("utm_", "ref_"))
            and name not in {"source", "session"}
            and not name.endswith("clid")
        ]
    )
    rebuilt = parsed._replace(query=cleaned_query, fragment="")
    return urlunparse(rebuilt).rstrip("/")


def coerce_datetime_utc(
    value: Any,
    *,
    default: datetime | None = None,
) -> datetime:
    """Coerce an arbitrary value to a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return default or datetime(1970, 1, 1, tzinfo=UTC)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return default or datetime(1970, 1, 1, tzinfo=UTC)
