"""
Financial News - Advanced Financial News Analysis and Summarization Platform.

This package provides comprehensive tools for financial news analysis, including:
- Real-time news aggregation and processing
- Advanced sentiment analysis using transformer models
- Intelligent summarization and key insights extraction
- Interactive dashboard and visualization
- RESTful API for integration
- Command-line interface for automation

Main Components:
- Core: Business logic for analysis and summarization
- Models: Machine learning models and data schemas
- Services: External API integrations and real-time streaming
- API: Web API endpoints and middleware
- CLI: Command-line interface
- Dashboard: Interactive web dashboard
- Utils: Utility functions and helpers
"""

__version__ = "1.0.0"
__author__ = "Financial News Team"
__email__ = "team@financialnews.com"

# Import main components for easy access
from .config.settings import get_settings, Settings
from .config.logging import setup_logging, get_logger

# Package metadata
__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "get_settings",
    "Settings",
    "setup_logging",
    "get_logger",
]
