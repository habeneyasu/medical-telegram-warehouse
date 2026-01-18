"""
Utility script to find and validate Telegram channels from et.tgstat.com/medicine

This script helps discover additional medical-related Telegram channels
that can be scraped for the project.
"""

import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_medical_channels() -> List[str]:
    """
    Returns a list of Telegram channel usernames for medical products in Ethiopia.
    
    This is a curated list. For a production system, you might want to:
    1. Scrape et.tgstat.com/medicine to get a dynamic list
    2. Use Telegram's search functionality
    3. Maintain a database of discovered channels
    
    Returns:
        List of channel usernames (without @ symbol)
    """
    channels = [
        'CheMed123',           # CheMed Channel
        'lobelia4cosmetics',   # Lobelia Cosmetics
        'tikvahpharma',        # Tikvah Pharma
        # Add more channels discovered from et.tgstat.com/medicine
        # Example format: 'channel_username'
    ]
    
    logger.info(f"Found {len(channels)} medical channels")
    return channels


def validate_channel_format(channel: str) -> bool:
    """
    Validate that a channel username is in the correct format.
    
    Args:
        channel: Channel username to validate
        
    Returns:
        True if valid format, False otherwise
    """
    # Remove @ if present
    channel = channel.lstrip('@')
    
    # Check length and characters
    if not channel or len(channel) < 5:
        return False
    
    # Telegram usernames can contain letters, numbers, and underscores
    if not all(c.isalnum() or c == '_' for c in channel):
        return False
    
    return True


if __name__ == "__main__":
    channels = get_medical_channels()
    print("Medical Telegram Channels:")
    for i, channel in enumerate(channels, 1):
        print(f"{i}. @{channel}")
        print(f"   URL: https://t.me/{channel}")
