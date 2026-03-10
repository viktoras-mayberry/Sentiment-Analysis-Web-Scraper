"""
Centralized logging setup. All modules log to both console and
output/scraper.log with consistent formatting.
"""

import os
import logging
from utils.config import config


# Create output directory for logs if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "scraper.log")


def get_logger(name):
    """Create a logger for a specific module"""
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    # Set the log level from config (DEBUG, INFO, WARNING, ERROR)
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Format: timestamp - module name - level - message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler — see output in real-time
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — persistent log for debugging
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # File captures everything
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
