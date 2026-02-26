#!/usr/bin/env python3
"""
Unit tests for Article model.
"""

import pytest
from datetime import datetime

from financial_news.models.article import Article


class TestArticle:
    """Test suite for Article model."""

    def test_article_initialization(self):
        """Test article initialization and auto-populated fields."""
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
            published_at="2023-01-01T12:00:00Z",
            content="This is a test article with some content for testing.",
        )

        # Check auto-populated fields
        assert article.id is not None
        assert len(article.id) == 32  # MD5 hash length
        assert article.word_count == 10  # Number of words in content

        # Check default values
        assert article.summary_bullets == []
        assert article.key_entities == []
        assert article.topics == []
        assert article.summarized_headline is None
        assert article.sentiment is None

    def test_article_equality(self):
        """Test that articles with same ID are considered equal."""
        article1 = Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
            published_at="2023-01-01T12:00:00Z",
            content="This is a test article.",
        )

        article2 = Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
            published_at="2023-01-01T12:00:00Z",
            content="This is a test article with different content.",
        )

        # Same title and URL should produce same ID
        assert article1.id == article2.id
        assert hash(article1) == hash(article2)

    def test_article_serialization(self):
        """Test article serialization to and from dict."""
        original = Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
            published_at="2023-01-01T12:00:00Z",
            content="This is a test article.",
        )
        
        # Add some processed data
        original.summarized_headline = "Test Summary"
        original.summary_bullets = ["Point 1", "Point 2"]
        original.sentiment = "positive"
        original.sentiment_score = 0.85
        original.processed_at = datetime.now()
        original.processing_time = 1.25

        # Convert to dict and back
        article_dict = original.to_dict()
        recreated = Article.from_dict(article_dict)

        # Check equality of key fields
        assert recreated.id == original.id
        assert recreated.title == original.title
        assert recreated.url == original.url
        assert recreated.summarized_headline == original.summarized_headline
        assert recreated.summary_bullets == original.summary_bullets
        assert recreated.sentiment == original.sentiment
        assert recreated.sentiment_score == original.sentiment_score
        assert recreated.processed_at is not None

    def test_long_content_truncation(self):
        """Test that long content is truncated in to_dict()."""
        long_content = "a" * 1000
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
            published_at="2023-01-01T12:00:00Z",
            content=long_content,
        )
        
        article_dict = article.to_dict()
        assert len(article_dict["content"]) < 1000
        assert article_dict["content"].endswith("...")
