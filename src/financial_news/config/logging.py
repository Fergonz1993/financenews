"""
Logging configuration for Financial News application.

This module provides centralized logging setup with different handlers
for development and production environments.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any


def get_logging_config(
    level: str = "INFO",
    log_file: str = "financial_news.log",
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> Dict[str, Any]:
    """
    Get logging configuration dictionary.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Logging configuration dictionary
    """
    
    # Ensure logs directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s - %(name)s - %(message)s"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(lineno)d %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "simple",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": level,
                "formatter": "detailed",
                "filename": log_file,
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": log_path.parent / "errors.log",
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8"
            }
        },
        "loggers": {
            "financial_news": {
                "level": level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "financial_news.core": {
                "level": level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "financial_news.models": {
                "level": level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "financial_news.services": {
                "level": level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "financial_news.api": {
                "level": level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"]
        }
    }
    
    return config


def setup_logging(
    level: str = "INFO",
    log_file: str = "logs/financial_news.log",
    environment: str = "development"
) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level
        log_file: Path to log file
        environment: Environment (development, production)
    """
    
    # Adjust configuration based on environment
    if environment == "production":
        # In production, log to file and reduce console output
        config = get_logging_config(level, log_file)
        config["handlers"]["console"]["level"] = "WARNING"
    else:
        # In development, more verbose console output
        config = get_logging_config(level, log_file)
        config["handlers"]["console"]["level"] = "DEBUG"
        config["handlers"]["console"]["formatter"] = "detailed"
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log startup message
    logger = logging.getLogger("financial_news")
    logger.info(f"Logging initialized - Level: {level}, Environment: {environment}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


# Performance logging decorator
def log_performance(func):
    """Decorator to log function execution time."""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(f"{func.__module__}.{func.__name__}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"Function executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Function failed after {execution_time:.4f} seconds: {str(e)}")
            raise
    
    return wrapper 