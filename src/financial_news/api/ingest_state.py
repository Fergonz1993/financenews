"""Shared ingest idempotency state."""

from __future__ import annotations

import time

_INGEST_IDEMPOTENCY_TTL_SECONDS = 900
_INGEST_IDEMPOTENCY_CACHE: dict[str, tuple[str, float]] = {}


def set_idempotency_ttl(seconds: int) -> None:
    global _INGEST_IDEMPOTENCY_TTL_SECONDS
    _INGEST_IDEMPOTENCY_TTL_SECONDS = max(60, int(seconds))


def _prune_ingest_idempotency_cache() -> None:
    now = time.monotonic()
    expired_keys = [
        key
        for key, (_run_id, expires_at) in _INGEST_IDEMPOTENCY_CACHE.items()
        if expires_at <= now
    ]
    for key in expired_keys:
        _INGEST_IDEMPOTENCY_CACHE.pop(key, None)


def _get_existing_run_for_idempotency(idempotency_key: str | None) -> str | None:
    if not idempotency_key:
        return None
    _prune_ingest_idempotency_cache()
    existing = _INGEST_IDEMPOTENCY_CACHE.get(idempotency_key)
    if not existing:
        return None
    return existing[0]


def _remember_ingest_idempotency(idempotency_key: str | None, run_id: str) -> None:
    if not idempotency_key:
        return
    expires_at = time.monotonic() + _INGEST_IDEMPOTENCY_TTL_SECONDS
    _INGEST_IDEMPOTENCY_CACHE[idempotency_key] = (run_id, expires_at)
