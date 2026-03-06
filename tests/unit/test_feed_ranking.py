"""Unit tests for feed ranking and near-duplicate suppression."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from financial_news.services.feed_ranking import rank_articles, suppress_near_duplicates


def test_rank_articles_prioritizes_recency_and_signal() -> None:
    now = datetime(2026, 2, 28, 12, 0, tzinfo=UTC)
    older_high_signal = {
        "id": "a1",
        "title": "Legacy earnings beat",
        "source": "Example Wire",
        "published_at": (now - timedelta(hours=20)).isoformat(),
        "market_impact_score": 0.9,
        "sentiment_score": 0.7,
        "key_entities": ["AAPL"],
        "topics": ["Earnings"],
    }
    fresh_moderate_signal = {
        "id": "a2",
        "title": "Fed comments move futures",
        "source": "Market Desk",
        "published_at": (now - timedelta(hours=2)).isoformat(),
        "market_impact_score": 0.55,
        "sentiment_score": 0.62,
        "key_entities": ["Federal Reserve"],
        "topics": ["Policy", "Markets"],
    }

    ranked = rank_articles([older_high_signal, fresh_moderate_signal], now=now)
    assert ranked[0]["id"] == "a2"
    assert ranked[0]["relevance_score_v2"] >= ranked[1]["relevance_score_v2"]


def test_suppress_near_duplicates_drops_similar_titles() -> None:
    payload = [
        {"id": "1", "title": "Tesla beats expectations in Q4 earnings", "source": "A"},
        {"id": "2", "title": "Tesla beats expectation in Q4 earnings", "source": "B"},
        {"id": "3", "title": "Oil prices rise after OPEC update", "source": "C"},
    ]

    kept, suppressed = suppress_near_duplicates(payload, similarity_threshold=0.9)
    assert suppressed == 1
    assert [item["id"] for item in kept] == ["1", "3"]
