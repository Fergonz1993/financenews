"""Unit tests for Reddit connector rollout controls."""

from __future__ import annotations

from financial_news.services.connectors.reddit import (
    _REDDIT_BUDGET_STATE,
    RedditFinanceConnector,
    _is_spammy_post,
    _parse_subreddits_from_env,
    _precision_score,
)


def test_parse_subreddits_from_env(monkeypatch) -> None:
    monkeypatch.setenv("REDDIT_SUBREDDITS", "stocks, investing,Economics")
    assert _parse_subreddits_from_env() == ["stocks", "investing", "economics"]


def test_precision_score_rewards_financial_signal() -> None:
    score = _precision_score(
        "AAPL beats Q4 earnings by 12%",
        "Apple earnings and Fed policy expectations moved markets.",
        "stocks",
        ["AAPL"],
    )
    assert score >= 0.6


def test_spam_filter_rejects_low_signal_posts() -> None:
    assert _is_spammy_post("Daily Discussion Thread", "what are your moves", 0.1) is True
    assert _is_spammy_post("Fed minutes released", "Detailed macro commentary", 0.75) is False


def test_rate_budget_is_enforced() -> None:
    connector = RedditFinanceConnector(
        subreddits=["stocks"],
        rate_budget_per_hour=2,
        precision_threshold=0.0,
    )
    _REDDIT_BUDGET_STATE["requests_used"] = 0
    assert connector._consume_rate_budget() is True
    assert connector._consume_rate_budget() is True
    assert connector._consume_rate_budget() is False
