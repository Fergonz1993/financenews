"""
News Intelligence & NLP Engine

This module provides advanced natural language processing capabilities for financial news,
including entity extraction, sentiment analysis, event detection, topic modeling, and
real-time news monitoring with AI-powered insights.
"""

import asyncio
import json
import logging
import re
import sqlite3
import uuid
import warnings
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import nltk
import numpy as np
import spacy
import yfinance as yf
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

warnings.filterwarnings("ignore")

# Download required NLTK data
try:
    nltk.download("punkt", quiet=True)
    nltk.download("stopwords", quiet=True)
    nltk.download("vader_lexicon", quiet=True)
except:
    pass

logger = logging.getLogger(__name__)


class SentimentPolarity(Enum):
    """Sentiment polarity classifications."""

    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class EventType(Enum):
    """Financial event types."""

    EARNINGS = "earnings"
    MERGER_ACQUISITION = "merger_acquisition"
    REGULATORY = "regulatory"
    LEADERSHIP_CHANGE = "leadership_change"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    INVESTMENT = "investment"
    LEGAL = "legal"
    MARKET_MOVEMENT = "market_movement"
    ECONOMIC_INDICATOR = "economic_indicator"
    DIVIDEND = "dividend"
    SHARE_BUYBACK = "share_buyback"
    BANKRUPTCY = "bankruptcy"
    IPO = "ipo"
    DELISTING = "delisting"
    SPLIT = "split"
    OTHER = "other"


class ConfidenceLevel(Enum):
    """Confidence levels for NLP predictions."""

    VERY_HIGH = "very_high"  # > 0.9
    HIGH = "high"  # 0.7 - 0.9
    MEDIUM = "medium"  # 0.5 - 0.7
    LOW = "low"  # 0.3 - 0.5
    VERY_LOW = "very_low"  # < 0.3


@dataclass
class Entity:
    """Named entity with metadata."""

    text: str
    label: str
    start: int
    end: int
    confidence: float
    ticker: str | None = None
    sector: str | None = None
    market_cap: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sentiment:
    """Sentiment analysis result."""

    polarity: SentimentPolarity
    score: float
    confidence: ConfidenceLevel
    reasoning: str
    entity_specific: dict[str, float] = field(default_factory=dict)
    aspects: dict[str, float] = field(default_factory=dict)  # Aspect-based sentiment


@dataclass
class Event:
    """Financial event detection result."""

    event_type: EventType
    entities: list[Entity]
    description: str
    impact_score: float
    confidence: float
    timeframe: str | None = None
    market_implications: list[str] = field(default_factory=list)


@dataclass
class Topic:
    """Topic modeling result."""

    topic_id: int
    keywords: list[str]
    description: str
    weight: float
    related_entities: list[str] = field(default_factory=list)


@dataclass
class NewsArticle:
    """Processed news article."""

    article_id: str
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    author: str | None = None
    entities: list[Entity] = field(default_factory=list)
    sentiment: Sentiment | None = None
    events: list[Event] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    market_impact: float = 0.0
    readability_score: float = 0.0
    credibility_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsInsight:
    """AI-generated news insight."""

    insight_id: str
    title: str
    summary: str
    key_points: list[str]
    affected_entities: list[str]
    market_implications: list[str]
    sentiment_overview: str
    confidence_score: float
    generated_at: datetime = field(default_factory=datetime.now)


