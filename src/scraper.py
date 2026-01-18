"""
Telegram Channel Scraper for Medical Products Data Collection

This module provides functionality to scrape messages from Telegram channels
related to Ethiopian medical businesses, download associated images, and store
the data in a structured format for further processing.

Author: Data Engineering Team
Date: 2026-01-17
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    SessionPasswordNeededError,
    UsernameNotOccupiedError,
)
from telethon.tl.types import Message, MessageMediaPhoto

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Maximum number of images to download per channel (from environment)
# Format: MAX_IMAGES_CHANNELNAME=limit
# Example: MAX_IMAGES_CheMed123=1200
# Default: 1500 if not specified for a channel
DEFAULT_MAX_IMAGES = int(os.getenv('MAX_IMAGES', '1500'))


class TelegramScraper:
    """
    A professional scraper for extracting data from Telegram channels.
    
    Features:
    - Extracts message metadata (ID, date, text, views, forwards)
    - Downloads images associated with messages
    - Handles rate limiting and errors gracefully
    - Stores data in organized directory structure
    - Comprehensive logging
    """
    
    def __init__(
        self,
        api_id: str,
        api_hash: str,
        session_name: str = "telegram_scraper",
        session_path: Optional[str] = None
    ):
        """
        Initialize the Telegram scraper.
        
        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API hash from my.telegram.org
            session_name: Name for the Telethon session file
        session_path: Optional path for session file directory
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        # Use provided session path or default to .telethon directory
        if session_path:
            self.session_path = Path(session_path) / f"{session_name}.session"
        else:
            # Default: use .telethon directory in home or current directory
            home_telethon = Path.home() / ".telethon"
            if home_telethon.exists() or os.getenv("TELEGRAM_SESSION_DIR"):
                session_dir = Path(os.getenv("TELEGRAM_SESSION_DIR", str(home_telethon)))
                session_dir.mkdir(parents=True, exist_ok=True)
                self.session_path = session_dir / f"{session_name}.session"
            else:
                self.session_path = Path(f"{session_name}.session")
        self.client: Optional[TelegramClient] = None
        
        # Setup directories
        self.setup_directories()
        
        # Track scraped channels and dates
        self.scraped_channels = set()
        self.scraped_dates = set()
        
        # Track downloaded images count per channel
        self.downloaded_images_count = {}  # {channel_name: count}
        self.channel_max_images = self._load_channel_limits()
        
        # Track which channels have reached their image limit (to avoid repeated warnings)
        self.channel_limit_reached = set()  # Set of channel names that reached limit
        
    def setup_directories(self):
        """Create necessary directories for data storage."""
        directories = [
            'data/raw/telegram_messages',
            'data/raw/images',
            'logs'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def _load_channel_limits(self) -> Dict[str, int]:
        """
        Load channel-specific image download limits from environment variables.
        
        Format: MAX_IMAGES_{CHANNEL_NAME}=limit
        Example: MAX_IMAGES_CheMed123=1200
        
        Returns:
            Dictionary mapping channel names to their limits
        """
        limits = {}
        # Load limits for known channels
        channel_names = ['CheMed123', 'lobelia4cosmetics', 'tikvahpharma']
        
        for channel in channel_names:
            env_key = f'MAX_IMAGES_{channel}'
            limit = os.getenv(env_key)
            if limit:
                try:
                    limits[channel] = int(limit)
                    logger.info(f"Loaded image limit for {channel}: {limits[channel]}")
                except ValueError:
                    logger.warning(f"Invalid MAX_IMAGES_{channel} value: {limit}. Using default.")
                    limits[channel] = DEFAULT_MAX_IMAGES
            else:
                limits[channel] = DEFAULT_MAX_IMAGES
        
        return limits
    
    def get_max_images_for_channel(self, channel_name: str) -> int:
        """
        Get the maximum image download limit for a specific channel.
        
        Args:
            channel_name: Name of the channel (can be display name or username)
            
        Returns:
            Maximum number of images allowed for this channel
        """
        # Normalize channel name for matching
        normalized_name = channel_name.lower().replace(' ', '').replace('_', '').replace('-', '')
        
        # Try exact match first
        if channel_name in self.channel_max_images:
            return self.channel_max_images[channel_name]
        
        # Try case-insensitive match
        for key, value in self.channel_max_images.items():
            if key.lower() == channel_name.lower():
                return value
        
        # Try normalized matching (e.g., "Lobelia pharmacy and cosmetics" -> "lobeliapharmacyandcosmetics")
        # Match against known channel patterns
        channel_mappings = {
            'lobelia': 'lobelia4cosmetics',
            'chemed': 'CheMed123',
            'tikvah': 'tikvahpharma'
        }
        
        for pattern, config_name in channel_mappings.items():
            if pattern in normalized_name and config_name in self.channel_max_images:
                return self.channel_max_images[config_name]
        
        # Default if not found
        return DEFAULT_MAX_IMAGES
    
    def get_config_channel_name(self, channel_name: str) -> str:
        """
        Get the configuration channel name for a given channel display name.
        
        Args:
            channel_name: Display name or username of the channel
            
        Returns:
            Configuration channel name used in .env
        """
        # Normalize for matching
        normalized_name = channel_name.lower().replace(' ', '').replace('_', '').replace('-', '')
        
        # Exact match
        if channel_name in self.channel_max_images:
            return channel_name
        
        # Case-insensitive match
        for key in self.channel_max_images.keys():
            if key.lower() == channel_name.lower():
                return key
        
        # Pattern matching
        channel_mappings = {
            'lobelia': 'lobelia4cosmetics',
            'chemed': 'CheMed123',
            'tikvah': 'tikvahpharma'
        }
        
        for pattern, config_name in channel_mappings.items():
            if pattern in normalized_name:
                return config_name
        
        return channel_name
    
    async def connect(self):
        """Initialize and connect to Telegram."""
        try:
            self.client = TelegramClient(
                str(self.session_path),
                self.api_id,
                self.api_hash
            )
            
            await self.client.start()
            
            if not await self.client.is_user_authorized():
                phone = input('Please enter your phone number: ')
                await self.client.send_code_request(phone)
                code = input('Enter the code: ')
                
                try:
                    await self.client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input('Two-step verification enabled. Enter password: ')
                    await self.client.sign_in(password=password)
            
            logger.info("Successfully connected to Telegram")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {str(e)}")
            return False
    
    async def scrape_channel(
        self,
        channel_username: str,
        limit: Optional[int] = None,
        offset_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Scrape messages from a Telegram channel.
        
        Args:
            channel_username: Username of the channel (e.g., 'lobelia4cosmetics')
            limit: Maximum number of messages to scrape (None for all)
            offset_date: Only scrape messages after this date
            
        Returns:
            List of message dictionaries
        """
        if not self.client:
            logger.error("Client not connected. Call connect() first.")
            return []
        
        messages = []
        
        try:
            logger.info(f"Starting scrape for channel: {channel_username}")
            
            # Get channel entity
            try:
                entity = await self.client.get_entity(channel_username)
            except UsernameNotOccupiedError:
                logger.error(f"Channel {channel_username} does not exist or is not accessible")
                return []
            except ChannelPrivateError:
                logger.error(f"Channel {channel_username} is private and cannot be accessed")
                return []
            
            channel_name = entity.title or channel_username
            logger.info(f"Channel found: {channel_name}")
            
            # Get config channel name for limit tracking
            config_channel = self.get_config_channel_name(channel_name)
            max_images = self.get_max_images_for_channel(channel_name)
            
            # Initialize counter if needed and count existing images
            if config_channel not in self.downloaded_images_count:
                # Count existing images for this channel
                image_dir = Path(f"data/raw/images/{channel_name}")
                existing_count = 0
                if image_dir.exists():
                    existing_count = len(list(image_dir.glob("*.jpg")))
                    if existing_count > 0:
                        logger.info(
                            f"Found {existing_count} existing images for {channel_name}. "
                            f"Limit: {max_images}"
                        )
                
                self.downloaded_images_count[config_channel] = existing_count
                
                # Check if limit already reached
                if existing_count >= max_images:
                    logger.warning(
                        f"Image download limit already reached for {channel_name} "
                        f"({existing_count}/{max_images}). Will skip image downloads and only scrape text messages."
                    )
                    self.channel_limit_reached.add(config_channel)
            else:
                # Check if limit reached during this session
                if self.downloaded_images_count[config_channel] >= max_images:
                    if config_channel not in self.channel_limit_reached:
                        logger.warning(
                            f"Image download limit reached for {channel_name} "
                            f"({self.downloaded_images_count[config_channel]}/{max_images}). "
                            f"Will skip image downloads and only scrape text messages."
                        )
                        self.channel_limit_reached.add(config_channel)
            
            # Scrape messages
            logger.info(f"Starting to iterate messages from {channel_name}...")
            message_count = 0
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                offset_date=offset_date
            ):
                try:
                    message_count += 1
                    # Log progress every 50 messages (more frequent for visibility)
                    if message_count % 50 == 0:
                        if config_channel in self.channel_limit_reached:
                            logger.info(
                                f"Scraping text messages from {channel_name}: "
                                f"{message_count} messages processed (images skipped - limit reached)"
                            )
                        else:
                            logger.info(
                                f"Scraping {channel_name}: {message_count} messages processed"
                            )
                    # Also log first message to confirm loop is working
                    elif message_count == 1:
                        logger.info(f"Processing first message from {channel_name}...")
                    
                    message_data = await self.extract_message_data(message, channel_name)
                    if message_data:
                        messages.append(message_data)
                        
                        # Download image if present (respects channel-specific MAX_IMAGES limit)
                        # Continue scraping text messages even if image limit is reached
                        if message_data.get('has_media') and message_data.get('image_path'):
                            downloaded = await self.download_image(
                                message,
                                channel_name,
                                message_data['message_id']
                            )
                            # If limit reached, log info but continue scraping text messages
                            if not downloaded and config_channel in self.channel_limit_reached:
                                # Already logged warning once, just continue without downloading images
                                pass
                    
                    # Handle rate limiting
                    await asyncio.sleep(0.5)  # Be respectful to Telegram API
                    
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    logger.error(f"Error processing message {message.id}: {str(e)}")
                    continue
            
            # Log completion status
            if config_channel in self.channel_limit_reached:
                logger.info(
                    f"Completed scraping {len(messages)} messages from {channel_name}. "
                    f"Image limit reached ({self.downloaded_images_count.get(config_channel, 0)}/{max_images}), "
                    f"but all text messages were scraped. Moving to next channel."
                )
            else:
                logger.info(f"Scraped {len(messages)} messages from {channel_name}")
            
            self.scraped_channels.add(channel_name)
            
        except Exception as e:
            logger.error(f"Error scraping channel {channel_username}: {str(e)}")
        
        return messages
    
    async def extract_message_data(
        self,
        message: Message,
        channel_name: str
    ) -> Optional[Dict]:
        """
        Extract relevant data from a Telegram message.
        
        Args:
            message: Telethon Message object
            channel_name: Name of the channel
            
        Returns:
            Dictionary with message data or None if invalid
        """
        try:
            # Skip if message is empty or invalid
            if not message or not hasattr(message, 'id'):
                return None
            
            # Extract message data
            message_data = {
                'message_id': message.id,
                'channel_name': channel_name,
                'message_date': message.date.isoformat() if message.date else None,
                'message_text': message.text or '',
                'has_media': message.media is not None,
                'image_path': None,
                'views': message.views or 0,
                'forwards': message.forwards or 0,
                'is_reply': message.is_reply,
                'reply_to_msg_id': message.reply_to_msg_id if message.is_reply else None,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Check if message has photo media
            if message.media and isinstance(message.media, MessageMediaPhoto):
                image_filename = f"{message.id}.jpg"
                message_data['image_path'] = f"data/raw/images/{channel_name}/{image_filename}"
            
            return message_data
            
        except Exception as e:
            logger.error(f"Error extracting message data: {str(e)}")
            return None
    
    async def download_image(
        self,
        message: Message,
        channel_name: str,
        message_id: int
    ) -> bool:
        """
        Download image from a message if present.
        
        Args:
            message: Telethon Message object
            channel_name: Name of the channel
            message_id: ID of the message
            
        Returns:
            True if image was downloaded or already exists, False if limit reached
        """
        try:
            if not message.media or not isinstance(message.media, MessageMediaPhoto):
                return False
            
            # Get config channel name for consistent tracking
            config_channel = self.get_config_channel_name(channel_name)
            max_images = self.get_max_images_for_channel(channel_name)
            
            # Initialize counter for this channel if not exists
            if config_channel not in self.downloaded_images_count:
                self.downloaded_images_count[config_channel] = 0
            
            # Check if we've reached the maximum image limit for this channel
            if self.downloaded_images_count[config_channel] >= max_images:
                # Only log warning once per channel
                if config_channel not in self.channel_limit_reached:
                    logger.warning(
                        f"Maximum image download limit reached for {channel_name} "
                        f"({max_images}). Skipping further image downloads for this channel."
                    )
                    self.channel_limit_reached.add(config_channel)
                return False
            
            # Create channel-specific directory
            image_dir = Path(f"data/raw/images/{channel_name}")
            image_dir.mkdir(parents=True, exist_ok=True)
            
            # Download image
            image_path = image_dir / f"{message_id}.jpg"
            
            if not image_path.exists():
                await self.client.download_media(message, file=str(image_path))
                self.downloaded_images_count[config_channel] += 1
                logger.debug(
                    f"Downloaded image {self.downloaded_images_count[config_channel]}/{max_images} "
                    f"for {channel_name}: {image_path}"
                )
            else:
                logger.debug(f"Image already exists: {image_path}")
            
            return True
                
        except Exception as e:
            logger.error(f"Error downloading image for message {message_id}: {str(e)}")
            return False
    
    def save_messages_to_json(
        self,
        messages: List[Dict],
        channel_name: str,
        date: Optional[datetime] = None
    ):
        """
        Save scraped messages to JSON file in the data lake structure.
        
        Partitioned directory structure: data/raw/telegram_messages/YYYY-MM-DD/channel_name.json
        This structure is optimized for:
        - Date-range queries (most common analytics pattern)
        - Incremental loading by date
        - Database partitioning strategies
        - dbt incremental models
        
        Args:
            messages: List of message dictionaries
            channel_name: Name of the channel
            date: Date for partitioning (defaults to today)
        """
        if not messages:
            logger.warning(f"No messages to save for {channel_name}")
            return
        
        # Use provided date or current date
        if date is None:
            date = datetime.now()
        
        # Create date-partitioned directory structure
        date_str = date.strftime("%Y-%m-%d")
        safe_channel_name = "".join(c for c in channel_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_channel_name = safe_channel_name.replace(' ', '_')
        
        # Partitioned structure: telegram_messages/{date}/{channel}.json
        output_dir = Path(f"data/raw/telegram_messages/{date_str}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save to JSON with channel name as filename
        output_file = output_dir / f"{safe_channel_name}.json"
        
        # Load existing data if file exists
        existing_data = []
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not read existing file {output_file}, creating new one")
        
        # Merge with new messages (avoid duplicates)
        existing_ids = {msg.get('message_id') for msg in existing_data}
        new_messages = [msg for msg in messages if msg.get('message_id') not in existing_ids]
        
        all_messages = existing_data + new_messages
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_messages, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(new_messages)} new messages to {output_file} (total: {len(all_messages)})")
        self.scraped_dates.add(date_str)
    
    async def scrape_multiple_channels(
        self,
        channel_usernames: List[str],
        limit_per_channel: Optional[int] = None
    ):
        """
        Scrape multiple channels in sequence.
        
        Args:
            channel_usernames: List of channel usernames to scrape
            limit_per_channel: Maximum messages per channel
        """
        if not self.client:
            await self.connect()
        
        for username in channel_usernames:
            try:
                messages = await self.scrape_channel(username, limit=limit_per_channel)
                
                if messages:
                    # Group messages by date for proper partitioning
                    messages_by_date = {}
                    for msg in messages:
                        msg_date = datetime.fromisoformat(msg['message_date']) if msg.get('message_date') else datetime.now()
                        date_key = msg_date.strftime("%Y-%m-%d")
                        
                        if date_key not in messages_by_date:
                            messages_by_date[date_key] = []
                        messages_by_date[date_key].append(msg)
                    
                    # Save messages grouped by date
                    channel_name = messages[0]['channel_name'] if messages else username
                    for date_str, date_messages in messages_by_date.items():
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        self.save_messages_to_json(date_messages, channel_name, date_obj)
                
                # Wait between channels to avoid rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing channel {username}: {str(e)}")
                continue
    
    async def close(self):
        """Close the Telegram client connection."""
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from Telegram")
    
    def get_scraping_summary(self) -> Dict:
        """Get a summary of scraping activity."""
        total_images = sum(self.downloaded_images_count.values())
        images_by_channel = {
            channel: {
                'downloaded': count,
                'max': self.get_max_images_for_channel(channel)
            }
            for channel, count in self.downloaded_images_count.items()
        }
        
        return {
            'channels_scraped': list(self.scraped_channels),
            'dates_scraped': list(self.scraped_dates),
            'total_channels': len(self.scraped_channels),
            'total_dates': len(self.scraped_dates),
            'images_downloaded': total_images,
            'images_by_channel': images_by_channel
        }


async def main():
    """
    Main function to run the scraper.
    
    Configure channels and run the scraping process.
    """
    # Get API credentials from environment
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file")
        return
    
    # Initialize scraper
    scraper = TelegramScraper(api_id, api_hash)
    
    try:
        # Connect to Telegram
        if not await scraper.connect():
            logger.error("Failed to connect to Telegram")
            return
        
        # Define channels to scrape
        # Note: Remove @ symbol if present, Telethon handles it
        channels = [
            'lobelia4cosmetics',
            'tikvahpharma',
            # Add more channels from et.tgstat.com/medicine
            # Example: 'chemed_channel' (update with actual username)
        ]
        
        logger.info(f"Starting scrape for {len(channels)} channels")
        
        # Scrape all channels
        await scraper.scrape_multiple_channels(
            channel_usernames=channels,
            limit_per_channel=100  # Adjust based on needs
        )
        
        # Print summary
        summary = scraper.get_scraping_summary()
        logger.info("Scraping Summary:")
        logger.info(f"  Channels scraped: {summary['total_channels']}")
        logger.info(f"  Dates covered: {summary['total_dates']}")
        logger.info(f"  Total images downloaded: {summary['images_downloaded']}")
        logger.info(f"  Images by channel:")
        for channel, stats in summary['images_by_channel'].items():
            logger.info(f"    {channel}: {stats['downloaded']}/{stats['max']}")
        logger.info(f"  Channels: {', '.join(summary['channels_scraped'])}")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
