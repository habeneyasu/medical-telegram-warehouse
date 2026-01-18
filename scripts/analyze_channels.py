#!/usr/bin/env python3
"""Analyze which channels are in database vs JSON files vs expected."""

import json
import os
from pathlib import Path
from collections import Counter
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Expected channels from scraper
EXPECTED_CHANNELS = {
    'CheMed123': ['CheMed', 'CheMed123'],
    'lobelia4cosmetics': ['Lobelia pharmacy and cosmetics', 'lobelia4cosmetics', 'Lobelia'],
    'tikvahpharma': ['tikvahpharma', 'Tikvah', 'Tikvah Pharma']
}

print("="*70)
print("CHANNEL ANALYSIS")
print("="*70)

# 1. Check JSON files
print("\n1️⃣  CHANNELS IN JSON FILES:")
print("-"*70)
data_dir = Path("data/raw/telegram_messages")
channel_names_json = []

for json_file in data_dir.rglob("*.json"):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for msg in data:
                    if isinstance(msg, dict) and 'channel_name' in msg:
                        channel_names_json.append(msg['channel_name'])
            elif isinstance(data, dict) and 'channel_name' in data:
                channel_names_json.append(data['channel_name'])
    except Exception as e:
        pass

channel_counts_json = Counter(channel_names_json)
for channel, count in channel_counts_json.most_common():
    print(f"  ✓ {channel:<50} {count:>6} messages")

print(f"\n  Total: {len(channel_counts_json)} unique channels in JSON files")

# 2. Check database
print("\n2️⃣  CHANNELS IN DATABASE:")
print("-"*70)

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

try:
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                channel_name,
                COUNT(*) as message_count
            FROM raw.telegram_messages
            GROUP BY channel_name
            ORDER BY message_count DESC;
        """))
        
        channel_counts_db = {}
        for row in result:
            channel_counts_db[row[0]] = row[1]
            print(f"  ✓ {row[0]:<50} {row[1]:>6} messages")
        
        print(f"\n  Total: {len(channel_counts_db)} unique channels in database")
        
except Exception as e:
    print(f"  ❌ Error connecting to database: {e}")
    channel_counts_db = {}

# 3. Compare and identify missing
print("\n3️⃣  MISSING CHANNELS ANALYSIS:")
print("-"*70)

# Get all unique channel names from JSON
json_channel_names = set(channel_counts_json.keys())
db_channel_names = set(channel_counts_db.keys())

# Check which expected channels are missing
print("\nExpected channels:")
for expected_username, possible_names in EXPECTED_CHANNELS.items():
    # Check if any variant exists in JSON
    found_in_json = any(
        any(variant.lower() in json_name.lower() or json_name.lower() in variant.lower() 
            for variant in possible_names)
        for json_name in json_channel_names
    )
    
    # Check if any variant exists in DB
    found_in_db = any(
        any(variant.lower() in db_name.lower() or db_name.lower() in variant.lower() 
            for variant in possible_names)
        for db_name in db_channel_names
    )
    
    status_json = "✓" if found_in_json else "✗"
    status_db = "✓" if found_in_db else "✗"
    
    print(f"  {status_json} JSON | {status_db} DB | {expected_username}")
    
    if not found_in_json:
        print(f"      ⚠ Not found in JSON files - may need to scrape")
    elif not found_in_db:
        print(f"      ⚠ Found in JSON but not in DB - may need to reload")

# 4. Check for tikvahpharma specifically
print("\n4️⃣  TIKVAHPHARMA CHECK:")
print("-"*70)

tikvah_in_json = any('tikvah' in name.lower() for name in json_channel_names)
tikvah_in_db = any('tikvah' in name.lower() for name in db_channel_names)

if tikvah_in_json:
    tikvah_names = [name for name in json_channel_names if 'tikvah' in name.lower()]
    print(f"  ✓ Found in JSON: {tikvah_names}")
else:
    print("  ✗ NOT found in JSON files")
    print("     → Run scraper: python3 scripts/run_scraper.py")

if tikvah_in_db:
    tikvah_db_names = [name for name in db_channel_names if 'tikvah' in name.lower()]
    print(f"  ✓ Found in DB: {tikvah_db_names}")
else:
    print("  ✗ NOT found in database")
    if tikvah_in_json:
        print("     → Reload data: python3 scripts/load_raw_to_postgres.py")
    else:
        print("     → First scrape, then reload")

# 5. Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"JSON files: {len(channel_counts_json)} channels, {sum(channel_counts_json.values())} messages")
print(f"Database:   {len(channel_counts_db)} channels, {sum(channel_counts_db.values())} messages")
print(f"Expected:   3 channels (CheMed123, lobelia4cosmetics, tikvahpharma)")

if len(channel_counts_json) < 3:
    print("\n⚠ Action needed: Scrape missing channels")
    print("   python3 scripts/run_scraper.py")

if len(channel_counts_db) < len(channel_counts_json):
    print("\n⚠ Action needed: Reload data to database")
    print("   python3 scripts/load_raw_to_postgres.py")

print("="*70)
