"""FinBERT-powered financial sentiment analysis — optional upgrade over VADER.

When the ``transformers`` library is installed (via ``pip install -e ".[ai]"``),
this module loads ProsusAI/finbert for domain-specific sentiment analysis.
Otherwise the system falls back to the VADER-based analyser in ``sentiment.py``.

Usage::

    from financial_news.core.sentiment_finbert import analyze_article_sentiment_finbert

    result = analyze_article_sentiment_finbert("Apple beats Q3 earnings expectations")
    # {'sentiment': 'positive', 'sentiment_score': 0.87, ...}

Model reference:
    https://huggingface.co/ProsusAI/finbert
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---- lazy-loaded singleton ----

_finbert_pipeline: Any = None
_finbert_available: bool | None = None

MODEL_NAME = "ProsusAI/finbert"
MAX_TOKENS = 512  # FinBERT's max input length


def is_finbert_available() -> bool:
    """Check whether `transformers` and `torch` are installed."""
    global _finbert_available
    if _finbert_available is None:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            _finbert_available = True
        except ImportError:
            _finbert_available = False
    return _finbert_available


def _get_pipeline() -> Any:
    """Lazily initialise the FinBERT sentiment pipeline."""
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return _finbert_pipeline

    if not is_finbert_available():
        raise RuntimeError(
            "FinBERT requires 'transformers' and 'torch'. "
            "Install with: pip install -e '.[ai]'"
        )

    from transformers import pipeline

    logger.info("Loading FinBERT model (%s) — first run may download ~500 MB", MODEL_NAME)
    _finbert_pipeline = pipeline(
        "sentiment-analysis",
        model=MODEL_NAME,
        tokenizer=MODEL_NAME,
        truncation=True,
        max_length=MAX_TOKENS,
    )
    logger.info("FinBERT loaded successfully")
    return _finbert_pipeline


def _clean_text(text: str) -> str:
    """Minimal cleaning for transformer input."""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def analyze_article_sentiment_finbert(article_text: str) -> dict[str, Any]:
    """Analyse sentiment using FinBERT.

    Returns a dict with the same keys as the VADER-based
    ``analyze_article_sentiment`` for drop-in compatibility.

    Label mapping:
        FinBERT outputs ``positive``, ``negative``, ``neutral`` directly.

    Score mapping:
        ``sentiment_score`` is normalised to [0, 1] where 0 = most negative,
        0.5 = neutral, 1 = most positive.
    """
    if not article_text or not article_text.strip():
        return {
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "compound_score": 0.0,
            "positive_score": 0.0,
            "negative_score": 0.0,
            "neutral_score": 0.0,
        }

    pipe = _get_pipeline()
    cleaned = _clean_text(article_text)

    # Truncate to avoid tokenizer issues (rough char limit)
    if len(cleaned) > MAX_TOKENS * 4:
        cleaned = cleaned[: MAX_TOKENS * 4]

    result = pipe(cleaned)[0]
    label: str = result["label"].lower()  # positive / negative / neutral
    score: float = result["score"]  # confidence

    # Map to normalised sentiment_score [0, 1]
    if label == "positive":
        sentiment_score = 0.5 + (score * 0.5)  # → [0.5, 1.0]
        compound = score
    elif label == "negative":
        sentiment_score = 0.5 - (score * 0.5)  # → [0.0, 0.5]
        compound = -score
    else:
        sentiment_score = 0.5
        compound = 0.0

    return {
        "sentiment": label,
        "sentiment_score": round(sentiment_score, 4),
        "compound_score": round(compound, 4),
        "positive_score": round(score if label == "positive" else 0.0, 4),
        "negative_score": round(score if label == "negative" else 0.0, 4),
        "neutral_score": round(score if label == "neutral" else 0.0, 4),
    }


# ---- Auto-selecting wrapper ----


def analyze_article_sentiment_auto(article_text: str) -> dict[str, Any]:
    """Use FinBERT if available, otherwise fall back to VADER.

    This is the recommended entry-point for callers who want the best
    available sentiment analysis without caring which engine is used.
    """
    if is_finbert_available():
        try:
            return analyze_article_sentiment_finbert(article_text)
        except Exception as exc:
            logger.warning("FinBERT failed, falling back to VADER: %s", exc)

    # Fallback to VADER
    from financial_news.core.sentiment import analyze_article_sentiment
    return analyze_article_sentiment(article_text)
