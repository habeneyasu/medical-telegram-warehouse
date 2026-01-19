#!/usr/bin/env python3
"""
Load YOLO detection results from CSV into PostgreSQL raw schema.

This script:
1. Reads CSV file from data/processed/image_detections.csv
2. Loads them into raw.image_detections table in PostgreSQL
3. Handles duplicates and data validation
"""

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    create_schema_if_not_exists,
    get_db_connection,
    get_db_engine,
    test_connection
)
from src.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__, log_file="load_detections_to_postgres.log")

# CSV file path
DETECTIONS_CSV = Path("data/processed/image_detections.csv")


def create_raw_schema():
    """Create raw schema if it doesn't exist."""
    try:
        if create_schema_if_not_exists("raw"):
            logger.info("✓ Raw schema created/verified")
            return True
        else:
            logger.error("Failed to create raw schema")
            return False
    except Exception as e:
        logger.error(f"Error creating raw schema: {e}", exc_info=True)
        return False


def create_detections_table():
    """Create raw.image_detections table if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS raw.image_detections (
        id SERIAL PRIMARY KEY,
        message_id BIGINT NOT NULL,
        channel_name VARCHAR(255) NOT NULL,
        image_path VARCHAR(500),
        detected_classes TEXT,
        total_detections INTEGER DEFAULT 0,
        max_confidence NUMERIC(5, 4),
        image_category VARCHAR(50),
        processed_at TIMESTAMP,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(message_id, channel_name)
    );
    
    CREATE INDEX IF NOT EXISTS idx_detections_message_id ON raw.image_detections(message_id);
    CREATE INDEX IF NOT EXISTS idx_detections_channel_name ON raw.image_detections(channel_name);
    CREATE INDEX IF NOT EXISTS idx_detections_category ON raw.image_detections(image_category);
    """
    
    try:
        with get_db_connection() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("✓ Image detections table created/verified")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Error creating detections table: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating detections table: {e}", exc_info=True)
        return False


