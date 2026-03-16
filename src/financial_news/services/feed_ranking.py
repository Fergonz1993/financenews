"""Feed ranking and near-duplicate suppression helpers.

This module is intentionally side-effect free so the scoring logic can be
reused by API responses, smoke checks, and future offline evaluations.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _parse_published_at(value: Any, *, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return fallback or datetime.now(UTC)


def _normalize_title(value: Any) -> str:
    title = str(value or "").strip().lower()
    if not title:
        return ""
    return _NORMALIZE_RE.sub(" ", title).strip()


def _source_key(article: dict[str, Any]) -> str:
    source = article.get("source") or article.get("source_name") or "unknown"
    return _NORMALIZE_RE.sub("-", str(source).strip().lower()).strip("-") or "unknown"


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_relevance_score(
    article: dict[str, Any],
    *,
    now: datetime | None = None,
    source_counts: Counter[str] | None = None,
) -> float:
    """Compute a relevance score in [0.0, 1.0]."""
    current = now or datetime.now(UTC)
    published_at = _parse_published_at(article.get("published_at"), fallback=current)
    age_hours = max(0.0, (current - published_at).total_seconds() / 3600.0)
    recency_score = math.exp(-age_hours / 24.0)

    market_impact = max(0.0, min(1.0, _coerce_float(article.get("market_impact_score"))))
    sentiment_score = _coerce_float(article.get("sentiment_score"), default=0.5)
    sentiment_intensity = max(0.0, min(1.0, abs(sentiment_score - 0.5) * 2.0))
    raw_entities = article.get("key_entities")
    entities = raw_entities if isinstance(raw_entities, list) else []
    raw_topics = article.get("topics")
    topics = raw_topics if isinstance(raw_topics, list) else []
    richness = min(1.0, (len(entities) / 5.0) + (len(topics) / 6.0))

    source_diversity = 0.5
    if source_counts:
        source = _source_key(article)
        total = max(1, sum(source_counts.values()))
        concentration = source_counts.get(source, 0) / total
        source_diversity = max(0.0, 1.0 - concentration)

    score = (
        (0.45 * recency_score)
        + (0.20 * market_impact)
        + (0.15 * sentiment_intensity)
        + (0.10 * source_diversity)
        + (0.10 * richness)
    )
    return round(max(0.0, min(1.0, score)), 6)


def rank_articles(
    articles: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    descending: bool = True,
) -> list[dict[str, Any]]:
    """Return articles ranked by relevance with score annotations."""
    if not articles:
        return []
    source_counts: Counter[str] = Counter(_source_key(article) for article in articles)
    scored: list[dict[str, Any]] = []
    for article in articles:
        payload = dict(article)
        payload["relevance_score_v2"] = compute_relevance_score(
            payload,
            now=now,
            source_counts=source_counts,
        )
        scored.append(payload)
    return sorted(
        scored,
        key=lambda item: float(item.get("relevance_score_v2", 0.0)),
        reverse=descending,
    )


def suppress_near_duplicates(
    articles: list[dict[str, Any]],
    *,
    similarity_threshold: float = 0.92,
) -> tuple[list[dict[str, Any]], int]:
    """Drop near-duplicate titles while keeping deterministic order.

    Uses Jaccard similarity (word sets intersection over union) instead of
    difflib.SequenceMatcher for O(N) string comparison performance.
    """
    if not articles:
        return [], 0

    kept: list[dict[str, Any]] = []

    # Store tuples of (title_string, set_of_bigrams)
    fingerprints: list[tuple[str, set[str]]] = []
    suppressed = 0

    for article in articles:
        title = _normalize_title(article.get("title"))
        if not title:
            kept.append(article)
            continue

        # Use character bigrams for better approximation of SequenceMatcher
        # Pad with spaces to capture word boundaries
        padded_title = f" {title} "
        title_bigrams = {padded_title[i:i+2] for i in range(len(padded_title) - 1)}
        title_bigrams_len = len(title_bigrams)
        is_duplicate = False

        for existing_title, existing_bigrams in fingerprints:
            if title == existing_title:
                is_duplicate = True
                break

            if not title_bigrams or not existing_bigrams:
                continue

            intersection_size = len(title_bigrams & existing_bigrams)

            # SequenceMatcher ratio is roughly equivalent to 2*|A ∩ B| / (|A| + |B|)
            # which is Dice coefficient, but Jaccard is |A ∩ B| / |A U B|
            # We can compute a Dice-like coefficient from intersection and total length
            total_len = title_bigrams_len + len(existing_bigrams)
            if total_len > 0 and (2 * intersection_size / total_len) >= similarity_threshold:
                is_duplicate = True
                break

        if is_duplicate:
            suppressed += 1
            continue

        fingerprints.append((title, title_bigrams))
        kept.append(article)

    return kept, suppressed
