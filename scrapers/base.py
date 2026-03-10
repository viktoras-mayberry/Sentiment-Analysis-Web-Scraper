"""
Base Scraper
============
Abstract base class that all platform scrapers (Twitter, Reddit, Nairaland,
Facebook) must inherit from.
"""

from abc import ABC, abstractmethod
from utils.config import config
from utils.logger import get_logger


class BaseScraper(ABC):
    """Abstract base class for all platform scrapers."""

    def __init__(self, platform_name):
        self.platform_name = platform_name
        self.logger = get_logger(f"scrapers.{platform_name}")
        self.config = config
        self.platform_config = config.get_platform_config(platform_name)
        self.api_credentials = config.get_api_key(platform_name)
        self.max_posts = config.max_posts_per_platform

    @abstractmethod
    def scrape_state(self, state):
        """Scrape data for a specific state"""
        pass

    def get_keywords(self, state):
        """Get expanded search keywords for a state."""
        return self.config.get_keywords_for_state(state)

    def is_enabled(self):
        """Check if this platform is enabled in config."""
        return self.config.is_platform_enabled(self.platform_name)
