"""
Test configuration and fixtures for Financial News application.

This module provides common test fixtures and configuration for pytest.
"""

import pytest
import sys
from pathlib import Path

# Add src to Python path for testing
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from financial_news.config.settings import Settings


@pytest.fixture
def test_settings():
    """Provide test-specific settings."""
    settings = Settings()
    settings.environment = "test"
    settings.debug = True
    settings.database.name = "financial_news_test"
    return settings


@pytest.fixture
def sample_news_data():
    """Provide sample news data for testing."""
    return {
        "title": "Test News Article",
        "content": "This is a test news article content for testing purposes.",
        "source": "Test Source",
        "published_at": "2024-01-01T00:00:00Z",
        "url": "https://example.com/test-article",
        "sentiment": 0.5,
        "summary": "Test summary"
    }


@pytest.fixture
def sample_market_data():
    """Provide sample market data for testing."""
    return {
        "symbol": "AAPL",
        "price": 150.00,
        "change": 2.50,
        "change_percent": 1.69,
        "volume": 1000000,
        "timestamp": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def mock_api_response():
    """Provide mock API response data."""
    return {
        "status": "success",
        "data": {
            "articles": [
                {
                    "title": "Mock Article 1",
                    "content": "Mock content 1",
                    "source": "Mock Source 1"
                },
                {
                    "title": "Mock Article 2", 
                    "content": "Mock content 2",
                    "source": "Mock Source 2"
                }
            ]
        }
    } 