class FinancialEntityRecognizer:
    """Advanced financial entity recognition system."""

    def __init__(self):
        self.company_patterns = self._load_company_patterns()
        self.financial_terms = self._load_financial_terms()
        self.ticker_cache = {}
        self.sector_cache = {}

        # Load spaCy model for NER
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning(
                "spaCy model not found. Install with: python -m spacy download en_core_web_sm"
            )
            self.nlp = None

    def _load_company_patterns(self) -> list[str]:
        """Load company name patterns."""
        return [
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|LLC|Ltd|Company|Co)\b",
            r"\b[A-Z]{2,5}\b",  # Potential tickers
            r"\b(?:Apple|Microsoft|Google|Amazon|Tesla|Meta|Netflix|Nvidia)\b",  # Major companies
        ]

    def _load_financial_terms(self) -> set[str]:
        """Load financial terminology."""
        return {
            "earnings",
            "revenue",
            "profit",
            "loss",
            "acquisition",
            "merger",
            "dividend",
            "buyback",
            "ipo",
            "bankruptcy",
            "delisting",
            "split",
            "partnership",
            "investment",
            "funding",
            "valuation",
            "market cap",
            "share price",
            "stock",
            "equity",
            "bond",
            "debt",
            "credit",
            "bear market",
            "bull market",
            "volatility",
            "liquidity",
        }

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract financial entities from text."""
        entities = []

        # Use spaCy for general NER
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ["ORG", "PERSON", "GPE", "MONEY", "PERCENT"]:
                    entity = Entity(
                        text=ent.text,
                        label=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char,
                        confidence=0.8,
                    )

                    # Enhanced processing for organizations
                    if ent.label_ == "ORG":
                        ticker = await self._get_ticker_for_company(ent.text)
                        if ticker:
                            entity.ticker = ticker
                            entity.sector = await self._get_sector_for_ticker(ticker)
                            entity.confidence = 0.9

                    entities.append(entity)

        # Extract potential tickers
        ticker_pattern = r"\b[A-Z]{1,5}\b"
        for match in re.finditer(ticker_pattern, text):
            ticker = match.group()
            if await self._is_valid_ticker(ticker):
                entity = Entity(
                    text=ticker,
                    label="TICKER",
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    ticker=ticker,
                )
                entity.sector = await self._get_sector_for_ticker(ticker)
                entities.append(entity)

        # Extract financial terms
        for term in self.financial_terms:
            pattern = r"\b" + re.escape(term) + r"\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(
                    Entity(
                        text=match.group(),
                        label="FINANCIAL_TERM",
                        start=match.start(),
                        end=match.end(),
                        confidence=0.7,
                    )
                )

        # Remove duplicates and overlapping entities
        entities = self._remove_overlapping_entities(entities)

        return entities

    async def _get_ticker_for_company(self, company_name: str) -> str | None:
        """Get ticker symbol for company name."""
        if company_name in self.ticker_cache:
            return self.ticker_cache[company_name]

        # Simple mapping for major companies (in real implementation, use API)
        company_tickers = {
            "Apple": "AAPL",
            "Microsoft": "MSFT",
            "Google": "GOOGL",
            "Amazon": "AMZN",
            "Tesla": "TSLA",
            "Meta": "META",
            "Netflix": "NFLX",
            "Nvidia": "NVDA",
        }

        ticker = company_tickers.get(company_name)
        if ticker:
            self.ticker_cache[company_name] = ticker

        return ticker

    async def _get_sector_for_ticker(self, ticker: str) -> str | None:
        """Get sector for ticker symbol."""
        if ticker in self.sector_cache:
            return self.sector_cache[ticker]

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get("sector")
            if sector:
                self.sector_cache[ticker] = sector
            return sector
        except:
            return None

    async def _is_valid_ticker(self, ticker: str) -> bool:
        """Check if string is a valid ticker symbol."""
        if len(ticker) < 1 or len(ticker) > 5:
            return False

        # Exclude common English words that are all caps
        common_words = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL"}
        if ticker in common_words:
            return False

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return "symbol" in info or "shortName" in info
        except:
            return False

    def _remove_overlapping_entities(self, entities: list[Entity]) -> list[Entity]:
        """Remove overlapping entities, keeping the one with highest confidence."""
        entities.sort(key=lambda x: (x.start, -x.confidence))
        filtered = []

        for entity in entities:
            overlaps = False
            for existing in filtered:
                if entity.start < existing.end and entity.end > existing.start:
                    if entity.confidence > existing.confidence:
                        filtered.remove(existing)
                    else:
                        overlaps = True
                        break

            if not overlaps:
                filtered.append(entity)

        return filtered


class AdvancedSentimentAnalyzer:
    """Multi-model sentiment analysis for financial text."""

    def __init__(self):
        self.vader_analyzer = SentimentIntensityAnalyzer()
        self.financial_lexicon = self._load_financial_lexicon()

        # Load FinBERT for financial sentiment analysis
        try:
            self.finbert_tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.finbert_model = AutoModelForSequenceClassification.from_pretrained(
                "ProsusAI/finbert"
            )
            self.finbert_pipeline = pipeline(
                "sentiment-analysis",
                model=self.finbert_model,
                tokenizer=self.finbert_tokenizer,
            )
        except Exception as e:
            logger.warning(f"Could not load FinBERT: {e}")
            self.finbert_pipeline = None

    def _load_financial_lexicon(self) -> dict[str, float]:
        """Load financial-specific sentiment lexicon."""
        return {
            # Positive terms
            "growth": 1.5,
            "profit": 1.8,
            "revenue": 1.2,
            "bullish": 2.0,
            "outperform": 1.7,
            "upgrade": 1.5,
            "beat": 1.8,
            "strong": 1.3,
            "rally": 1.6,
            "surge": 1.9,
            "soar": 2.0,
            "climb": 1.4,
            # Negative terms
            "loss": -1.8,
            "decline": -1.5,
            "bearish": -2.0,
            "downgrade": -1.7,
            "miss": -1.6,
            "weak": -1.3,
            "plunge": -2.0,
            "crash": -2.2,
            "bankruptcy": -2.5,
            "fraud": -2.3,
            "scandal": -2.1,
            "lawsuit": -1.4,
            # Neutral/contextual terms
            "merger": 0.5,
            "acquisition": 0.7,
            "ipo": 0.3,
            "dividend": 0.8,
            "split": 0.2,
            "partnership": 0.6,
            "investment": 0.4,
        }

    async def analyze_sentiment(
        self, text: str, entities: list[Entity] | None = None
    ) -> Sentiment:
        """Comprehensive sentiment analysis."""

        # VADER sentiment
        vader_scores = self.vader_analyzer.polarity_scores(text)

        # TextBlob sentiment
        blob = TextBlob(text)
        textblob_polarity = blob.sentiment.polarity

        # FinBERT sentiment (if available)
        finbert_score = 0.0
        if self.finbert_pipeline:
            try:
                finbert_result = self.finbert_pipeline(text[:512])  # Truncate for model
                finbert_label = finbert_result[0]["label"].lower()
                finbert_confidence = finbert_result[0]["score"]

                if finbert_label == "positive":
                    finbert_score = finbert_confidence
                elif finbert_label == "negative":
                    finbert_score = -finbert_confidence
                else:
                    finbert_score = 0.0
            except:
                finbert_score = 0.0

        # Financial lexicon sentiment
        lexicon_score = self._calculate_lexicon_sentiment(text)

        # Ensemble scoring
        weights = {"vader": 0.2, "textblob": 0.2, "finbert": 0.4, "lexicon": 0.2}

        final_score = (
            weights["vader"] * vader_scores["compound"]
            + weights["textblob"] * textblob_polarity
            + weights["finbert"] * finbert_score
            + weights["lexicon"] * lexicon_score
        )

        # Determine polarity
        if final_score >= 0.6:
            polarity = SentimentPolarity.VERY_POSITIVE
        elif final_score >= 0.2:
            polarity = SentimentPolarity.POSITIVE
        elif final_score >= -0.2:
            polarity = SentimentPolarity.NEUTRAL
        elif final_score >= -0.6:
            polarity = SentimentPolarity.NEGATIVE
        else:
            polarity = SentimentPolarity.VERY_NEGATIVE

        # Calculate confidence
        variance = np.var(
            [vader_scores["compound"], textblob_polarity, finbert_score, lexicon_score]
        )

        if variance < 0.1:
            confidence = ConfidenceLevel.VERY_HIGH
        elif variance < 0.2:
            confidence = ConfidenceLevel.HIGH
        elif variance < 0.4:
            confidence = ConfidenceLevel.MEDIUM
        elif variance < 0.6:
            confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.VERY_LOW

        # Entity-specific sentiment
        entity_sentiment = {}
        if entities:
            entity_sentiment = await self._analyze_entity_sentiment(text, entities)

        # Aspect-based sentiment
        aspects = self._analyze_aspect_sentiment(text)

        reasoning = self._generate_sentiment_reasoning(
            final_score, polarity, vader_scores, finbert_score
        )

        return Sentiment(
            polarity=polarity,
            score=final_score,
            confidence=confidence,
            reasoning=reasoning,
            entity_specific=entity_sentiment,
            aspects=aspects,
        )

    def _calculate_lexicon_sentiment(self, text: str) -> float:
        """Calculate sentiment using financial lexicon."""
        words = text.lower().split()
        sentiment_sum = 0.0
        word_count = 0

        for word in words:
            if word in self.financial_lexicon:
                sentiment_sum += self.financial_lexicon[word]
                word_count += 1

        return sentiment_sum / max(word_count, 1)

    async def _analyze_entity_sentiment(
        self, text: str, entities: list[Entity]
    ) -> dict[str, float]:
        """Analyze sentiment specific to each entity."""
        entity_sentiment = {}

        for entity in entities:
            if entity.label in ["ORG", "TICKER"]:
                # Extract context around entity
                start = max(0, entity.start - 100)
                end = min(len(text), entity.end + 100)
                context = text[start:end]

                # Analyze sentiment of context
                vader_scores = self.vader_analyzer.polarity_scores(context)
                entity_sentiment[entity.text] = vader_scores["compound"]

        return entity_sentiment

    def _analyze_aspect_sentiment(self, text: str) -> dict[str, float]:
        """Analyze sentiment for different aspects (earnings, management, etc.)."""
        aspects = {
            "earnings": ["earnings", "revenue", "profit", "income", "sales"],
            "management": ["ceo", "cfo", "management", "leadership", "executive"],
            "products": ["product", "service", "innovation", "technology"],
            "market": ["market", "competition", "share", "position"],
            "financial": ["debt", "cash", "balance sheet", "liquidity"],
        }

        aspect_sentiment = {}

        for aspect, keywords in aspects.items():
            aspect_score = 0.0
            found_keywords = 0

            for keyword in keywords:
                if keyword in text.lower():
                    # Extract context around keyword
                    pattern = r".{0,50}" + re.escape(keyword) + r".{0,50}"
                    matches = re.finditer(pattern, text.lower())

                    for match in matches:
                        context = match.group()
                        scores = self.vader_analyzer.polarity_scores(context)
                        aspect_score += scores["compound"]
                        found_keywords += 1

            if found_keywords > 0:
                aspect_sentiment[aspect] = aspect_score / found_keywords

        return aspect_sentiment

    def _generate_sentiment_reasoning(
        self,
        final_score: float,
        polarity: SentimentPolarity,
        vader_scores: dict,
        finbert_score: float,
    ) -> str:
        """Generate human-readable sentiment reasoning."""
        reasoning_parts = []

        reasoning_parts.append(
            f"Overall sentiment is {polarity.value} (score: {final_score:.3f})"
        )

        if abs(vader_scores["compound"]) > 0.5:
            reasoning_parts.append("Strong lexical sentiment indicators detected")

        if abs(finbert_score) > 0.7:
            reasoning_parts.append(
                f"Financial context suggests {polarity.value} sentiment"
            )

        if vader_scores["pos"] > 0.3:
            reasoning_parts.append(f"Positive terms: {vader_scores['pos']:.2f}")

        if vader_scores["neg"] > 0.3:
            reasoning_parts.append(f"Negative terms: {vader_scores['neg']:.2f}")

        return ". ".join(reasoning_parts)


class EventDetector:
    """Financial event detection from news text."""

    def __init__(self):
        self.event_patterns = self._load_event_patterns()
        self.impact_weights = self._load_impact_weights()

    def _load_event_patterns(self) -> dict[EventType, list[str]]:
        """Load event detection patterns."""
        return {
            EventType.EARNINGS: [
                r"earnings?\s+(?:report|results?|call)",
                r"quarterly?\s+(?:report|results?)",
                r"(?:beats?|misses?)\s+(?:expectations?|estimates?)",
                r"eps\s+of\s+\$[\d.]+",
                r"revenue\s+of\s+\$[\d.]+[bmk]?",
            ],
            EventType.MERGER_ACQUISITION: [
                r"(?:merges?\s+with|acquires?|acquisition\s+of)",
                r"takeover\s+(?:bid|offer)",
                r"buyout\s+(?:deal|offer)",
                r"\$[\d.]+[bmk]?\s+(?:deal|acquisition)",
            ],
            EventType.LEADERSHIP_CHANGE: [
                r"(?:ceo|cfo|president|chairman)\s+(?:steps\s+down|resigns?)",
                r"(?:appoints?|names?)\s+new\s+(?:ceo|cfo|president)",
                r"leadership\s+(?:change|transition)",
            ],
            EventType.REGULATORY: [
                r"(?:sec|fda|ftc)\s+(?:approves?|rejects?|investigates?)",
                r"regulatory\s+(?:approval|rejection)",
                r"compliance\s+(?:issue|violation)",
            ],
            EventType.DIVIDEND: [
                r"dividend\s+of\s+\$[\d.]+",
                r"(?:increases?|cuts?|suspends?)\s+dividend",
                r"(?:quarterly|annual)\s+dividend",
            ],
            EventType.IPO: [
                r"(?:files?\s+for\s+)?ipo",
                r"initial\s+public\s+offering",
                r"going\s+public",
            ],
        }

    def _load_impact_weights(self) -> dict[EventType, float]:
        """Load market impact weights for different events."""
        return {
            EventType.EARNINGS: 0.8,
            EventType.MERGER_ACQUISITION: 0.9,
            EventType.LEADERSHIP_CHANGE: 0.6,
            EventType.REGULATORY: 0.7,
            EventType.DIVIDEND: 0.5,
            EventType.IPO: 0.8,
            EventType.BANKRUPTCY: 1.0,
            EventType.LEGAL: 0.6,
            EventType.PRODUCT_LAUNCH: 0.4,
        }

    async def detect_events(self, text: str, entities: list[Entity]) -> list[Event]:
        """Detect financial events in text."""
        events = []

        for event_type, patterns in self.event_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    # Extract relevant entities near the event
                    event_entities = self._extract_event_entities(text, match, entities)

                    # Calculate confidence based on pattern specificity and context
                    confidence = self._calculate_event_confidence(pattern, match, text)

                    # Generate event description
                    description = self._generate_event_description(
                        event_type, match.group(), event_entities
                    )

                    # Calculate impact score
                    impact_score = self._calculate_impact_score(
                        event_type, event_entities, text
                    )

                    # Generate market implications
                    implications = self._generate_market_implications(
                        event_type, event_entities
                    )

                    event = Event(
                        event_type=event_type,
                        entities=event_entities,
                        description=description,
                        impact_score=impact_score,
                        confidence=confidence,
                        market_implications=implications,
                    )

                    events.append(event)

        # Remove duplicate events
        events = self._deduplicate_events(events)

        return events

    def _extract_event_entities(
        self, text: str, match: re.Match, entities: list[Entity]
    ) -> list[Entity]:
        """Extract entities relevant to the detected event."""
        event_entities = []
        context_window = 200

        start = max(0, match.start() - context_window)
        end = min(len(text), match.end() + context_window)

        for entity in entities:
            if start <= entity.start <= end or start <= entity.end <= end:
                event_entities.append(entity)

        return event_entities

    def _calculate_event_confidence(
        self, pattern: str, match: re.Match, text: str
    ) -> float:
        """Calculate confidence score for event detection."""
        base_confidence = 0.7

        # Adjust based on pattern specificity
        if r"\$[\d.]+" in pattern:  # Contains monetary amount
            base_confidence += 0.2

        if len(match.group()) > 10:  # Longer matches are more specific
            base_confidence += 0.1

        # Adjust based on context
        context_start = max(0, match.start() - 50)
        context_end = min(len(text), match.end() + 50)
        context = text[context_start:context_end].lower()

        supporting_terms = ["announces", "reports", "confirms", "official"]
        for term in supporting_terms:
            if term in context:
                base_confidence += 0.05

        return min(base_confidence, 1.0)

    def _generate_event_description(
        self, event_type: EventType, matched_text: str, entities: list[Entity]
    ) -> str:
        """Generate human-readable event description."""
        company_entities = [e for e in entities if e.label in ["ORG", "TICKER"]]

        if company_entities:
            company = company_entities[0].text
            return f"{company} - {event_type.value}: {matched_text}"
        else:
            return f"{event_type.value}: {matched_text}"

    def _calculate_impact_score(
        self, event_type: EventType, entities: list[Entity], text: str
    ) -> float:
        """Calculate potential market impact score."""
        base_impact = self.impact_weights.get(event_type, 0.5)

        # Adjust based on entity characteristics
        for entity in entities:
            if entity.label == "TICKER" and entity.sector:
                # Some sectors have higher impact
                if entity.sector in ["Technology", "Healthcare", "Financial Services"]:
                    base_impact += 0.1

        # Adjust based on sentiment indicators in text
        positive_indicators = ["beats", "exceeds", "strong", "growth"]
        negative_indicators = ["misses", "weak", "declines", "loss"]

        for indicator in positive_indicators:
            if indicator in text.lower():
                base_impact += 0.05

        for indicator in negative_indicators:
            if indicator in text.lower():
                base_impact += 0.1  # Negative events often have higher impact

        return min(base_impact, 1.0)

    def _generate_market_implications(
        self, event_type: EventType, entities: list[Entity]
    ) -> list[str]:
        """Generate potential market implications."""
        implications = []

        if event_type == EventType.EARNINGS:
            implications.extend(
                [
                    "Stock price volatility expected",
                    "Analyst rating revisions possible",
                    "Sector performance impact",
                ]
            )
        elif event_type == EventType.MERGER_ACQUISITION:
            implications.extend(
                [
                    "Target company stock premium",
                    "Acquiring company debt impact",
                    "Industry consolidation trend",
                ]
            )
        elif event_type == EventType.REGULATORY:
            implications.extend(
                [
                    "Compliance cost implications",
                    "Competitive landscape changes",
                    "Industry-wide regulatory review",
                ]
            )

        return implications

    def _deduplicate_events(self, events: list[Event]) -> list[Event]:
        """Remove duplicate or very similar events."""
        unique_events = []

        for event in events:
            is_duplicate = False
            for existing in unique_events:
                if (
                    event.event_type == existing.event_type
                    and abs(event.impact_score - existing.impact_score) < 0.2
                ):
                    # Check entity overlap
                    event_entities = {e.text for e in event.entities}
                    existing_entities = {e.text for e in existing.entities}
                    overlap = len(event_entities & existing_entities)

                    if overlap > 0:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_events.append(event)

        return unique_events


class TopicModeler:
    """Advanced topic modeling for financial news."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2)
        )
        self.lda_model = None
        self.topic_cache = {}

    async def extract_topics(
        self, documents: list[str], n_topics: int = 10
    ) -> list[Topic]:
        """Extract topics from a collection of documents."""
        if len(documents) < 2:
            return []

        # Preprocess documents
        processed_docs = [self._preprocess_document(doc) for doc in documents]

        # Vectorize documents
        doc_term_matrix = self.vectorizer.fit_transform(processed_docs)

        # Fit LDA model
        self.lda_model = LatentDirichletAllocation(
            n_components=n_topics, random_state=42, max_iter=10
        )

        self.lda_model.fit(doc_term_matrix)

        # Extract topics
        topics = []
        feature_names = self.vectorizer.get_feature_names_out()

        for topic_idx in range(n_topics):
            top_words_idx = self.lda_model.components_[topic_idx].argsort()[-10:][::-1]
            keywords = [feature_names[i] for i in top_words_idx]

            # Generate topic description
            description = self._generate_topic_description(keywords)

            # Calculate topic weight
            weight = float(self.lda_model.components_[topic_idx].sum())

            topic = Topic(
                topic_id=topic_idx,
                keywords=keywords,
                description=description,
                weight=weight,
            )

            topics.append(topic)

        return topics

    def _preprocess_document(self, document: str) -> str:
        """Preprocess document for topic modeling."""
        # Convert to lowercase
        doc = document.lower()

        # Remove special characters and digits
        doc = re.sub(r"[^a-zA-Z\s]", "", doc)

        # Remove extra whitespace
        doc = " ".join(doc.split())

        return doc

    def _generate_topic_description(self, keywords: list[str]) -> str:
        """Generate human-readable topic description."""
        if not keywords:
            return "General financial news"

        # Create description based on keywords
        primary_keywords = keywords[:3]

        if any(word in primary_keywords for word in ["earnings", "revenue", "profit"]):
            return "Earnings and Financial Performance"
        elif any(
            word in primary_keywords for word in ["merger", "acquisition", "deal"]
        ):
            return "Mergers and Acquisitions"
        elif any(
            word in primary_keywords for word in ["ceo", "management", "leadership"]
        ):
            return "Corporate Leadership and Management"
        elif any(
            word in primary_keywords for word in ["regulatory", "sec", "compliance"]
        ):
            return "Regulatory and Compliance"
        elif any(
            word in primary_keywords for word in ["technology", "innovation", "digital"]
        ):
            return "Technology and Innovation"
        else:
            return f"Financial News - {', '.join(primary_keywords[:2])}"


