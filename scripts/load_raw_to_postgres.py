#!/usr/bin/env python3
"""
Load raw JSON data from data lake into PostgreSQL raw schema.

This script:
1. Reads JSON files from data/raw/telegram_messages/
2. Loads them into raw.telegram_messages table in PostgreSQL
3. Handles duplicates and data validation
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables
load_dotenv()

# Database connection
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "medical_warehouse")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")


def get_db_connection():
    """Create and return database connection."""
    # URL-encode password to handle special characters like @
    encoded_password = quote_plus(POSTGRES_PASSWORD)
    connection_string = (
        f"postgresql://{POSTGRES_USER}:{encoded_password}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    return create_engine(connection_string)


def create_raw_schema(engine):
    """Create raw schema if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        conn.commit()
        print("✓ Raw schema created/verified")


def create_raw_table(engine):
    """Create raw.telegram_messages table if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS raw.telegram_messages (
        id SERIAL PRIMARY KEY,
        message_id BIGINT,
        channel_name VARCHAR(255),
        message_date TIMESTAMP,
        message_text TEXT,
        has_media BOOLEAN,
        image_path VARCHAR(500),
        views INTEGER,
        forwards INTEGER,
        is_reply BOOLEAN,
        reply_to_msg_id BIGINT,
        scraped_at TIMESTAMP,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(message_id, channel_name, message_date)
    );
    
    CREATE INDEX IF NOT EXISTS idx_message_id ON raw.telegram_messages(message_id);
    CREATE INDEX IF NOT EXISTS idx_channel_name ON raw.telegram_messages(channel_name);
    CREATE INDEX IF NOT EXISTS idx_message_date ON raw.telegram_messages(message_date);
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✓ Raw table created/verified")


def load_json_files(data_dir: Path) -> List[Dict]:
    """Load all JSON files from data lake directory structure."""
    messages = []
    json_files = list(data_dir.rglob("*.json"))
    
    print(f"Found {len(json_files)} JSON files to process")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                file_messages = json.load(f)
                
                # Handle both single dict and list of dicts
                if isinstance(file_messages, dict):
                    file_messages = [file_messages]
                
                for msg in file_messages:
                    if isinstance(msg, dict):
                        messages.append(msg)
            
            print(f"  Loaded {len(file_messages)} messages from {json_file.name}")
            
        except json.JSONDecodeError as e:
            print(f"  ⚠ Error reading {json_file}: {e}")
            continue
        except Exception as e:
            print(f"  ⚠ Error processing {json_file}: {e}")
            continue
    
    return messages


def prepare_dataframe(messages: List[Dict]) -> pd.DataFrame:
    """Convert messages list to DataFrame with proper data types."""
    if not messages:
        return pd.DataFrame()
    
    df = pd.DataFrame(messages)
    
    # Convert message_date to datetime
    if 'message_date' in df.columns:
        df['message_date'] = pd.to_datetime(df['message_date'], errors='coerce')
    
    # Convert scraped_at to datetime
    if 'scraped_at' in df.columns:
        df['scraped_at'] = pd.to_datetime(df['scraped_at'], errors='coerce')
    
    # Ensure boolean columns
    bool_columns = ['has_media', 'is_reply']
    for col in bool_columns:
        if col in df.columns:
            df[col] = df[col].astype('boolean', errors='ignore')
    
    # Ensure integer columns
    int_columns = ['message_id', 'views', 'forwards', 'reply_to_msg_id']
    for col in int_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    
    # Select and order columns
    columns = [
        'message_id', 'channel_name', 'message_date', 'message_text',
        'has_media', 'image_path', 'views', 'forwards',
        'is_reply', 'reply_to_msg_id', 'scraped_at'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns]
    
    return df


def load_to_postgres(df: pd.DataFrame, engine):
    """Load DataFrame to PostgreSQL using upsert (ON CONFLICT)."""
    if df.empty:
        print("⚠ No data to load")
        return
    
    table_name = "raw.telegram_messages"
    
    # Load in chunks to handle large datasets
    chunk_size = 1000
    total_rows = len(df)
    loaded_rows = 0
    
    print(f"\nLoading {total_rows} messages to {table_name}...")
    
    for i in range(0, total_rows, chunk_size):
        chunk = df.iloc[i:i + chunk_size]
        
        try:
            # Use pandas to_sql with method='multi' for better performance
            chunk.to_sql(
                name='telegram_messages',
                schema='raw',
                con=engine,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            loaded_rows += len(chunk)
            print(f"  Loaded {loaded_rows}/{total_rows} messages...", end='\r')
            
        except SQLAlchemyError as e:
            # Handle duplicate key errors (expected due to UNIQUE constraint)
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                # Try individual inserts with ON CONFLICT handling
                for _, row in chunk.iterrows():
                    try:
                        row.to_frame().T.to_sql(
                            name='telegram_messages',
                            schema='raw',
                            con=engine,
                            if_exists='append',
                            index=False
                        )
                        loaded_rows += 1
                    except:
                        pass  # Skip duplicates
            else:
                print(f"\n  ⚠ Error loading chunk: {e}")
                continue
    
    print(f"\n✓ Successfully loaded {loaded_rows} messages to {table_name}")


def get_table_stats(engine):
    """Get statistics about loaded data."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT channel_name) as unique_channels,
                MIN(message_date) as earliest_date,
                MAX(message_date) as latest_date
            FROM raw.telegram_messages
        """))
        
        stats = result.fetchone()
        if stats:
            print("\n" + "="*50)
            print("Data Warehouse Statistics")
            print("="*50)
            print(f"Total Messages: {stats[0]}")
            print(f"Unique Channels: {stats[1]}")
            print(f"Date Range: {stats[2]} to {stats[3]}")
            print("="*50)


def main():
    """Main function to load raw data to PostgreSQL."""
    print("="*50)
    print("Loading Raw Data to PostgreSQL")
    print("="*50)
    
    # Get data directory
    data_dir = Path("data/raw/telegram_messages")
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Connect to database
    try:
        engine = get_db_connection()
        print("✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Create schema and table
    create_raw_schema(engine)
    create_raw_table(engine)
    
    # Load JSON files
    print(f"\nLoading JSON files from {data_dir}...")
    messages = load_json_files(data_dir)
    
    if not messages:
        print("⚠ No messages found to load")
        sys.exit(0)
    
    print(f"\n✓ Loaded {len(messages)} total messages from JSON files")
    
    # Prepare DataFrame
    print("\nPreparing data...")
    df = prepare_dataframe(messages)
    
    if df.empty:
        print("⚠ No valid data to load")
        sys.exit(0)
    
    # Load to PostgreSQL
    load_to_postgres(df, engine)
    
    # Get statistics
    get_table_stats(engine)
    
    print("\n✓ Data loading complete!")


if __name__ == "__main__":
    main()
