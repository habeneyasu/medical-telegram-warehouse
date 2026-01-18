#!/usr/bin/env python3
"""
Convenience script to run the Telegram scraper.

Usage:
    python scripts/run_scraper.py
    python scripts/run_scraper.py --channels lobelia4cosmetics tikvahpharma
    python scripts/run_scraper.py --limit 50
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import TelegramScraper
from src.channel_finder import get_medical_channels


async def run_scraper(channels: list = None, limit: int = None):
    """
    Run the Telegram scraper with specified parameters.
    
    Args:
        channels: List of channel usernames to scrape (None for default)
        limit: Maximum messages per channel (None for all)
    """
    # Get API credentials from environment
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file")
        print("\nTo get API credentials:")
        print("1. Go to https://my.telegram.org")
        print("2. Log in with your phone number")
        print("3. Go to 'API development tools'")
        print("4. Create an application and copy API ID and API Hash")
        print("5. Add them to your .env file:")
        print("   TELEGRAM_API_ID=your_api_id")
        print("   TELEGRAM_API_HASH=your_api_hash")
        sys.exit(1)
    
    # Use default channels if none specified
    if channels is None:
        channels = get_medical_channels()
    
    # Initialize scraper
    scraper = TelegramScraper(api_id, api_hash)
    
    try:
        # Connect to Telegram
        if not await scraper.connect():
            print("Failed to connect to Telegram")
            sys.exit(1)
        
        print(f"\nStarting scrape for {len(channels)} channels...")
        print(f"Channels: {', '.join(channels)}")
        if limit:
            print(f"Limit: {limit} messages per channel")
        print()
        
        # Scrape all channels
        await scraper.scrape_multiple_channels(
            channel_usernames=channels,
            limit_per_channel=limit
        )
        
        # Print summary
        summary = scraper.get_scraping_summary()
        print("\n" + "="*50)
        print("SCRAPING SUMMARY")
        print("="*50)
        print(f"Channels scraped: {summary['total_channels']}")
        print(f"Dates covered: {summary['total_dates']}")
        print(f"Total images downloaded: {summary['images_downloaded']}")
        print(f"\nImages by channel:")
        for channel, stats in summary['images_by_channel'].items():
            print(f"  {channel}: {stats['downloaded']}/{stats['max']}")
        print(f"\nChannels: {', '.join(summary['channels_scraped'])}")
        print(f"Dates: {', '.join(sorted(summary['dates_scraped']))}")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        sys.exit(1)
    finally:
        await scraper.close()


def main():
    """Parse arguments and run scraper."""
    parser = argparse.ArgumentParser(
        description='Scrape Telegram channels for medical products data'
    )
    parser.add_argument(
        '--channels',
        nargs='+',
        help='Channel usernames to scrape (without @)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of messages to scrape per channel'
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_scraper(channels=args.channels, limit=args.limit))


if __name__ == "__main__":
    main()
