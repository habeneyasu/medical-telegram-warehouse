"""
Professional logging configuration for the entire project.

Provides:
- Consistent logging format across all modules
- File and console handlers
- Log rotation
- Different log levels for different environments
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Default log level
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: str = DEFAULT_LOG_LEVEL,
    console: bool = True,
    file: bool = True
) -> logging.Logger:
    """
    Set up a professional logger with file and console handlers.
    
    Args:
        name: Logger name (typically __name__)
        log_file: Optional log file name (defaults to {name}.log)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Whether to log to console
        file: Whether to log to file
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level, logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if file:
        if log_file is None:
            log_file = f"{name.split('.')[-1]}.log"
        
        log_path = LOG_DIR / log_file
        
        # Rotating file handler: 10MB max, keep 5 backup files
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level, logging.INFO))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance (convenience function).
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return setup_logger(name)
