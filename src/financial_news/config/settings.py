"""
Configuration settings for Financial News application.

This module provides centralized configuration management using environment variables
and configuration files.
"""

import os
import toml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str = "localhost"
    port: int = 5432
    name: str = "financial_news"
    user: str = "postgres"
    password: str = ""
    
    @property
    def url(self) -> str:
        """Get database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class APIConfig:
    """API configuration settings."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: ["*"])
    rate_limit: str = "100/minute"


@dataclass
class NewsSourcesConfig:
    """News sources configuration."""
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    news_api_key: str = ""
    polygon_api_key: str = ""
    refresh_interval: int = 300  # seconds


@dataclass
class MLConfig:
    """Machine learning configuration."""
    model_cache_dir: str = "./models"
    sentiment_model: str = "finbert"
    summarization_model: str = "facebook/bart-large-cnn"
    max_sequence_length: int = 512
    batch_size: int = 16


@dataclass
class WebSocketConfig:
    """WebSocket configuration."""
    host: str = "0.0.0.0"
    port: int = 8001
    max_connections: int = 100
    heartbeat_interval: int = 30


@dataclass
class Settings:
    """Main application settings."""
    app_name: str = "Financial News"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    secret_key: str = ""
    
    # Component configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    news_sources: NewsSourcesConfig = field(default_factory=NewsSourcesConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        settings = cls()
        
        # App settings
        settings.app_name = os.getenv("APP_NAME", settings.app_name)
        settings.version = os.getenv("APP_VERSION", settings.version)
        settings.environment = os.getenv("ENVIRONMENT", settings.environment)
        settings.debug = os.getenv("DEBUG", "true").lower() == "true"
        settings.secret_key = os.getenv("SECRET_KEY", settings.secret_key)
        
        # Database settings
        settings.database.host = os.getenv("DB_HOST", settings.database.host)
        settings.database.port = int(os.getenv("DB_PORT", str(settings.database.port)))
        settings.database.name = os.getenv("DB_NAME", settings.database.name)
        settings.database.user = os.getenv("DB_USER", settings.database.user)
        settings.database.password = os.getenv("DB_PASSWORD", settings.database.password)
        
        # API settings
        settings.api.host = os.getenv("API_HOST", settings.api.host)
        settings.api.port = int(os.getenv("API_PORT", str(settings.api.port)))
        settings.api.debug = os.getenv("API_DEBUG", str(settings.api.debug)).lower() == "true"
        
        # News sources
        settings.news_sources.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        settings.news_sources.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")
        settings.news_sources.news_api_key = os.getenv("NEWS_API_KEY", "")
        settings.news_sources.polygon_api_key = os.getenv("POLYGON_API_KEY", "")
        
        # ML settings
        settings.ml.model_cache_dir = os.getenv("MODEL_CACHE_DIR", settings.ml.model_cache_dir)
        settings.ml.sentiment_model = os.getenv("SENTIMENT_MODEL", settings.ml.sentiment_model)
        settings.ml.summarization_model = os.getenv("SUMMARIZATION_MODEL", settings.ml.summarization_model)
        
        # WebSocket settings
        settings.websocket.host = os.getenv("WS_HOST", settings.websocket.host)
        settings.websocket.port = int(os.getenv("WS_PORT", str(settings.websocket.port)))
        
        return settings
    
    @classmethod
    def from_toml(cls, config_path: Optional[str] = None) -> "Settings":
        """Create settings from TOML configuration file."""
        if config_path is None:
            # Try to find config file
            possible_paths = [
                "pyproject.toml",
                "config/development.yaml",
                "config/production.yaml"
            ]
            config_path = next((p for p in possible_paths if Path(p).exists()), None)
        
        if config_path and Path(config_path).exists():
            if config_path.endswith('.toml'):
                config_data = toml.load(config_path)
                # Extract financial_news specific config if it exists
                if 'financial_news' in config_data:
                    config_data = config_data['financial_news']
            else:
                # For YAML files, we'd need PyYAML
                config_data = {}
        else:
            config_data = {}
        
        # Start with environment settings
        settings = cls.from_env()
        
        # Override with config file values
        if config_data:
            for key, value in config_data.items():
                if hasattr(settings, key):
                    if isinstance(getattr(settings, key), (DatabaseConfig, APIConfig, NewsSourcesConfig, MLConfig, WebSocketConfig)):
                        # Handle nested config objects
                        config_obj = getattr(settings, key)
                        for sub_key, sub_value in value.items():
                            if hasattr(config_obj, sub_key):
                                setattr(config_obj, sub_key, sub_value)
                    else:
                        setattr(settings, key, value)
        
        return settings


# Global settings instance
settings = Settings.from_env()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """Reload settings from environment and config file."""
    global settings
    settings = Settings.from_toml(config_path)
    return settings 