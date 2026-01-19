"""
Database connection module for FastAPI.

This module provides database connection utilities using the shared
database connection from src.database.
"""

import sys
from pathlib import Path
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_connection, test_connection
from src.logger_config import setup_logger

logger = setup_logger(__name__)


@contextmanager
def _get_raw_connection():
    """
    Internal context manager to get raw psycopg2 connection.
    """
    with get_db_connection() as sqlalchemy_conn:
        # Get the raw psycopg2 connection from SQLAlchemy
        # SQLAlchemy wraps the raw connection in a ConnectionFairy
        raw_conn = sqlalchemy_conn.connection.driver_connection
        yield raw_conn


def get_db():
    """
    Database dependency for FastAPI.
    
    Yields a raw psycopg2 connection that is automatically closed after use.
    Use this as a FastAPI dependency.
    
    Yields:
        psycopg2.connection: Raw database connection object
        
    Example:
        @app.get("/endpoint")
        def my_endpoint(db = Depends(get_db)):
            with db.cursor() as cursor:
                cursor.execute("SELECT * FROM ...")
    """
    try:
        # Use the context manager but keep it open for FastAPI's dependency lifecycle
        conn_manager = _get_raw_connection()
        raw_conn = conn_manager.__enter__()
        try:
            yield raw_conn
        finally:
            # Close the connection when FastAPI is done with it
            conn_manager.__exit__(None, None, None)
    except Exception as e:
        logger.error(f"Database connection error: {e}", exc_info=True)
        raise


def check_database_health() -> str:
    """
    Check database connection health.
    
    Returns:
        str: "connected" if healthy, "disconnected" otherwise
    """
    try:
        if test_connection():
            return "connected"
        return "disconnected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return "disconnected"
