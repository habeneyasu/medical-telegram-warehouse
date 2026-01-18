#!/usr/bin/env python3
"""Check which channels are in the database."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "medical_warehouse")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

encoded_password = quote_plus(POSTGRES_PASSWORD)
connection_string = (
    f"postgresql://{POSTGRES_USER}:{encoded_password}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(connection_string)

with engine.connect() as conn:
    # Get unique channels with counts
    result = conn.execute(text("""
        SELECT 
            channel_name,
            COUNT(*) as message_count,
            MIN(message_date) as first_message,
            MAX(message_date) as last_message
        FROM raw.telegram_messages
        GROUP BY channel_name
        ORDER BY message_count DESC;
    """))
    
    print("="*70)
    print("CHANNELS IN DATABASE")
    print("="*70)
    print(f"{'Channel Name':<40} {'Messages':<10} {'First Message':<20}")
    print("-"*70)
    
    channels = []
    for row in result:
        channels.append(row[0])
        print(f"{row[0]:<40} {row[1]:<10} {str(row[2])[:20]:<20}")
    
    print("-"*70)
    print(f"Total unique channels: {len(channels)}")
    print("="*70)
    
    # Check expected channels
    print("\nExpected channels from scraper:")
    expected = ['CheMed123', 'lobelia4cosmetics', 'tikvahpharma']
    print(f"  - CheMed123")
    print(f"  - lobelia4cosmetics")
    print(f"  - tikvahpharma")
    
    print("\n📊 Analysis:")
    print(f"  • Found in database: {len(channels)} channels")
    print(f"  • Expected: 3 channels")
    
    if len(channels) < 3:
        print(f"\n⚠ Missing channels:")
        for exp in expected:
            found = any(exp.lower() in ch.lower() or ch.lower() in exp.lower() 
                       for ch in channels)
            if not found:
                print(f"    - {exp} (not found in database)")
    
    print("\n💡 Note: Channel names in database may differ from usernames.")
    print("   The scraper uses display names from Telegram, not usernames.")
