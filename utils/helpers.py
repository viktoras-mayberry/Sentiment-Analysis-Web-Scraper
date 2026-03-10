"""
Shared utilities: retry decorator, rate-limit delay, text cleaning,
author anonymization, and date parsing.
"""

import time
import re
import hashlib
from datetime import datetime
from functools import wraps
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def retry_on_failure(max_retries=None, delay=1, backoff=2):
    """Decorator that retries a function on exception"""
    if max_retries is None:
        max_retries = config.max_retries

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator


def respectful_delay():
    """Pause between requests using the configured delay."""
    time.sleep(config.request_delay)


def clean_text(text):
    """Remove URLs and normalize whitespace. Preserves hashtags and mentions."""
    if not text:
        return ""
    # Remove URLs
    text = re.sub(r"http\S+|www\.\S+", "", text)
    # Remove excessive whitespace (multiple spaces, newlines)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def anonymize_author(author_name):
    """Anonymize author identifiers using a one-way hash"""
    if not author_name:
        return "anonymous"
    return hashlib.sha256(author_name.encode("utf-8")).hexdigest()[:12]


def parse_date(date_string, formats=None):
    """Try to parse a date string using multiple common formats"""
    if not date_string:
        return None

    date_string = date_string.strip()

    # Handle Nairaland format: "1:01pmOnFeb 12", "10:36pmOnFeb 05"
    nairaland_match = re.match(
        r"(\d{1,2}:\d{2}(?:am|pm))On(\w{3} \d{1,2})", date_string, re.IGNORECASE
    )
    if nairaland_match:
        time_part = nairaland_match.group(1)
        date_part = nairaland_match.group(2)
        current_year = datetime.now().year
        try:
            return datetime.strptime(
                f"{date_part} {current_year} {time_part}", "%b %d %Y %I:%M%p"
            )
        except ValueError:
            pass

    if formats is None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",   # ISO 8601 (Twitter, Reddit)
            "%Y-%m-%dT%H:%M:%SZ",       # ISO 8601 without microseconds
            "%Y-%m-%d %H:%M:%S",        # Standard datetime
            "%Y-%m-%d",                  # Date only
            "%b %d, %Y",                # "Jan 01, 2025" (Nairaland)
            "%d %b %Y",                 # "01 Jan 2025"
            "%B %d, %Y",                # "January 01, 2025"
        ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except (ValueError, AttributeError):
            continue

    logger.warning(f"Could not parse date: {date_string}")
    return None


def is_within_time_range(date_obj):
    """Check if a date falls within the configured time range"""
    if date_obj is None:
        return True  # If we can't parse the date, include it anyway
    return date_obj >= config.start_date
