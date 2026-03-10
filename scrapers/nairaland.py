"""
Nairaland scraper using cloudscraper + BeautifulSoup.

Nairaland is Nigeria's largest online forum (~2M+ registered users). It has
no public API, so we parse HTML directly. The site uses Cloudflare protection,
which we handle via cloudscraper (a requests wrapper that solves Cloudflare
challenges automatically).

We browse the Politics board, filter threads by election-related keywords,
then scrape individual posts from relevant threads.
"""

from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import cloudscraper

from scrapers.base import BaseScraper
from utils.helpers import (
    retry_on_failure,
    respectful_delay,
    clean_text,
    anonymize_author,
    parse_date,
    is_within_time_range,
)


class NairalandScraper(BaseScraper):
    """Scrapes Nairaland forum for Nigerian election discussions."""

    def __init__(self):
        super().__init__("nairaland")
        self.base_url = self.platform_config.get(
            "base_url", "https://www.nairaland.com"
        )
        self.sections = self.platform_config.get("sections", ["politics"])
        self.scraper = cloudscraper.create_scraper()

    def _fetch_page(self, url):
        """Fetch a page using cloudscraper (handles Cloudflare automatically)."""
        try:
            resp = self.scraper.get(url, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def scrape_state(self, state):
        """
        Main entry point: scrape all posts related to a state's election.

        Strategy:
        1. Browse the Nairaland Politics board pages
        2. Find threads whose titles contain election-related keywords for the state
        3. Scrape individual posts from those relevant threads
        4. Return all posts in the standard format
        """
        self.logger.info(f"Scraping Nairaland for {state}...")
        all_posts = []
        seen_urls = set()

        keywords = self.get_keywords(state)

        # Primary: Browse the politics board and filter threads by relevance
        thread_urls = self._browse_politics_board(state, keywords, max_pages=5)
        self.logger.info(
            f"Found {len(thread_urls)} relevant threads for {state}"
        )

        for url in thread_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            if len(all_posts) >= self.max_posts:
                self.logger.info(
                    f"Reached max posts limit ({self.max_posts}) for {state}"
                )
                break

            posts = self._scrape_thread(url, state)
            all_posts.extend(posts)
            respectful_delay()

        # Secondary: Try the search endpoint for additional threads
        search_threads = self._search_threads(state, keywords)
        for url in search_threads:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            if len(all_posts) >= self.max_posts:
                break

            posts = self._scrape_thread(url, state)
            all_posts.extend(posts)
            respectful_delay()

        self.logger.info(
            f"Nairaland: Collected {len(all_posts)} posts for {state}"
        )
        return all_posts

    def _browse_politics_board(self, state, keywords, max_pages=5):
        """
        Browse the Nairaland Politics board and find threads relevant to
        this state's election.

        Nairaland's politics board URL pattern:
        - Page 0: /politics
        - Page 1: /politics/1
        - Page 2: /politics/2
        """
        relevant_threads = []
        state_lower = state.lower()

        # Build keyword set for matching thread titles
        match_terms = {state_lower, f"{state_lower} governor", f"{state_lower} election"}
        for kw in keywords:
            match_terms.add(kw.lower())

        for page in range(max_pages):
            url = (
                f"{self.base_url}/politics"
                if page == 0
                else f"{self.base_url}/politics/{page}"
            )
            self.logger.debug(f"Browsing politics board page {page}...")

            html = self._fetch_page(url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")

            found = 0
            for link in soup.find_all("a"):
                href = link.get("href", "")
                title = link.get_text(strip=True).lower()

                if not href or not title:
                    continue

                if not self._is_thread_url(href):
                    continue

                # Check if the thread title is relevant to this state's election
                if self._is_relevant_thread(title, state_lower):
                    full_url = (
                        href if href.startswith("http")
                        else f"{self.base_url}{href}"
                    )
                    if full_url not in relevant_threads:
                        relevant_threads.append(full_url)
                        found += 1
                        self.logger.debug(
                            f"  Relevant thread: {link.get_text(strip=True)[:60]}"
                        )

            self.logger.debug(f"Page {page}: found {found} relevant threads")

            if found == 0 and page > 0:
                break  # No more relevant content on deeper pages

            respectful_delay()

        return relevant_threads

    def _is_relevant_thread(self, title, state_lower):
        """Check if a thread title is relevant to a state's election."""
        # Must mention the state
        if state_lower not in title:
            return False

        # Check for election/political context
        election_words = {
            "governor", "governorship", "election", "candidate", "aspirant",
            "campaign", "vote", "ballot", "primary", "contest", "gubernatorial",
            "apc", "pdp", "lp", "nnpp", "apga", "political",
            "senator", "minister", "incumbent", "2027",
        }
        return any(word in title for word in election_words)

    def _search_threads(self, state, keywords):
        """
        Try the Nairaland search endpoint as a secondary source.
        May fail due to Cloudflare on some requests, so it's best-effort.
        """
        thread_urls = []

        for keyword in keywords[:3]:  # Limit to first 3 keywords
            encoded = quote_plus(keyword)
            url = f"{self.base_url}/search/{encoded}/0/0/0/1"

            html = self._fetch_page(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            for link in soup.find_all("a"):
                href = link.get("href", "")
                if href and self._is_thread_url(href):
                    full_url = (
                        href if href.startswith("http")
                        else f"{self.base_url}{href}"
                    )
                    if full_url not in thread_urls:
                        thread_urls.append(full_url)

            respectful_delay()

        self.logger.debug(f"Search found {len(thread_urls)} additional threads")
        return thread_urls

    def _is_thread_url(self, href):
        """Check if a URL is a valid Nairaland thread URL."""
        path = href.replace(self.base_url, "")
        if not path.startswith("/"):
            return False

        parts = path.strip("/").split("/")
        if len(parts) >= 1 and parts[0].isdigit():
            return True

        return False

    def _scrape_thread(self, url, state):
        """Scrape individual posts from a Nairaland thread."""
        posts = []

        html = self._fetch_page(url)
        if not html:
            return posts

        soup = BeautifulSoup(html, "lxml")

        # Find all post bodies on the page.
        # Nairaland wraps each post's content in a <div class="narrow">
        post_bodies = soup.find_all("div", class_="narrow")

        for post_div in post_bodies:
            try:
                # --- Extract post text ---
                text = post_div.get_text(separator=" ", strip=True)
                text = clean_text(text)

                # Skip empty or very short posts (likely not meaningful)
                if not text or len(text) < 20:
                    continue

                # --- Extract author ---
                author_tag = None
                parent_td = post_div.find_parent("td")
                if parent_td:
                    author_tag = parent_td.find("a", class_="user")

                if not author_tag:
                    parent_table = post_div.find_parent("table")
                    if parent_table:
                        author_tag = parent_table.find("a", class_="user")

                author = anonymize_author(
                    author_tag.text.strip() if author_tag else None
                )

                # --- Extract date ---
                date_str = ""
                date_span = None
                parent_table = post_div.find_parent("table")
                if parent_td:
                    date_span = parent_td.find("span", class_="s")
                if not date_span and parent_table:
                    date_span = parent_table.find("span", class_="s")

                if date_span:
                    date_str = date_span.get_text(strip=True)

                # Parse and validate date
                parsed_date = parse_date(date_str) if date_str else None
                if parsed_date and not is_within_time_range(parsed_date):
                    continue  # Skip posts outside our time range

                date_formatted = (
                    parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                    if parsed_date
                    else date_str
                )

                # --- Extract engagement metrics ---
                likes = 0
                likes_span = post_div.find("span", class_="likes")
                if likes_span:
                    try:
                        likes = int(
                            likes_span.get_text(strip=True)
                            .replace("Likes", "")
                            .replace("Like", "")
                            .strip()
                        )
                    except ValueError:
                        likes = 0

                # Build the standardized post dict
                post = {
                    "platform": "nairaland",
                    "state": state,
                    "text": text,
                    "author": author,
                    "date": date_formatted,
                    "url": url,
                    "likes": likes,
                    "shares": 0,  # Nairaland doesn't have a share concept
                    "keyword_used": f"{state} governorship election",
                }
                posts.append(post)

            except Exception as e:
                self.logger.debug(f"Error parsing a post in {url}: {e}")
                continue

        self.logger.debug(f"Extracted {len(posts)} posts from {url}")
        return posts
