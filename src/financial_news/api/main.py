#!/usr/bin/env python3
"""
Financial News API
FastAPI backend for the Financial News Analysis Platform.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import our models and services
from financial_news.config.settings import get_settings
from financial_news.models.article import Article
from financial_news.core.summarizer_config import Config, setup_logging
from financial_news.core.sentiment import analyze_article_sentiment, get_sentiment_analyzer

# Set up logging
logger = setup_logging()

# Initialize settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Financial News API",
    description="API for Financial News Analysis Platform",
    version="1.0.0",
)

# Add CORS middleware to allow requests from the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define API models
class ArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str
    summarized_headline: Optional[str] = None
    summary_bullets: List[str] = []
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    market_impact_score: Optional[float] = None
    key_entities: List[str] = []
    topics: List[str] = []


class AnalyticsResponse(BaseModel):
    sentiment_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    top_entities: List[Dict[str, int]]
    top_topics: List[Dict[str, int]]
    processing_stats: Dict[str, float]


# Mock data for initial testing
def get_mock_articles() -> List[Article]:
    """Generate mock articles for testing."""
    articles = [
        Article(
            title="Apple Reports Record Profits in Q3",
            url="https://example.com/apple-profits",
            source="Financial Times",
            published_at="2025-05-27T10:00:00Z",
            content="Apple Inc. reported record profits in the third quarter, exceeding analyst expectations...",
        ),
        Article(
            title="Tesla Announces New Battery Technology",
            url="https://example.com/tesla-battery",
            source="Bloomberg",
            published_at="2025-05-26T15:30:00Z",
            content="Tesla unveiled a new battery technology that extends vehicle range by 50%...",
        ),
        Article(
            title="Federal Reserve Signals Interest Rate Cut",
            url="https://example.com/fed-rate-cut",
            source="Wall Street Journal",
            published_at="2025-05-25T12:15:00Z",
            content="The Federal Reserve indicated it may cut interest rates in the next meeting...",
        ),
    ]
    
    # Add mock analysis data
    for i, article in enumerate(articles):
        article.summarized_headline = f"Summary: {article.title}"
        article.summary_bullets = [f"Key point {j+1}" for j in range(3)]
        article.sentiment = ["positive", "neutral", "negative"][i % 3]
        article.sentiment_score = 0.7 if article.sentiment == "positive" else 0.5 if article.sentiment == "neutral" else 0.2
        article.market_impact_score = 0.8 - (i * 0.2)
        article.key_entities = ["Apple", "NASDAQ"] if i == 0 else ["Tesla", "Battery"] if i == 1 else ["Federal Reserve", "Interest Rates"]
        article.topics = ["Technology", "Earnings"] if i == 0 else ["Technology", "Innovation"] if i == 1 else ["Economy", "Policy"]
        article.processed_at = datetime.now()
        
    return articles


# API routes
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {"message": "Financial News API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/articles", response_model=List[ArticleResponse])
async def get_articles(
    limit: int = Query(10, ge=1, le=100),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(None, enum=["date", "relevance", "sentiment"]),
    sort_order: Optional[str] = Query("desc", enum=["asc", "desc"]),
):
    """Get articles with optional filtering and sorting."""
    # In a real implementation, this would fetch from a database
    articles = get_mock_articles()
    
    # Apply filters
    if source:
        articles = [a for a in articles if a.source.lower() == source.lower()]
    if sentiment:
        articles = [a for a in articles if a.sentiment == sentiment]
    if topic:
        articles = [a for a in articles if topic in a.topics]
    
    # Apply search
    if search:
        search_lower = search.lower()
        articles = [a for a in articles if 
                    search_lower in a.title.lower() or 
                    search_lower in a.content.lower() or
                    any(search_lower in entity.lower() for entity in a.key_entities) or
                    any(search_lower in topic.lower() for topic in a.topics)]
    
    # Apply sorting
    if sort_by:
        reverse = sort_order.lower() == "desc"
        if sort_by == "date":
            articles = sorted(articles, key=lambda a: a.published_at, reverse=reverse)
        elif sort_by == "relevance":
            # For relevance, we'd need a real scoring algorithm, but for mock data we'll use the market impact
            articles = sorted(articles, key=lambda a: a.market_impact_score or 0, reverse=reverse)
        elif sort_by == "sentiment":
            articles = sorted(articles, key=lambda a: a.sentiment_score or 0, reverse=reverse)
    
    # Apply limit
    articles = articles[:limit]
    
    return [ArticleResponse(**article.to_dict()) for article in articles]


@app.get("/api/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str):
    """Get a specific article by ID."""
    articles = get_mock_articles()
    for article in articles:
        if article.id == article_id:
            return ArticleResponse(**article.to_dict())
    
    raise HTTPException(status_code=404, detail="Article not found")


@app.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    """Get analytics data."""
    # Mock analytics data
    analytics = {
        "sentiment_distribution": {"positive": 42, "neutral": 28, "negative": 14},
        "source_distribution": {
            "Financial Times": 25, 
            "Bloomberg": 22, 
            "Wall Street Journal": 18, 
            "Reuters": 12, 
            "CNBC": 7
        },
        "top_entities": [
            {"name": "Apple", "count": 15},
            {"name": "Tesla", "count": 12},
            {"name": "Federal Reserve", "count": 10},
            {"name": "Microsoft", "count": 8},
            {"name": "Amazon", "count": 7},
        ],
        "top_topics": [
            {"name": "Technology", "count": 28},
            {"name": "Economy", "count": 22},
            {"name": "Markets", "count": 18},
            {"name": "Policy", "count": 12},
            {"name": "Earnings", "count": 10},
        ],
        "processing_stats": {
            "avg_processing_time": 1.5,
            "articles_processed": 84,
            "last_update": datetime.now().timestamp(),
        }
    }
    
    return analytics


@app.get("/api/sources")
async def get_sources():
    """Get available news sources."""
    # Mock data
    sources = [
        {"id": "financial-times", "name": "Financial Times"},
        {"id": "bloomberg", "name": "Bloomberg"},
        {"id": "wall-street-journal", "name": "Wall Street Journal"},
        {"id": "reuters", "name": "Reuters"},
        {"id": "cnbc", "name": "CNBC"},
    ]
    return sources


@app.get("/api/topics")
async def get_topics():
    """Get available topics."""
    # Mock data
    topics = [
        {"id": "technology", "name": "Technology"},
        {"id": "economy", "name": "Economy"},
        {"id": "markets", "name": "Markets"},
        {"id": "policy", "name": "Policy"},
        {"id": "earnings", "name": "Earnings"},
    ]
    return topics


@app.post("/api/analyze/sentiment")
async def analyze_sentiment(data: Dict):
    """Analyze sentiment for provided text."""
    if "text" not in data:
        raise HTTPException(status_code=400, detail="Text field is required")
        
    text = data["text"]
    result = analyze_article_sentiment(text)
    return result


@app.get("/api/user/settings")
async def get_user_settings():
    """Get user settings."""
    # Mock user settings
    settings = {
        "darkMode": True,
        "autoRefresh": False,
        "refreshInterval": 5,  # minutes
        "defaultFilters": {
            "sources": [],
            "topics": [],
            "sentiment": ""
        },
        "emailAlerts": {
            "enabled": False,
            "frequency": "daily",
            "keywords": []
        },
        "visualization": {
            "chartType": "bar",
            "colorScheme": "default"
        }
    }
    return settings


@app.post("/api/user/settings")
async def update_user_settings(settings: Dict):
    """Update user settings."""
    # In a real app, we would save these to a database
    # For this mock, we'll just return the settings
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "settings": settings
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
