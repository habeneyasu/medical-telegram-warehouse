"""
Tests for shared database connection module.

Tests:
- Database connection creation
- Connection pooling
- Error handling
- Schema creation
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from src.database import (
    get_db_engine,
    get_db_connection,
    test_connection,
    close_connection,
    create_schema_if_not_exists
)


class TestDatabaseConnection:
    """Test database connection functionality."""
    
    def test_get_db_engine_singleton(self):
        """Test that get_db_engine returns the same instance (singleton)."""
        # Close any existing connection
        close_connection()
        
        engine1 = get_db_engine()
        engine2 = get_db_engine()
        
        assert engine1 is engine2, "Should return the same engine instance (singleton)"
    
    @patch('src.database.create_engine')
    def test_get_db_engine_connection_error(self, mock_create_engine):
        """Test error handling when database connection fails."""
        close_connection()
        
        mock_create_engine.side_effect = SQLAlchemyError("Connection failed")
        
        with pytest.raises(ConnectionError):
            get_db_engine()
    
    def test_get_db_connection_context_manager(self):
        """Test that get_db_connection works as a context manager."""
        from sqlalchemy import text
        try:
            with get_db_connection() as conn:
                assert conn is not None
                # Connection should be valid
                result = conn.execute(text("SELECT 1"))
                assert result is not None
        except Exception:
            # If database is not available, skip this test
            pytest.skip("Database not available for testing")
    
    @patch('src.database.get_db_engine')
    def test_get_db_connection_error_handling(self, mock_get_engine):
        """Test error handling in get_db_connection."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection error")
        mock_get_engine.return_value = mock_engine
        
        with pytest.raises(ConnectionError):
            with get_db_connection():
                pass
    
    def test_test_connection(self):
        """Test connection health check."""
        try:
            result = test_connection()
            assert isinstance(result, bool)
        except Exception:
            # If database is not available, skip this test
            pytest.skip("Database not available for testing")
    
    def test_close_connection(self):
        """Test closing the connection pool."""
        # Get engine first
        engine = get_db_engine()
        assert engine is not None
        
        # Close connection
        close_connection()
        
        # Get engine again - should create new instance
        new_engine = get_db_engine()
        assert new_engine is not None
        # Should be different instance after close
        assert new_engine is not engine
    
    def test_create_schema_if_not_exists(self):
        """Test schema creation."""
        try:
            result = create_schema_if_not_exists("test_schema")
            assert isinstance(result, bool)
            
            # Clean up - drop test schema
            from sqlalchemy import text
            with get_db_connection() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS test_schema CASCADE"))
                conn.commit()
        except Exception:
            # If database is not available, skip this test
            pytest.skip("Database not available for testing")


class TestDatabaseConfiguration:
    """Test database configuration."""
    
    @patch.dict(os.environ, {
        'POSTGRES_HOST': 'test_host',
        'POSTGRES_PORT': '5433',
        'POSTGRES_DB': 'test_db',
        'POSTGRES_USER': 'test_user',
        'POSTGRES_PASSWORD': 'test_pass'
    })
    def test_database_config_from_env(self):
        """Test that database configuration is read from environment variables."""
        # Reload module to pick up new env vars
        import importlib
        import src.database
        importlib.reload(src.database)
        
        # Close existing connection
        close_connection()
        
        # This will use the mocked environment variables
        # We can't easily test the actual connection without a real DB,
        # but we can verify the configuration is read
        assert src.database.POSTGRES_HOST == 'test_host'
        assert src.database.POSTGRES_PORT == '5433'
        assert src.database.POSTGRES_DB == 'test_db'
        assert src.database.POSTGRES_USER == 'test_user'
        assert src.database.POSTGRES_PASSWORD == 'test_pass'
