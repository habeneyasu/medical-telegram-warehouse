"""
Shared database connection module for the entire project.

This module provides:
- Singleton database connection (one connection pool for the whole project)
- Professional logging
- Proper exception handling
- Connection health checks
- Optimized connection pooling
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "medical_warehouse")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Singleton engine instance
_engine: Optional[Engine] = None


def get_db_engine() -> Engine:
    """
    Get or create the singleton database engine.
    
    Uses connection pooling for optimal performance:
    - pool_size: Number of connections to maintain
    - max_overflow: Additional connections beyond pool_size
    - pool_pre_ping: Verify connections before using (handles stale connections)
    - pool_recycle: Recycle connections after 3600 seconds (1 hour)
    
    Returns:
        SQLAlchemy Engine instance (singleton)
    
    Raises:
        ConnectionError: If database connection fails
    """
    global _engine
    
    if _engine is None:
        try:
            # URL-encode password to handle special characters like @
            encoded_password = quote_plus(POSTGRES_PASSWORD)
            connection_string = (
                f"postgresql://{POSTGRES_USER}:{encoded_password}@"
                f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
            )
            
            logger.info(f"Creating database connection pool to {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
            
            # Create engine with optimized connection pooling
            _engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=5,  # Number of connections to maintain
                max_overflow=10,  # Additional connections beyond pool_size
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
                echo=False,  # Set to True for SQL query logging
                connect_args={
                    "connect_timeout": 10,  # Connection timeout in seconds
                    "application_name": "medical_telegram_warehouse"
                }
            )
            
            # Test connection
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("✓ Database connection pool created successfully")
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to create database connection: {e}")
            raise ConnectionError(f"Database connection failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating database connection: {e}")
            raise ConnectionError(f"Unexpected database error: {e}") from e
    
    return _engine


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    
    Provides automatic connection management:
    - Gets connection from pool
    - Handles exceptions
    - Automatically returns connection to pool
    
    Usage:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT * FROM table"))
    
    Yields:
        Database connection from pool
    
    Raises:
        ConnectionError: If connection cannot be obtained
    """
    engine = get_db_engine()
    
    try:
        conn = engine.connect()
        logger.debug("Database connection obtained from pool")
        try:
            yield conn
        finally:
            conn.close()
            logger.debug("Database connection returned to pool")
    except SQLAlchemyError as e:
        logger.error(f"Error obtaining database connection: {e}")
        raise ConnectionError(f"Failed to get database connection: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error with database connection: {e}")
        raise ConnectionError(f"Unexpected database error: {e}") from e


def test_connection() -> bool:
    """
    Test database connection health.
    
    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            
            if test_value == 1:
                logger.info("✓ Database connection test passed")
                return True
            else:
                logger.warning("Database connection test returned unexpected value")
                return False
                
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def close_connection():
    """
    Close the database connection pool.
    
    Should be called when application is shutting down.
    """
    global _engine
    
    if _engine is not None:
        try:
            _engine.dispose()
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing database connection pool: {e}")
        finally:
            _engine = None


def create_schema_if_not_exists(schema_name: str) -> bool:
    """
    Create a database schema if it doesn't exist.
    
    Args:
        schema_name: Name of the schema to create
    
    Returns:
        True if schema was created or already exists, False on error
    """
    try:
        with get_db_connection() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            conn.commit()
            logger.info(f"✓ Schema '{schema_name}' created/verified")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Error creating schema '{schema_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating schema '{schema_name}': {e}")
        return False