def load_csv_file(csv_path: Path) -> pd.DataFrame:
    """Load CSV file into DataFrame."""
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    logger.info(f"Loading CSV file: {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"✓ Loaded {len(df)} rows from CSV")
        return df
    except pd.errors.EmptyDataError as e:
        logger.error(f"CSV file is empty: {csv_path}")
        raise
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV file: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error reading CSV: {e}", exc_info=True)
        raise


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare DataFrame with proper data types."""
    if df.empty:
        return df
    
    # Convert message_id to integer
    if 'message_id' in df.columns:
        df['message_id'] = pd.to_numeric(df['message_id'], errors='coerce').astype('Int64')
    
    # Convert total_detections to integer
    if 'total_detections' in df.columns:
        df['total_detections'] = pd.to_numeric(df['total_detections'], errors='coerce').astype('Int64').fillna(0)
    
    # Convert max_confidence to float
    if 'max_confidence' in df.columns:
        df['max_confidence'] = pd.to_numeric(df['max_confidence'], errors='coerce').astype('float64')
    
    # Convert processed_at to datetime
    if 'processed_at' in df.columns:
        df['processed_at'] = pd.to_datetime(df['processed_at'], errors='coerce')
    
    # Select and order columns
    columns = [
        'message_id',
        'channel_name',
        'image_path',
        'detected_classes',
        'total_detections',
        'max_confidence',
        'image_category',
        'processed_at'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns]
    
    return df


def load_to_postgres(df: pd.DataFrame):
    """Load DataFrame to PostgreSQL using upsert (ON CONFLICT)."""
    if df.empty:
        logger.warning("No data to load")
        return 0
    
    table_name = "raw.image_detections"
    engine = get_db_engine()
    
    # Load in chunks to handle large datasets
    chunk_size = 1000
    total_rows = len(df)
    loaded_rows = 0
    skipped_rows = 0
    
    logger.info(f"Loading {total_rows} detection results to {table_name}...")
    
    for i in range(0, total_rows, chunk_size):
        chunk = df.iloc[i:i + chunk_size]
        
        try:
            # Use pandas to_sql with method='multi' for better performance
            chunk.to_sql(
                name='image_detections',
                schema='raw',
                con=engine,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            loaded_rows += len(chunk)
            logger.debug(f"Loaded {loaded_rows}/{total_rows} rows...")
            
        except SQLAlchemyError as e:
            # Handle duplicate key errors (expected due to UNIQUE constraint)
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Handling duplicates in chunk {i//chunk_size + 1}")
                # Try individual inserts with ON CONFLICT handling
                for _, row in chunk.iterrows():
                    try:
                        row.to_frame().T.to_sql(
                            name='image_detections',
                            schema='raw',
                            con=engine,
                            if_exists='append',
                            index=False
                        )
                        loaded_rows += 1
                    except SQLAlchemyError:
                        skipped_rows += 1  # Skip duplicates
                    except Exception as e:
                        logger.warning(f"Error inserting row: {e}")
                        skipped_rows += 1
            else:
                logger.error(f"Error loading chunk {i//chunk_size + 1}: {e}", exc_info=True)
                continue
        except Exception as e:
            logger.error(f"Unexpected error loading chunk {i//chunk_size + 1}: {e}", exc_info=True)
            continue
    
    logger.info(f"✓ Successfully loaded {loaded_rows} rows to {table_name}")
    if skipped_rows > 0:
        logger.info(f"  (Skipped {skipped_rows} duplicate rows)")
    
    return loaded_rows


def get_table_stats():
    """Get statistics about loaded data."""
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_detections,
                    COUNT(DISTINCT channel_name) as unique_channels,
                    COUNT(DISTINCT message_id) as unique_messages,
                    COUNT(DISTINCT image_category) as unique_categories
                FROM raw.image_detections
            """))
            
            stats = result.fetchone()
            if stats:
                logger.info("="*50)
                logger.info("Image Detections Statistics")
                logger.info("="*50)
                logger.info(f"Total Detection Records: {stats[0]}")
                logger.info(f"Unique Channels: {stats[1]}")
                logger.info(f"Unique Messages: {stats[2]}")
                logger.info(f"Unique Categories: {stats[3]}")
                
                # Category breakdown
                category_result = conn.execute(text("""
                    SELECT 
                        image_category,
                        COUNT(*) as count,
                        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM raw.image_detections), 2) as percentage
                    FROM raw.image_detections
                    GROUP BY image_category
                    ORDER BY count DESC
                """))
                
                logger.info("\nCategory Breakdown:")
                for row in category_result:
                    logger.info(f"  {row[0]}: {row[1]} ({row[2]}%)")
                
                logger.info("="*50)
                return stats
            return None
    except SQLAlchemyError as e:
        logger.error(f"Error getting table statistics: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting table statistics: {e}", exc_info=True)
        return None


def main():
    """Main function to load detection results to PostgreSQL."""
    logger.info("="*50)
    logger.info("Loading Image Detection Results to PostgreSQL")
    logger.info("="*50)
    
    try:
        # Check CSV file exists
        if not DETECTIONS_CSV.exists():
            logger.error(f"CSV file not found: {DETECTIONS_CSV}")
            logger.error("Please run: python3 src/yolo_detect.py first")
            sys.exit(1)
        
        # Test database connection
        if not test_connection():
            logger.error("Database connection test failed")
            sys.exit(1)
        
        # Create schema and table
        if not create_raw_schema():
            logger.error("Failed to create raw schema")
            sys.exit(1)
        
        if not create_detections_table():
            logger.error("Failed to create detections table")
            sys.exit(1)
        
        # Load CSV file
        df = load_csv_file(DETECTIONS_CSV)
        
        # Prepare DataFrame
        logger.info("Preparing data...")
        df = prepare_dataframe(df)
        
        if df.empty:
            logger.warning("No valid data to load")
            sys.exit(0)
        
        # Load to PostgreSQL
        loaded_count = load_to_postgres(df)
        
        if loaded_count == 0:
            logger.warning("No rows were loaded")
        else:
            # Get statistics
            get_table_stats()
        
        logger.info("✓ Data loading complete!")
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        sys.exit(1)
    except FileNotFoundError:
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
