"""
YAML configuration loader. Provides a singleton Config object with
API keys, state lists, keyword templates, and platform settings.
"""

import os
import yaml
from datetime import datetime, timedelta


# Path to config.yaml (sits at project root, one level above this file)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")


class Config:
    """Holds all configuration values loaded from config.yaml."""

    def __init__(self, config_path=None):
        path = config_path or CONFIG_PATH
        with open(path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

        # --- General settings ---
        general = self._raw.get("general", {})
        self.time_range_months = general.get("time_range_months", 12)
        self.max_posts_per_platform = general.get("max_posts_per_platform", 500)
        self.request_delay = general.get("request_delay", 2)
        self.max_retries = general.get("max_retries", 3)
        self.log_level = general.get("log_level", "INFO")

        # Calculate the start date: today minus time_range_months
        self.start_date = datetime.now() - timedelta(days=self.time_range_months * 30)

        # --- States ---
        self.states = self._raw.get("states", ["Lagos", "Kano"])

        # --- Keyword templates ---
        self._keyword_templates = self._raw.get("keywords", [])

        # --- API keys ---
        self.api_keys = self._raw.get("api_keys", {})

        # --- Platform settings ---
        self.platforms = self._raw.get("platforms", {})

        # --- Sentiment settings ---
        self.sentiment = self._raw.get("sentiment", {})

        # --- Storage settings ---
        self.storage = self._raw.get("storage", {})

    def get_keywords_for_state(self, state):
        """Expand keyword templates for a specific state."""
        return [kw.replace("{state}", state) for kw in self._keyword_templates]

    def is_platform_enabled(self, platform_name):
        """Check if a platform is enabled in config."""
        platform = self.platforms.get(platform_name, {})
        return platform.get("enabled", False)

    def get_platform_config(self, platform_name):
        """Get the full config dict for a specific platform."""
        return self.platforms.get(platform_name, {})

    def get_api_key(self, platform_name):
        """Get API credentials for a platform."""
        return self.api_keys.get(platform_name, {})


# Singleton instance — import this from anywhere in the project
config = Config()
