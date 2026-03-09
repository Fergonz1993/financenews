"""
Sentiment Analysis Module for Financial News
"""

import re

import nltk
from nltk.sentiment.vader import (
    SentimentIntensityAnalyzer,
)
from nltk.tokenize import sent_tokenize

from financial_news.core.summarizer_config import setup_logging

# Set up logging
logger = setup_logging()

# Financial terms with their sentiment bias
FINANCIAL_TERMS = {
    # Positive terms
    "growth": 2.0,
    "profit": 2.0,
    "increase": 1.5,
    "rise": 1.5,
    "gain": 1.5,
    "surge": 2.0,
    "bull": 1.5,
    "recovery": 1.5,
    "outperform": 2.0,
    "beat expectations": 2.5,
    "exceed": 1.5,
    "upgrade": 2.0,
    "rally": 1.5,
    "breakthrough": 2.0,
    "innovation": 1.5,
    "expansion": 1.5,
    "opportunity": 1.0,

    # Negative terms
    "loss": -2.0,
    "decline": -1.5,
    "decrease": -1.5,
    "fall": -1.5,
    "drop": -1.5,
    "plunge": -2.0,
    "bear": -1.5,
    "recession": -2.5,
    "bankruptcy": -3.0,
    "default": -2.5,
    "underperform": -2.0,
    "miss expectations": -2.5,
    "downgrade": -2.0,
    "investigation": -1.5,
    "lawsuit": -2.0,
    "debt": -1.0,
    "volatility": -1.0,
    "risk": -1.0,
    "inflation": -1.0,
}


class FinancialSentimentAnalyzer:
    """Sentiment analyzer specifically tuned for financial news."""

    def __init__(self) -> None:
        """Initialize the sentiment analyzer."""
        # Download necessary NLTK resources if not already downloaded
        try:
            nltk.data.find("vader_lexicon")
        except LookupError:
            nltk.download("vader_lexicon")

        try:
            nltk.data.find("punkt")
        except LookupError:
            nltk.download("punkt")

        # Initialize VADER sentiment analyzer
        self.sia = SentimentIntensityAnalyzer()

        # Add financial terms to the VADER lexicon
        for term, score in FINANCIAL_TERMS.items():
            self.sia.lexicon[term] = score

    def analyze_text(self, text: str) -> dict:
        """
        Analyze the sentiment of a financial news article.

        Args:
            text: The article text to analyze

        Returns:
            Dictionary containing sentiment analysis results
        """
        if not text:
            return {
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "compound_score": 0.0,
                "positive_score": 0.0,
                "negative_score": 0.0,
                "neutral_score": 0.0,
                "sentence_scores": [],
            }

        # Clean text
        text = self._clean_text(text)

        # Newer NLTK releases may require punkt_tab in addition to punkt.
        # Fall back to a simple regex splitter so CI and clean installs do not
        # depend on downloading tokenizer data at runtime.
        try:
            sentences = sent_tokenize(text)
        except LookupError:
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", text)
                if sentence.strip()
            ] or [text]

        # Analyze each sentence
        sentence_scores = []
        for sentence in sentences:
            score = self.sia.polarity_scores(sentence)
            sentence_scores.append(
                {
                    "text": sentence[:100] + "..." if len(sentence) > 100 else sentence,
                    "compound": score["compound"],
                    "positive": score["pos"],
                    "negative": score["neg"],
                    "neutral": score["neu"],
                }
            )

        # Calculate overall sentiment
        compound_scores = [score["compound"] for score in sentence_scores]
        avg_compound = sum(compound_scores) / len(compound_scores) if compound_scores else 0

        # Get average scores for positive, negative, and neutral
        pos_scores = [score["positive"] for score in sentence_scores]
        neg_scores = [score["negative"] for score in sentence_scores]
        neu_scores = [score["neutral"] for score in sentence_scores]

        avg_pos = sum(pos_scores) / len(pos_scores) if pos_scores else 0
        avg_neg = sum(neg_scores) / len(neg_scores) if neg_scores else 0
        avg_neu = sum(neu_scores) / len(neu_scores) if neu_scores else 0

        # Determine sentiment category
        sentiment_score = (avg_compound + 1) / 2  # Normalize from [-1, 1] to [0, 1]

        if avg_compound >= 0.05:
            sentiment = "positive"
        elif avg_compound <= -0.05:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "compound_score": avg_compound,
            "positive_score": avg_pos,
            "negative_score": avg_neg,
            "neutral_score": avg_neu,
            "sentence_scores": sentence_scores[:5],  # Return only top 5 sentence scores
        }

    def estimate_market_impact(
        self,
        sentiment_score: float,
        entity_importance: float = 1.0,
    ) -> float:
        """
        Estimate the potential market impact based on sentiment and entity importance.

        Args:
            sentiment_score: Normalized sentiment score (0-1)
            entity_importance: Importance weight of entities mentioned (0-1)

        Returns:
            Market impact score (0-1)
        """
        # Adjust sentiment to be centered at 0.5
        adjusted_sentiment = abs(sentiment_score - 0.5) * 2  # Convert to 0-1 scale

        # Calculate impact (entities with extreme sentiment have higher impact)
        impact = adjusted_sentiment * entity_importance

        # Normalize to 0-1 range
        return min(1.0, impact)

    def _clean_text(self, text: str) -> str:
        """Clean the text for sentiment analysis."""
        # Remove URLs
        text = re.sub(r"http\S+", "", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r"[^\w\s.,!?;:-]", "", text)

        return text.strip()


# Singleton instance
_sentiment_analyzer = None


def get_sentiment_analyzer() -> FinancialSentimentAnalyzer:
    """Get or create a singleton instance of the sentiment analyzer."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = FinancialSentimentAnalyzer()
    return _sentiment_analyzer


def analyze_article_sentiment(article_text: str) -> dict:
    """
    Analyze the sentiment of a financial news article.

    Args:
        article_text: The article text to analyze

    Returns:
        Dictionary containing sentiment analysis results
    """
    analyzer = get_sentiment_analyzer()
    return analyzer.analyze_text(article_text)
