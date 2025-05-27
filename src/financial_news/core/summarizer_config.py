#!/usr/bin/env python3
"""
Configuration management for Financial News Summarizer.
Extracted from summarizer.py for better modularity.
"""

import functools
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import colorlog
import dotenv
import yaml

# Load environment variables
dotenv.load_dotenv()


# Configure enhanced logging with caching
@functools.lru_cache(maxsize=1)
def setup_logging():
    """Setup enhanced logging with colors - cached for performance."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )

    logger = logging.getLogger("enhanced_news_summarizer")
    if not logger.handlers:  # Avoid duplicate handlers
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    return logger


logger = setup_logging()


# Enhanced configuration class with slots for memory optimization
@dataclass
class Config:
    """Enhanced configuration management with dataclass for better performance."""

    __slots__ = ("_config_cache", "config", "config_path")

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config_cache = None
        self.config = self._load_config()
        self._validate_config()

    @functools.cached_property
    def _loaded_config(self) -> dict:
        """Load configuration from YAML file - cached as property."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            return self._get_default_config()

    def _load_config(self) -> dict:
        """Load configuration using cached property."""
        return self._loaded_config

    @staticmethod
    def _get_default_config() -> dict:
        """Get default configuration if file is missing."""
        return {
            "queries": ["AAPL", "MSFT", "GOOGL"],
            "ai": {"model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 500},
            "processing": {"max_articles": 25, "concurrent_requests": 5},
        }

    def _validate_config(self):
        """Validate configuration."""
        required_keys = ["queries", "ai", "processing"]
        for key in required_keys:
            if key not in self.config:
                logger.warning(f"⚠️  Missing config section: {key}")

    def get(self, key: str, default=None):
        """Get configuration value with dot notation - using instance cache."""
        if not hasattr(self, "_get_cache"):
            self._get_cache = {}

        if key in self._get_cache:
            return self._get_cache[key]

        keys = key.split(".")
        value = self.config
        try:
            for k in keys:
                value = value[k]
            self._get_cache[key] = value
            return value
        except (KeyError, TypeError):
            self._get_cache[key] = default
            return default