class NewsIntelligenceEngine:
    """Main news intelligence and NLP processing engine."""

    def __init__(self):
        self.entity_recognizer = FinancialEntityRecognizer()
        self.sentiment_analyzer = AdvancedSentimentAnalyzer()
        self.event_detector = EventDetector()
        self.topic_modeler = TopicModeler()
        self.db_path = "news_intelligence.db"
        self._setup_database()

    def _setup_database(self):
        """Setup news intelligence database."""
        conn = sqlite3.connect(self.db_path)

        # News articles table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_articles (
                article_id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                url TEXT,
                source TEXT,
                published_at TEXT,
                author TEXT,
                market_impact REAL,
                readability_score REAL,
                credibility_score REAL,
                metadata TEXT,
                created_at TEXT
            )
        """
        )

        # Entities table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                article_id TEXT,
                text TEXT,
                label TEXT,
                start_pos INTEGER,
                end_pos INTEGER,
                confidence REAL,
                ticker TEXT,
                sector TEXT,
                metadata TEXT
            )
        """
        )

        # Sentiment analysis table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiments (
                sentiment_id TEXT PRIMARY KEY,
                article_id TEXT,
                polarity TEXT,
                score REAL,
                confidence TEXT,
                reasoning TEXT,
                entity_specific TEXT,
                aspects TEXT
            )
        """
        )

        # Events table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                article_id TEXT,
                event_type TEXT,
                description TEXT,
                impact_score REAL,
                confidence REAL,
                timeframe TEXT,
                market_implications TEXT
            )
        """
        )

        # News insights table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_insights (
                insight_id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                key_points TEXT,
                affected_entities TEXT,
                market_implications TEXT,
                sentiment_overview TEXT,
                confidence_score REAL,
                generated_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def process_article(
        self,
        title: str,
        content: str,
        url: str,
        source: str,
        published_at: datetime,
        author: str | None = None,
    ) -> NewsArticle:
        """Process a single news article through the full NLP pipeline."""
        article_id = str(uuid.uuid4())

        # Combine title and content for processing
        full_text = f"{title}. {content}"

        # Entity extraction
        entities = await self.entity_recognizer.extract_entities(full_text)

        # Sentiment analysis
        sentiment = await self.sentiment_analyzer.analyze_sentiment(full_text, entities)

        # Event detection
        events = await self.event_detector.detect_events(full_text, entities)

        # Calculate additional metrics
        market_impact = self._calculate_market_impact(entities, events, sentiment)
        readability_score = self._calculate_readability(content)
        credibility_score = self._calculate_credibility(source, author, content)

        # Create article object
        article = NewsArticle(
            article_id=article_id,
            title=title,
            content=content,
            url=url,
            source=source,
            published_at=published_at,
            author=author,
            entities=entities,
            sentiment=sentiment,
            events=events,
            market_impact=market_impact,
            readability_score=readability_score,
            credibility_score=credibility_score,
        )

        # Store in database
        await self._store_article(article)

        return article

    async def generate_market_insights(
        self, articles: list[NewsArticle], timeframe_hours: int = 24
    ) -> NewsInsight:
        """Generate AI-powered market insights from a collection of articles."""

        # Filter articles by timeframe
        cutoff_time = datetime.now() - timedelta(hours=timeframe_hours)
        recent_articles = [a for a in articles if a.published_at >= cutoff_time]

        if not recent_articles:
            return None

        # Aggregate analysis
        all_entities = []
        all_events = []
        sentiment_scores = []

        for article in recent_articles:
            all_entities.extend(article.entities)
            all_events.extend(article.events)
            if article.sentiment:
                sentiment_scores.append(article.sentiment.score)

        # Find most mentioned entities
        entity_counts = Counter(
            [e.text for e in all_entities if e.label in ["ORG", "TICKER"]]
        )
        top_entities = [entity for entity, count in entity_counts.most_common(10)]

        # Aggregate sentiment
        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0.0
        sentiment_overview = self._generate_sentiment_overview(
            avg_sentiment, sentiment_scores
        )

        # Extract key themes
        article_contents = [a.content for a in recent_articles]
        topics = await self.topic_modeler.extract_topics(article_contents, n_topics=5)

        # Generate key points
        key_points = self._generate_key_points(all_events, topics, top_entities)

        # Generate market implications
        market_implications = self._generate_market_implications(
            all_events, sentiment_scores
        )

        # Generate summary
        summary = self._generate_insights_summary(
            len(recent_articles), top_entities, sentiment_overview, key_points
        )

        # Calculate confidence score
        confidence_score = self._calculate_insights_confidence(
            recent_articles, entity_counts, sentiment_scores
        )

        insight = NewsInsight(
            insight_id=str(uuid.uuid4()),
            title=f"Market Intelligence Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            summary=summary,
            key_points=key_points,
            affected_entities=top_entities,
            market_implications=market_implications,
            sentiment_overview=sentiment_overview,
            confidence_score=confidence_score,
        )

        # Store insight
        await self._store_insight(insight)

        return insight

    def _calculate_market_impact(
        self, entities: list[Entity], events: list[Event], sentiment: Sentiment
    ) -> float:
        """Calculate potential market impact score."""
        base_impact = 0.1

        # Entity impact
        for entity in entities:
            if entity.label == "TICKER":
                base_impact += 0.2
            elif entity.label == "ORG":
                base_impact += 0.1

        # Event impact
        for event in events:
            base_impact += event.impact_score * 0.3

        # Sentiment impact
        sentiment_multiplier = abs(sentiment.score) if sentiment else 0
        base_impact *= 1 + sentiment_multiplier

        return min(base_impact, 1.0)

    def _calculate_readability(self, content: str) -> float:
        """Calculate text readability score (simplified)."""
        if not content:
            return 0.0

        sentences = content.count(".") + content.count("!") + content.count("?")
        words = len(content.split())

        if sentences == 0:
            return 0.0

        avg_words_per_sentence = words / sentences

        # Flesch reading ease approximation
        if avg_words_per_sentence <= 10:
            return 0.9
        elif avg_words_per_sentence <= 15:
            return 0.7
        elif avg_words_per_sentence <= 20:
            return 0.5
        else:
            return 0.3

    def _calculate_credibility(
        self, source: str, author: str | None, content: str
    ) -> float:
        """Calculate source credibility score."""
        base_credibility = 0.5

        # Source reputation (simplified)
        reputable_sources = {
            "reuters": 0.9,
            "bloomberg": 0.9,
            "wsj": 0.9,
            "ft": 0.9,
            "cnbc": 0.8,
            "marketwatch": 0.7,
            "yahoo finance": 0.6,
        }

        source_lower = source.lower()
        for rep_source, score in reputable_sources.items():
            if rep_source in source_lower:
                base_credibility = score
                break

        # Content quality indicators
        if author:
            base_credibility += 0.1

        if len(content) > 500:  # Substantial content
            base_credibility += 0.1

        # Look for quality indicators
        quality_indicators = ["according to", "reported", "confirmed", "disclosed"]
        for indicator in quality_indicators:
            if indicator in content.lower():
                base_credibility += 0.05
                break

        return min(base_credibility, 1.0)

    def _generate_sentiment_overview(
        self, avg_sentiment: float, sentiment_scores: list[float]
    ) -> str:
        """Generate sentiment overview text."""
        if not sentiment_scores:
            return "No sentiment data available"

        volatility = np.std(sentiment_scores) if len(sentiment_scores) > 1 else 0

        if avg_sentiment >= 0.3:
            base = "Overall market sentiment is positive"
        elif avg_sentiment >= -0.3:
            base = "Market sentiment is neutral"
        else:
            base = "Overall market sentiment is negative"

        if volatility > 0.4:
            base += " with high volatility in opinions"
        elif volatility > 0.2:
            base += " with moderate variation in opinions"
        else:
            base += " with consistent sentiment across sources"

        return base

    def _generate_key_points(
        self, events: list[Event], topics: list[Topic], top_entities: list[str]
    ) -> list[str]:
        """Generate key points from analysis."""
        points = []

        # Event-based points
        event_types = Counter([e.event_type for e in events])
        for event_type, count in event_types.most_common(3):
            points.append(f"{count} {event_type.value} events detected")

        # Topic-based points
        for topic in topics[:3]:
            points.append(f"Key theme: {topic.description}")

        # Entity-based points
        if top_entities:
            points.append(f"Most mentioned: {', '.join(top_entities[:3])}")

        return points[:5]  # Limit to 5 key points

    def _generate_market_implications(
        self, events: list[Event], sentiment_scores: list[float]
    ) -> list[str]:
        """Generate market implications."""
        implications = []

        # High-impact events
        high_impact_events = [e for e in events if e.impact_score > 0.7]
        if high_impact_events:
            implications.append(
                f"{len(high_impact_events)} high-impact events may cause market volatility"
            )

        # Sentiment implications
        if sentiment_scores:
            avg_sentiment = np.mean(sentiment_scores)
            if avg_sentiment > 0.5:
                implications.append("Positive sentiment may drive buying interest")
            elif avg_sentiment < -0.5:
                implications.append("Negative sentiment may trigger selling pressure")

        # Event-specific implications
        for event in events[:3]:  # Top 3 events
            implications.extend(
                event.market_implications[:1]
            )  # One implication per event

        return implications[:5]  # Limit to 5 implications

    def _generate_insights_summary(
        self,
        article_count: int,
        top_entities: list[str],
        sentiment_overview: str,
        key_points: list[str],
    ) -> str:
        """Generate comprehensive insights summary."""
        summary_parts = [
            f"Analysis of {article_count} recent news articles reveals:",
            sentiment_overview + ".",
            (
                f"Key developments involve {', '.join(top_entities[:3])}."
                if top_entities
                else ""
            ),
            f"Main themes include {key_points[0] if key_points else 'general market activity'}.",
        ]

        return " ".join([part for part in summary_parts if part])

    def _calculate_insights_confidence(
        self,
        articles: list[NewsArticle],
        entity_counts: Counter,
        sentiment_scores: list[float],
    ) -> float:
        """Calculate confidence score for insights."""
        base_confidence = 0.5

        # More articles = higher confidence
        if len(articles) >= 10:
            base_confidence += 0.2
        elif len(articles) >= 5:
            base_confidence += 0.1

        # Entity consistency
        if entity_counts and entity_counts.most_common(1)[0][1] >= 3:
            base_confidence += 0.1

        # Sentiment consistency
        if sentiment_scores and np.std(sentiment_scores) < 0.3:
            base_confidence += 0.1

        # Source diversity
        sources = {a.source for a in articles}
        if len(sources) >= 3:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    async def _store_article(self, article: NewsArticle):
        """Store processed article in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Store article
            conn.execute(
                """
                INSERT OR REPLACE INTO news_articles
                (article_id, title, content, url, source, published_at, author,
                 market_impact, readability_score, credibility_score, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    article.article_id,
                    article.title,
                    article.content,
                    article.url,
                    article.source,
                    article.published_at.isoformat(),
                    article.author,
                    article.market_impact,
                    article.readability_score,
                    article.credibility_score,
                    json.dumps(article.metadata),
                    datetime.now().isoformat(),
                ),
            )

            # Store entities
            for entity in article.entities:
                entity_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO entities
                    (entity_id, article_id, text, label, start_pos, end_pos,
                     confidence, ticker, sector, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entity_id,
                        article.article_id,
                        entity.text,
                        entity.label,
                        entity.start,
                        entity.end,
                        entity.confidence,
                        entity.ticker,
                        entity.sector,
                        json.dumps(entity.metadata),
                    ),
                )

            # Store sentiment
            if article.sentiment:
                sentiment_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO sentiments
                    (sentiment_id, article_id, polarity, score, confidence,
                     reasoning, entity_specific, aspects)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        sentiment_id,
                        article.article_id,
                        article.sentiment.polarity.value,
                        article.sentiment.score,
                        article.sentiment.confidence.value,
                        article.sentiment.reasoning,
                        json.dumps(article.sentiment.entity_specific),
                        json.dumps(article.sentiment.aspects),
                    ),
                )

            # Store events
            for event in article.events:
                event_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO events
                    (event_id, article_id, event_type, description, impact_score,
                     confidence, timeframe, market_implications)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event_id,
                        article.article_id,
                        event.event_type.value,
                        event.description,
                        event.impact_score,
                        event.confidence,
                        event.timeframe,
                        json.dumps(event.market_implications),
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing article: {e}")

    async def _store_insight(self, insight: NewsInsight):
        """Store news insight in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT INTO news_insights
                (insight_id, title, summary, key_points, affected_entities,
                 market_implications, sentiment_overview, confidence_score, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    insight.insight_id,
                    insight.title,
                    insight.summary,
                    json.dumps(insight.key_points),
                    json.dumps(insight.affected_entities),
                    json.dumps(insight.market_implications),
                    insight.sentiment_overview,
                    insight.confidence_score,
                    insight.generated_at.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing insight: {e}")

    async def get_entity_sentiment_timeline(
        self, entity: str, days: int = 30
    ) -> dict[str, Any]:
        """Get sentiment timeline for a specific entity."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Query sentiment data for entity
            query = """
                SELECT a.published_at, s.score, s.polarity
                FROM news_articles a
                JOIN sentiments s ON a.article_id = s.article_id
                JOIN entities e ON a.article_id = e.article_id
                WHERE (e.text = ? OR e.ticker = ?)
                AND a.published_at >= ?
                ORDER BY a.published_at
            """

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            cursor = conn.execute(query, (entity, entity, cutoff_date))
            results = cursor.fetchall()

            conn.close()

            # Process results
            timeline = []
            for published_at, score, polarity in results:
                timeline.append(
                    {
                        "date": published_at,
                        "sentiment_score": score,
                        "polarity": polarity,
                    }
                )

            # Calculate statistics
            scores = [r[1] for r in results]
            avg_sentiment = np.mean(scores) if scores else 0
            sentiment_trend = self._calculate_sentiment_trend(scores)

            return {
                "entity": entity,
                "timeline": timeline,
                "average_sentiment": avg_sentiment,
                "sentiment_trend": sentiment_trend,
                "data_points": len(timeline),
            }

        except Exception as e:
            logger.error(f"Error getting entity sentiment timeline: {e}")
            return {}

    def _calculate_sentiment_trend(self, scores: list[float]) -> str:
        """Calculate sentiment trend direction."""
        if len(scores) < 2:
            return "insufficient_data"

        # Simple linear trend
        x = np.arange(len(scores))
        slope = np.polyfit(x, scores, 1)[0]

        if slope > 0.05:
            return "improving"
        elif slope < -0.05:
            return "deteriorating"
        else:
            return "stable"


