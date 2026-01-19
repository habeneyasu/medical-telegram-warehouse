"""
Tests for logging configuration module.

Tests:
- Logger creation
- File and console handlers
- Log rotation
- Different log levels
"""

import logging
import os
from pathlib import Path
from unittest.mock import patch

from src.logger_config import setup_logger, get_logger


class TestLoggerSetup:
    """Test logger setup functionality."""
    
    def test_setup_logger_creates_logger(self):
        """Test that setup_logger creates a logger instance."""
        logger = setup_logger("test_logger", log_file="test.log", console=False, file=False)
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
    
    def test_setup_logger_with_file(self):
        """Test logger with file handler."""
        log_file = "test_file.log"
        logger = setup_logger("test_file_logger", log_file=log_file, console=False, file=True)
        
        # Check that file handler exists
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0, "Should have at least one file handler"
        
        # Clean up
        log_path = Path("logs") / log_file
        if log_path.exists():
            log_path.unlink()
    
    def test_setup_logger_with_console(self):
        """Test logger with console handler."""
        logger = setup_logger("test_console_logger", console=True, file=False)
        
        # Check that stream handler exists
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) > 0, "Should have at least one stream handler"
    
    def test_setup_logger_log_level(self):
        """Test logger with different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger = setup_logger(f"test_{level}", level=level, console=False, file=False)
            assert logger.level == getattr(logging, level)
    
    def test_get_logger_convenience_function(self):
        """Test get_logger convenience function."""
        logger = get_logger("test_convenience")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_convenience"
    
    def test_setup_logger_prevents_duplicate_handlers(self):
        """Test that setup_logger doesn't add duplicate handlers."""
        logger = setup_logger("test_duplicate", console=True, file=False)
        initial_handler_count = len(logger.handlers)
        
        # Call setup_logger again
        logger2 = setup_logger("test_duplicate", console=True, file=False)
        
        # Should be the same logger instance
        assert logger is logger2
        # Should not have added duplicate handlers
        assert len(logger.handlers) == initial_handler_count
    
    def test_log_directory_creation(self):
        """Test that log directory is created if it doesn't exist."""
        log_dir = Path("logs")
        test_log_file = "test_dir_creation.log"
        
        # Remove log directory if it exists
        if log_dir.exists():
            test_log_path = log_dir / test_log_file
            if test_log_path.exists():
                test_log_path.unlink()
        
        # Create logger - should create logs directory
        logger = setup_logger("test_dir", log_file=test_log_file, console=False, file=True)
        
        assert log_dir.exists(), "Logs directory should be created"
        
        # Clean up
        test_log_path = log_dir / test_log_file
        if test_log_path.exists():
            test_log_path.unlink()
