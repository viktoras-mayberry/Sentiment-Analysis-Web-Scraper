"""
Twitter/X scraper using Tweepy (API v2).

Searches recent tweets via search_recent_tweets endpoint. Requires at
minimum a Basic-tier API key — the free tier doesn't support search.
Gracefully skips if credentials are missing or access is denied.
"""

import tweepy
from datetime import datetime

from scrapers.base import BaseScraper
from utils.helpers import clean_text, anonymize_author, is_within_time_range


class TwitterScraper(BaseScraper):
    """Scrapes Twitter/X for Nigerian election discussions using API v2."""

    def __init__(self):
        super().__init__("twitter")
        self.client = None
        self.max_results_per_query = self.platform_config.get(
            "max_results_per_query", 100
        )

    def _connect(self):
        """
        Initialize the Tweepy Client for API v2.

        API v2 uses a Bearer Token for app-only authentication.
        This gives read access to public tweets — we don't need user-level
        auth since we never post, like, or follow anything.

        The bearer_token comes from config.yaml under api_keys.twitter.
        You get one by creating a project at developer.twitter.com.
        """
        creds = self.api_credentials
        bearer_token = creds.get("bearer_token", "")

        if not bearer_token or bearer_token == "YOUR_TWITTER_BEARER_TOKEN":
            self.logger.warning(
                "Twitter API bearer token not configured. "
                "Set bearer_token in config.yaml under api_keys.twitter"
            )
            return False

        try:
            # Tweepy Client is the API v2 interface
            # wait_on_rate_limit=True tells Tweepy to automatically pause
            # when we hit rate limits instead of throwing an error.
            # This satisfies the task requirement for handling rate limits.
            self.client = tweepy.Client(
                bearer_token=bearer_token,
                wait_on_rate_limit=True,
            )
            self.logger.info("Connected to Twitter API v2 successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Twitter API: {e}")
            return False

    def scrape_state(self, state):
        """
        Scrape tweets about a state's governorship election.

        Flow:
        1. Connect to Twitter API v2
        2. For each keyword (e.g., "Lagos governorship election"):
           a. Search recent tweets matching the keyword
           b. Filter by time range and relevance
           c. Extract tweet text, author, metrics
        3. Return all collected tweets in standard format

        API v2 search_recent_tweets limitations:
        - Only returns tweets from the last 7 days (Basic tier)
        - Max 100 results per request, paginated via next_token
        - Rate limit: 450 requests per 15-minute window (Basic tier)
        """
        self.logger.info(f"Scraping Twitter for {state}...")

        if not self.client and not self._connect():
            self.logger.warning("Skipping Twitter — not connected")
            return []

        all_posts = []
        keywords = self.get_keywords(state)
        seen_ids = set()

        for keyword in keywords:
            if len(all_posts) >= self.max_posts:
                break

            # Build the search query
            # We add "-is:retweet" to exclude retweets — they duplicate content
            # and don't represent original opinions.
            # We add "lang:en" to focus on English tweets (Pidgin English
            # is often tagged as English by Twitter).
            query = f'"{keyword}" -is:retweet lang:en'

            # Twitter API v2 queries have a 512 character limit
            if len(query) > 512:
                query = f"{keyword} -is:retweet"

            try:
                tweets = self._search_tweets(query, keyword, state, seen_ids)
                all_posts.extend(tweets)
            except Exception as e:
                self.logger.warning(
                    f"Twitter search failed for '{keyword}': {e}"
                )
                continue

        self.logger.info(f"Twitter: Collected {len(all_posts)} tweets for {state}")
        return all_posts

    def _search_tweets(self, query, keyword, state, seen_ids):
        """
        Execute a Twitter API v2 search and process results.

        Uses Tweepy's Paginator to automatically handle pagination.
        The API returns max 100 tweets per page — Paginator fetches
        additional pages until we hit our limit.

        We request these tweet fields:
        - created_at: When the tweet was posted
        - public_metrics: likes, retweets, replies, quotes
        - author_id: Numeric user ID (we anonymize this)
        - text: The tweet content (always included by default)
        """
        tweets = []

        try:
            # Paginator handles multi-page results automatically
            # We cap at max_results_per_query (default 100) total tweets per keyword
            paginator = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=min(self.max_results_per_query, 100),  # API max per page is 100
                tweet_fields=["created_at", "public_metrics", "author_id"],
                limit=3,  # Max 3 pages of results per keyword
            )

            for response in paginator:
                if not response or not response.data:
                    break

                for tweet in response.data:
                    if tweet.id in seen_ids:
                        continue
                    seen_ids.add(tweet.id)

                    processed = self._process_tweet(tweet, state, keyword)
                    if processed:
                        tweets.append(processed)

                    if len(tweets) >= self.max_results_per_query:
                        return tweets

        except tweepy.TooManyRequests:
            self.logger.warning(
                "Twitter rate limit hit. Tweepy will auto-wait if configured."
            )
        except tweepy.Forbidden as e:
            self.logger.warning(
                f"Twitter API access forbidden — check your API tier. "
                f"Search requires Basic tier ($100/mo). Error: {e}"
            )
        except tweepy.Unauthorized:
            self.logger.error(
                "Twitter API authentication failed — check your bearer_token"
            )
        except Exception as e:
            self.logger.warning(f"Twitter search error: {e}")

        return tweets

    def _process_tweet(self, tweet, state, keyword):
        """
        Convert a Tweepy tweet object into our standard format.

        Tweet object attributes (API v2):
        - tweet.id: Unique tweet ID (int)
        - tweet.text: The tweet content
        - tweet.created_at: datetime object
        - tweet.author_id: Numeric author ID
        - tweet.public_metrics: dict with:
            - "like_count": Number of likes
            - "retweet_count": Number of retweets
            - "reply_count": Number of replies
            - "quote_count": Number of quote tweets

        We map:
        - like_count → likes (direct measure of approval)
        - retweet_count → shares (how widely the opinion spread)
        """
        try:
            text = clean_text(tweet.text)

            if not text or len(text) < 20:
                return None

            # Check time range
            tweet_date = tweet.created_at
            if tweet_date and not is_within_time_range(tweet_date):
                return None

            # Extract engagement metrics
            metrics = tweet.public_metrics or {}

            # Construct tweet URL
            # Format: https://twitter.com/user/status/{tweet_id}
            # Since we have author_id (not username), we use a generic format
            # that still resolves correctly
            tweet_url = f"https://twitter.com/i/web/status/{tweet.id}"

            return {
                "platform": "twitter",
                "state": state,
                "text": text,
                "author": anonymize_author(str(tweet.author_id)),
                "date": tweet_date.strftime("%Y-%m-%d %H:%M:%S") if tweet_date else "",
                "url": tweet_url,
                "likes": metrics.get("like_count", 0),
                "shares": metrics.get("retweet_count", 0),
                "keyword_used": keyword,
            }
        except Exception as e:
            self.logger.debug(f"Error processing tweet {tweet.id}: {e}")
            return None
