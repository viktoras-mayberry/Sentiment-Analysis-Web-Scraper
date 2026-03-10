"""
Facebook scraper using the Graph API (v18.0).

Fetches posts and comments from configured public Facebook Pages, then
filters locally by election keywords. Unlike the other scrapers, Facebook
doesn't support keyword search on posts — so we pull page feeds and match
client-side.

Disabled by default in config.yaml because getting a non-expired access
token requires Facebook App Review, which can take weeks.
"""

import requests
from datetime import datetime

from scrapers.base import BaseScraper
from utils.helpers import (
    clean_text,
    anonymize_author,
    parse_date,
    is_within_time_range,
    respectful_delay,
    retry_on_failure,
)


GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class FacebookScraper(BaseScraper):
    """Scrapes Facebook public pages via Graph API for election discussions."""

    def __init__(self):
        super().__init__("facebook")
        self.access_token = self.api_credentials.get("access_token", "")
        self.page_ids = self.platform_config.get("page_ids", [])

    def _is_token_valid(self):
        """
        Check if the Facebook access token is configured and not a placeholder.

        Unlike Twitter/Reddit where missing credentials just mean "skip",
        Facebook also requires specific page_ids to be listed in config
        because we can't do keyword search.
        """
        if not self.access_token or self.access_token == "YOUR_FACEBOOK_ACCESS_TOKEN":
            self.logger.warning(
                "Facebook access token not configured. "
                "Set access_token in config.yaml under api_keys.facebook"
            )
            return False

        if not self.page_ids:
            self.logger.warning(
                "No Facebook page_ids configured. "
                "Add public page IDs to config.yaml under platforms.facebook.page_ids"
            )
            return False

        return True

    def scrape_state(self, state):
        """
        Scrape Facebook for posts about a state's governorship election.

        Flow:
        1. Validate access token and page_ids
        2. For each configured Facebook Page:
           a. Fetch recent posts from the page
           b. Filter posts that mention election keywords for this state
           c. Fetch comments on relevant posts
        3. Return all collected data in standard format

        This is fundamentally different from the other scrapers:
        - Nairaland/Twitter/Reddit: We SEARCH by keyword, then collect results.
        - Facebook: We fetch ALL posts from specific pages, then FILTER
          by keyword locally. This is because the Graph API doesn't support
          keyword search on posts.
        """
        self.logger.info(f"Scraping Facebook for {state}...")

        if not self._is_token_valid():
            self.logger.warning("Skipping Facebook — not configured")
            return []

        all_posts = []
        keywords = self.get_keywords(state)
        # Convert keywords to lowercase for case-insensitive matching
        keyword_lower = [kw.lower() for kw in keywords]

        for page_id in self.page_ids:
            if len(all_posts) >= self.max_posts:
                break

            try:
                page_posts = self._fetch_page_posts(page_id)

                for post_data in page_posts:
                    if len(all_posts) >= self.max_posts:
                        break

                    # Check if the post mentions any of our keywords
                    post_text = post_data.get("message", "").lower()
                    matched_keyword = None

                    for i, kw in enumerate(keyword_lower):
                        # Check if any significant part of the keyword appears
                        # We split the keyword and check if major terms appear
                        kw_terms = kw.split()
                        matches = sum(1 for term in kw_terms if term in post_text)
                        if matches >= len(kw_terms) // 2 + 1:
                            matched_keyword = keywords[i]
                            break

                    if not matched_keyword:
                        continue  # Post doesn't match any keywords — skip

                    # Process the matching post
                    processed = self._process_post(post_data, state, matched_keyword)
                    if processed:
                        all_posts.append(processed)

                    # Also fetch comments on this relevant post
                    comments = self._fetch_post_comments(
                        post_data["id"], state, matched_keyword
                    )
                    all_posts.extend(comments)

            except Exception as e:
                self.logger.warning(f"Failed to scrape page {page_id}: {e}")
                continue

        self.logger.info(f"Facebook: Collected {len(all_posts)} posts for {state}")
        return all_posts

    @retry_on_failure()
    def _fetch_page_posts(self, page_id):
        """
        Fetch recent posts from a Facebook Page using the Graph API.

        Graph API endpoint: GET /{page_id}/posts
        Required fields: message, created_time, id, shares
        Reactions are fetched via a sub-request (reactions.summary)

        The 'since' parameter filters by date — we use our configured
        start_date to only get posts within the time range.
        """
        posts = []
        # Calculate 'since' as Unix timestamp for the Graph API
        since_timestamp = int(self.config.start_date.timestamp())

        url = f"{GRAPH_API_BASE}/{page_id}/posts"
        params = {
            "access_token": self.access_token,
            "fields": "id,message,created_time,from,shares,reactions.summary(true)",
            "since": since_timestamp,
            "limit": 100,  # Max per page
        }

        while url and len(posts) < self.max_posts:
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    self.logger.warning(
                        f"Graph API error for page {page_id}: {data['error'].get('message')}"
                    )
                    break

                page_posts = data.get("data", [])
                posts.extend(page_posts)

                # Handle pagination — Graph API returns a 'next' URL
                paging = data.get("paging", {})
                url = paging.get("next")
                # Reset params since the 'next' URL includes them
                params = None

                respectful_delay()

            except requests.RequestException as e:
                self.logger.warning(f"Request failed for page {page_id}: {e}")
                break

        self.logger.debug(f"Fetched {len(posts)} posts from page {page_id}")
        return posts

    def _process_post(self, post_data, state, keyword):
        """Convert a Graph API post object into our standard format."""
        try:
            text = clean_text(post_data.get("message", ""))
            if not text or len(text) < 20:
                return None

            # Parse and validate date
            date_str = post_data.get("created_time", "")
            parsed_date = parse_date(date_str)
            if parsed_date and not is_within_time_range(parsed_date):
                return None

            # Extract author (anonymize the 'from' field)
            from_data = post_data.get("from", {})
            author = anonymize_author(from_data.get("name") or from_data.get("id"))

            # Extract engagement metrics
            reactions = post_data.get("reactions", {}).get("summary", {})
            likes = reactions.get("total_count", 0)
            shares = post_data.get("shares", {}).get("count", 0)

            # Construct URL
            post_id = post_data.get("id", "")
            post_url = f"https://facebook.com/{post_id}" if post_id else ""

            return {
                "platform": "facebook",
                "state": state,
                "text": text,
                "author": author,
                "date": parsed_date.strftime("%Y-%m-%d %H:%M:%S") if parsed_date else date_str,
                "url": post_url,
                "likes": likes,
                "shares": shares,
                "keyword_used": keyword,
            }
        except Exception as e:
            self.logger.debug(f"Error processing Facebook post: {e}")
            return None

    @retry_on_failure()
    def _fetch_post_comments(self, post_id, state, keyword, max_comments=20):
        """
        Fetch comments on a specific Facebook post.

        Graph API endpoint: GET /{post_id}/comments
        Comments are where public opinion is expressed most directly —
        someone commenting on a political post is actively engaging.
        """
        comments = []

        url = f"{GRAPH_API_BASE}/{post_id}/comments"
        params = {
            "access_token": self.access_token,
            "fields": "id,message,created_time,from,like_count",
            "limit": max_comments,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                self.logger.debug(
                    f"Error fetching comments for {post_id}: {data['error'].get('message')}"
                )
                return comments

            for comment in data.get("data", []):
                text = clean_text(comment.get("message", ""))
                if not text or len(text) < 10:
                    continue

                date_str = comment.get("created_time", "")
                parsed_date = parse_date(date_str)

                from_data = comment.get("from", {})
                author = anonymize_author(
                    from_data.get("name") or from_data.get("id")
                )

                comments.append({
                    "platform": "facebook",
                    "state": state,
                    "text": text,
                    "author": author,
                    "date": parsed_date.strftime("%Y-%m-%d %H:%M:%S") if parsed_date else date_str,
                    "url": f"https://facebook.com/{comment.get('id', '')}",
                    "likes": comment.get("like_count", 0),
                    "shares": 0,  # Comments don't have shares
                    "keyword_used": keyword,
                })

        except requests.RequestException as e:
            self.logger.debug(f"Failed to fetch comments for {post_id}: {e}")

        return comments
