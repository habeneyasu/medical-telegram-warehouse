"""
Unit tests for the Telegram scraper module.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.scraper import TelegramScraper, DEFAULT_MAX_IMAGES


class TestTelegramScraper:
    """Test cases for TelegramScraper class."""

    def test_initialization(self):
        """Test scraper initialization."""
        scraper = TelegramScraper("test_id", "test_hash")
        assert scraper.api_id == "test_id"
        assert scraper.api_hash == "test_hash"
        assert scraper.downloaded_images_count == {}
        assert len(scraper.channel_max_images) > 0

    def test_setup_directories(self):
        """Test directory setup."""
        scraper = TelegramScraper("test_id", "test_hash")
        assert Path("data/raw/telegram_messages").exists()
        assert Path("data/raw/images").exists()
        assert Path("logs").exists()

    def test_get_max_images_for_channel(self):
        """Test getting max images for a channel."""
        scraper = TelegramScraper("test_id", "test_hash")
        
        # Test exact match
        limit = scraper.get_max_images_for_channel("CheMed123")
        assert limit > 0
        
        # Test default
        limit = scraper.get_max_images_for_channel("UnknownChannel")
        assert limit == DEFAULT_MAX_IMAGES

    def test_get_config_channel_name(self):
        """Test config channel name mapping."""
        scraper = TelegramScraper("test_id", "test_hash")
        
        # Test exact match
        config_name = scraper.get_config_channel_name("CheMed123")
        assert config_name == "CheMed123"
        
        # Test pattern matching
        config_name = scraper.get_config_channel_name("Lobelia pharmacy and cosmetics")
        assert "lobelia" in config_name.lower()

    @pytest.mark.asyncio
    async def test_download_image_limit_reached(self):
        """Test image download respects limit."""
        scraper = TelegramScraper("test_id", "test_hash")
        scraper.downloaded_images_count["test_channel"] = 1500
        scraper.channel_max_images["test_channel"] = 1500
        scraper.channel_limit_reached.add("test_channel")
        
        message = MagicMock()
        message.media = None
        
        result = await scraper.download_image(message, "test_channel", 123)
        assert result is False

    def test_get_scraping_summary(self):
        """Test scraping summary generation."""
        scraper = TelegramScraper("test_id", "test_hash")
        scraper.scraped_channels.add("test_channel")
        scraper.scraped_dates.add("2026-01-17")
        scraper.downloaded_images_count["test_channel"] = 100
        
        summary = scraper.get_scraping_summary()
        assert "test_channel" in summary["channels_scraped"]
        assert "2026-01-17" in summary["dates_scraped"]
        assert summary["images_downloaded"] == 100


class TestChannelFinder:
    """Test cases for channel finder utility."""
    
    def test_get_medical_channels(self):
        """Test getting medical channels list."""
        from src.channel_finder import get_medical_channels
        
        channels = get_medical_channels()
        assert isinstance(channels, list)
        assert len(channels) > 0
        assert "CheMed123" in channels
        assert "lobelia4cosmetics" in channels
        assert "tikvahpharma" in channels

    def test_validate_channel_format(self):
        """Test channel format validation."""
        from src.channel_finder import validate_channel_format
        
        assert validate_channel_format("valid_channel") is True
        assert validate_channel_format("@valid_channel") is True
        assert validate_channel_format("ab") is False  # Too short
        assert validate_channel_format("invalid-channel!") is False  # Invalid chars