# Example usage and testing
async def main():
    """Example usage of the News Intelligence Engine."""

    # Initialize engine
    engine = NewsIntelligenceEngine()

    # Sample news articles for testing
    sample_articles = [
        {
            "title": "Apple Reports Strong Q4 Earnings, Beats Analyst Expectations",
            "content": """Apple Inc. (AAPL) today announced financial results for its fiscal 2024 fourth quarter.
                       The company posted quarterly revenue of $94.9 billion, up 6% year over year, and quarterly
                       earnings per share of $1.64, which beat analyst expectations of $1.60. iPhone revenue was
                       $46.2 billion, up 5% from the prior year. CEO Tim Cook expressed optimism about the company's
                       AI initiatives and upcoming product launches.""",
            "url": "https://example.com/apple-earnings",
            "source": "Reuters",
            "published_at": datetime.now() - timedelta(hours=2),
            "author": "John Smith",
        },
        {
            "title": "Tesla Stock Surges on Strong Delivery Numbers",
            "content": """Tesla (TSLA) shares rose 8% in after-hours trading following the company's announcement
                       of record quarterly deliveries. The electric vehicle maker delivered 466,140 vehicles in Q4,
                       surpassing analyst estimates of 454,000. The strong performance was driven by increased
                       production at Tesla's Shanghai and Berlin factories. Analysts expect this momentum to continue
                       into 2024.""",
            "url": "https://example.com/tesla-deliveries",
            "source": "Bloomberg",
            "published_at": datetime.now() - timedelta(hours=4),
            "author": "Jane Doe",
        },
        {
            "title": "Microsoft Announces Major Azure Partnership",
            "content": """Microsoft Corporation (MSFT) today announced a strategic partnership with leading cloud
                       infrastructure provider. The deal, valued at over $2 billion, will expand Microsoft's Azure
                       cloud services globally. The partnership is expected to boost Microsoft's competitive position
                       against Amazon Web Services and Google Cloud Platform. Microsoft's stock gained 3% on the news.""",
            "url": "https://example.com/microsoft-partnership",
            "source": "CNBC",
            "published_at": datetime.now() - timedelta(hours=6),
            "author": "Tech Reporter",
        },
    ]

    # Process articles
    processed_articles = []
    print("Processing news articles...")

    for article_data in sample_articles:
        print(f"\nProcessing: {article_data['title']}")

        article = await engine.process_article(
            title=article_data["title"],
            content=article_data["content"],
            url=article_data["url"],
            source=article_data["source"],
            published_at=article_data["published_at"],
            author=article_data["author"],
        )

        processed_articles.append(article)

        # Display results
        print(f"  Entities found: {len(article.entities)}")
        for entity in article.entities[:3]:  # Show first 3
            print(f"    - {entity.text} ({entity.label})")

        if article.sentiment:
            print(
                f"  Sentiment: {article.sentiment.polarity.value} (score: {article.sentiment.score:.3f})"
            )

        print(f"  Events detected: {len(article.events)}")
        for event in article.events:
            print(f"    - {event.event_type.value}: {event.description}")

        print(f"  Market impact: {article.market_impact:.3f}")
        print(f"  Credibility: {article.credibility_score:.3f}")

    # Generate market insights
    print("\n" + "=" * 60)
    print("GENERATING MARKET INSIGHTS")
    print("=" * 60)

    insight = await engine.generate_market_insights(
        processed_articles, timeframe_hours=24
    )

    if insight:
        print(f"\nTitle: {insight.title}")
        print(f"\nSummary: {insight.summary}")

        print("\nKey Points:")
        for point in insight.key_points:
            print(f"  • {point}")

        print(f"\nAffected Entities: {', '.join(insight.affected_entities)}")

        print("\nMarket Implications:")
        for implication in insight.market_implications:
            print(f"  • {implication}")

        print(f"\nSentiment Overview: {insight.sentiment_overview}")
        print(f"Confidence Score: {insight.confidence_score:.3f}")

    # Test entity sentiment timeline
    print("\n" + "=" * 60)
    print("ENTITY SENTIMENT TIMELINE")
    print("=" * 60)

    timeline = await engine.get_entity_sentiment_timeline("AAPL", days=30)
    if timeline:
        print(f"\nEntity: {timeline['entity']}")
        print(f"Average Sentiment: {timeline['average_sentiment']:.3f}")
        print(f"Trend: {timeline['sentiment_trend']}")
        print(f"Data Points: {timeline['data_points']}")


if __name__ == "__main__":
    asyncio.run(main())
