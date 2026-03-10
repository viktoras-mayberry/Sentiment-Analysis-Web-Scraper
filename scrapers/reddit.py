"""
Reddit scraper using PRAW (Python Reddit API Wrapper).

Searches configured subreddits (r/Nigeria, r/NigeriaNews, etc.) for
election-related submissions and their top-level comments.
"""

import praw
from datetime import datetime

from scrapers.base import BaseScraper
from utils.helpers import clean_text, anonymize_author, is_within_time_range


class RedditScraper(BaseScraper):
    """Scrapes Reddit for Nigerian election discussions using PRAW."""

    def __init__(self):
        super().__init__("reddit")
        self.subreddits = self.platform_config.get(
            "subreddits", ["Nigeria", "NigeriaNews", "Africa"]
        )
        self.reddit_client = None

    def _connect(self):
        """
        Initialize the PRAW Reddit client.

        PRAW needs three credentials from config.yaml:
        - client_id: Your Reddit app's ID (the short string under the app name)
        - client_secret: Your Reddit app's secret key
        - user_agent: A descriptive string identifying your app to Reddit

        We use "read_only=True" because we only need to read posts —
        we never post, vote, or modify anything.
        """
        creds = self.api_credentials
        if not creds.get("client_id") or creds["client_id"] == "YOUR_REDDIT_CLIENT_ID":
            self.logger.warning(
                "Reddit API credentials not configured. "
                "Set client_id and client_secret in config.yaml"
            )
            return False

        try:
            self.reddit_client = praw.Reddit(
                client_id=creds["client_id"],
                client_secret=creds["client_secret"],
                user_agent=creds.get("user_agent", "NigeriaElectionScraper/1.0"),
                read_only=True,  # We only read, never write
            )
            # Test the connection by accessing the user identity
            self.reddit_client.user.me()
            self.logger.info("Connected to Reddit API successfully")
            return True
        except Exception as e:
            # read_only mode doesn't need user.me() — it may raise an exception
            # but the client still works for reading public data
            if self.reddit_client:
                self.logger.info("Reddit client initialized (read-only mode)")
                return True
            self.logger.error(f"Failed to connect to Reddit API: {e}")
            return False

    def scrape_state(self, state):
        """
        Scrape Reddit for posts about a state's governorship election.

        Flow:
        1. Connect to Reddit API via PRAW
        2. For each configured subreddit (r/Nigeria, r/NigeriaNews, r/Africa):
           a. Search using each keyword template for this state
           b. Collect matching submissions (posts)
           c. For each submission, also collect its top comments
        3. Return all collected data in standard format
        """
        self.logger.info(f"Scraping Reddit for {state}...")

        if not self.reddit_client and not self._connect():
            self.logger.warning("Skipping Reddit — not connected")
            return []

        all_posts = []
        keywords = self.get_keywords(state)
        seen_ids = set()  # Track submission IDs to avoid duplicates

        for subreddit_name in self.subreddits:
            if len(all_posts) >= self.max_posts:
                break

            try:
                subreddit = self.reddit_client.subreddit(subreddit_name)
                self.logger.debug(f"Searching r/{subreddit_name}...")

                for keyword in keywords:
                    if len(all_posts) >= self.max_posts:
                        break

                    # Search this subreddit with the keyword
                    # time_filter="year" aligns with our 12-month config
                    # sort="relevance" gives us the most relevant results first
                    try:
                        search_results = subreddit.search(
                            keyword,
                            sort="relevance",
                            time_filter="year",
                            limit=25,  # Per keyword per subreddit
                        )

                        for submission in search_results:
                            if submission.id in seen_ids:
                                continue
                            seen_ids.add(submission.id)

                            # Process the submission itself
                            sub_post = self._process_submission(
                                submission, state, keyword
                            )
                            if sub_post:
                                all_posts.append(sub_post)

                            # Process top-level comments on this submission
                            comment_posts = self._process_comments(
                                submission, state, keyword
                            )
                            all_posts.extend(comment_posts)

                            if len(all_posts) >= self.max_posts:
                                break

                    except Exception as e:
                        self.logger.warning(
                            f"Search failed for '{keyword}' in r/{subreddit_name}: {e}"
                        )
                        continue

            except Exception as e:
                self.logger.warning(f"Failed to access r/{subreddit_name}: {e}")
                continue

        self.logger.info(f"Reddit: Collected {len(all_posts)} posts for {state}")
        return all_posts

    def _process_submission(self, submission, state, keyword):
        """
        Convert a Reddit submission (post) into our standard format.

        A submission has:
        - title: The post headline
        - selftext: The body text (empty for link posts)
        - author: The Reddit username (we anonymize this)
        - created_utc: Unix timestamp of when it was posted
        - score: Net upvotes (upvotes minus downvotes) — maps to our "likes"
        - num_comments: Total comment count — maps to our "shares" (engagement proxy)
        - permalink: URL path to the post on Reddit

        We combine title + selftext because the title frames the topic
        and the body contains the actual discussion/opinion.
        """
        try:
            # Build full text from title + body
            text = submission.title
            if submission.selftext:
                text += " " + submission.selftext
            text = clean_text(text)

            if not text or len(text) < 20:
                return None

            # Check time range
            post_date = datetime.utcfromtimestamp(submission.created_utc)
            if not is_within_time_range(post_date):
                return None

            return {
                "platform": "reddit",
                "state": state,
                "text": text,
                "author": anonymize_author(
                    str(submission.author) if submission.author else None
                ),
                "date": post_date.strftime("%Y-%m-%d %H:%M:%S"),
                "url": f"https://reddit.com{submission.permalink}",
                "likes": submission.score,        # Net upvotes
                "shares": submission.num_comments, # Comments as engagement metric
                "keyword_used": keyword,
            }
        except Exception as e:
            self.logger.debug(f"Error processing submission: {e}")
            return None

    def _process_comments(self, submission, state, keyword, max_comments=10):
        """
        Extract top-level comments from a submission.

        Why collect comments?
        Comments often contain the strongest opinions and sentiments —
        someone replying to a political post is actively engaging with the topic.

        We only take the top `max_comments` to avoid:
        1. Hitting API rate limits on very popular threads
        2. Collecting low-quality deeply nested replies
        3. Blowing past our max_posts limit on a single thread
        """
        comments = []

        try:
            # Replace "MoreComments" objects with actual comments (limited depth)
            submission.comments.replace_more(limit=0)

            for comment in submission.comments[:max_comments]:
                try:
                    text = clean_text(comment.body)

                    if not text or len(text) < 20:
                        continue

                    # Check time range
                    comment_date = datetime.utcfromtimestamp(comment.created_utc)
                    if not is_within_time_range(comment_date):
                        continue

                    comments.append({
                        "platform": "reddit",
                        "state": state,
                        "text": text,
                        "author": anonymize_author(
                            str(comment.author) if comment.author else None
                        ),
                        "date": comment_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "url": f"https://reddit.com{comment.permalink}",
                        "likes": comment.score,
                        "shares": 0,  # Comments don't have a share count
                        "keyword_used": keyword,
                    })
                except Exception as e:
                    self.logger.debug(f"Error processing comment: {e}")
                    continue

        except Exception as e:
            self.logger.debug(f"Error loading comments: {e}")

        return comments
