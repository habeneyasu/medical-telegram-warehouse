#!/usr/bin/env python3
"""
Test database connection and verify configuration.

This script:
1. Tests connection to PostgreSQL
2. Verifies database exists
3. Checks if raw schema exists
4. Shows current database configuration
"""

import os
import sys
from urllib.parse import quote_plus
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


def test_connection():
    """Test database connection."""
    print("="*60)
    print("DATABASE CONNECTION TEST")
    print("="*60)
    
    # Display configuration (hide password)
    print("\n📋 Configuration:")
    print(f"  Host: {POSTGRES_HOST}")
    print(f"  Port: {POSTGRES_PORT}")
    print(f"  Database: {POSTGRES_DB}")
    print(f"  User: {POSTGRES_USER}")
    print(f"  Password: {'*' * len(POSTGRES_PASSWORD)}")
    
    # Build connection string (URL-encode password to handle special characters)
    encoded_password = quote_plus(POSTGRES_PASSWORD)
    connection_string = (
        f"postgresql://{POSTGRES_USER}:{encoded_password}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    print("\n🔌 Testing connection...")
    
    try:
        engine = create_engine(connection_string)
        
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"  ✅ Connected successfully!")
            print(f"  📊 PostgreSQL Version: {version.split(',')[0]}")
        
        # Test database exists
        print("\n📦 Checking database...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database();"))
            db_name = result.fetchone()[0]
            print(f"  ✅ Current database: {db_name}")
        
        # Check if raw schema exists
        print("\n📁 Checking schemas...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name IN ('raw', 'staging', 'marts')
                ORDER BY schema_name;
            """))
            schemas = [row[0] for row in result.fetchall()]
            
            if schemas:
                print(f"  ✅ Found schemas: {', '.join(schemas)}")
            else:
                print("  ⚠ No schemas found (will be created during data load)")
        
        # Check if raw.telegram_messages table exists
        print("\n📊 Checking tables...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'raw' 
                AND table_name = 'telegram_messages';
            """))
            table = result.fetchone()
            
            if table:
                # Get row count
                count_result = conn.execute(text("SELECT COUNT(*) FROM raw.telegram_messages;"))
                row_count = count_result.fetchone()[0]
                print(f"  ✅ Table exists: {table[0]}.{table[1]}")
                print(f"  📈 Row count: {row_count:,}")
            else:
                print("  ⚠ Table 'raw.telegram_messages' not found (will be created during data load)")
        
        print("\n" + "="*60)
        print("✅ ALL CHECKS PASSED - Database is ready!")
        print("="*60)
        return True
        
    except SQLAlchemyError as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\n💡 Troubleshooting:")
        print("  1. Check if PostgreSQL is running")
        print("  2. Verify credentials in .env file")
        print("  3. Check if database exists")
        print("  4. Verify network connectivity")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
