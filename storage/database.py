"""
SQLite storage layer with JSON/CSV export.

Three tables: `posts` (raw scraped data), `candidates` (identified per state),
and `sentiment_results` (sentiment scores linked back to posts). Sentiment is
kept separate so analysis can be re-run without re-scraping.
"""

import os
import json
import csv
import sqlite3
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager for election scraper data."""

    def __init__(self, db_path=None):
        """Initialize database connection and create tables if they don't exist"""
        self.db_path = db_path or config.storage.get(
            "database", "output/data/election_data.db"
        )

        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        # Return rows as dictionaries instead of tuples — much easier to work with
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")

    def _create_tables(self):
        """Create the database schema"""
        # Table 1: Raw scraped posts from all platforms
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                state TEXT NOT NULL,
                text TEXT NOT NULL,
                author TEXT,
                date TEXT,
                url TEXT,
                likes INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                keyword_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 2: Identified candidates
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                state TEXT NOT NULL,
                mention_count INTEGER DEFAULT 0,
                platforms_found TEXT,
                first_seen TEXT,
                last_seen TEXT,
                UNIQUE(name, state)
            )
        """)

        # Table 3: Sentiment analysis results (linked to posts)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                candidate_name TEXT,
                sentiment_label TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                confidence REAL,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)

        self.conn.commit()

    # ----------------------------------------------------------------
    # SAVING DATA
    # ----------------------------------------------------------------

    def save_posts(self, posts):
        """Save a batch of scraped posts to the database"""
        if not posts:
            return

        self.cursor.executemany(
            """
            INSERT INTO posts (platform, state, text, author, date, url,
                             likes, shares, keyword_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    p.get("platform", ""),
                    p.get("state", ""),
                    p.get("text", ""),
                    p.get("author", ""),
                    p.get("date", ""),
                    p.get("url", ""),
                    p.get("likes", 0),
                    p.get("shares", 0),
                    p.get("keyword_used", ""),
                )
                for p in posts
            ],
        )
        self.conn.commit()
        logger.debug(f"Saved {len(posts)} posts to database")

    def save_candidate(self, name, state, mention_count, platforms_found):
        """Save or update a candidate record"""
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO candidates
                (name, state, mention_count, platforms_found)
            VALUES (?, ?, ?, ?)
            """,
            (name, state, mention_count, json.dumps(platforms_found)),
        )
        self.conn.commit()

    def save_sentiment(self, post_id, candidate_name, label, score, confidence):
        """
        Save a sentiment analysis result for a specific post.

        Links back to the posts table via post_id, and to a candidate name
        so we can aggregate sentiment per candidate later.
        """
        self.cursor.execute(
            """
            INSERT INTO sentiment_results
                (post_id, candidate_name, sentiment_label, sentiment_score, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (post_id, candidate_name, label, score, confidence),
        )
        self.conn.commit()

    # ----------------------------------------------------------------
    # QUERYING DATA
    # ----------------------------------------------------------------

    def get_posts_by_state(self, state):
        """Get all posts for a specific state."""
        self.cursor.execute(
            "SELECT * FROM posts WHERE state = ? ORDER BY date DESC", (state,)
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_posts_by_platform(self, platform):
        """Get all posts from a specific platform."""
        self.cursor.execute(
            "SELECT * FROM posts WHERE platform = ? ORDER BY date DESC",
            (platform,),
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_all_posts(self):
        """Get all posts in the database."""
        self.cursor.execute("SELECT * FROM posts ORDER BY date DESC")
        return [dict(row) for row in self.cursor.fetchall()]

    def get_posts_mentioning(self, candidate_name, state=None):
        """Find all posts that mention a candidate's name"""
        if state:
            self.cursor.execute(
                """SELECT * FROM posts
                   WHERE text LIKE ? AND state = ?
                   ORDER BY date DESC""",
                (f"%{candidate_name}%", state),
            )
        else:
            self.cursor.execute(
                """SELECT * FROM posts
                   WHERE text LIKE ?
                   ORDER BY date DESC""",
                (f"%{candidate_name}%",),
            )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_candidates_by_state(self, state):
        """Get all identified candidates for a state."""
        self.cursor.execute(
            "SELECT * FROM candidates WHERE state = ? ORDER BY mention_count DESC",
            (state,),
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_sentiment_for_candidate(self, candidate_name, state=None):
        """Get all sentiment results for a candidate"""
        if state:
            self.cursor.execute(
                """
                SELECT sr.*, p.text, p.platform, p.state, p.date, p.url
                FROM sentiment_results sr
                JOIN posts p ON sr.post_id = p.id
                WHERE sr.candidate_name = ? AND p.state = ?
                ORDER BY sr.sentiment_score DESC
                """,
                (candidate_name, state),
            )
        else:
            self.cursor.execute(
                """
                SELECT sr.*, p.text, p.platform, p.state, p.date, p.url
                FROM sentiment_results sr
                JOIN posts p ON sr.post_id = p.id
                WHERE sr.candidate_name = ?
                ORDER BY sr.sentiment_score DESC
                """,
                (candidate_name,),
            )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_post_count(self):
        """Get total number of posts in the database."""
        self.cursor.execute("SELECT COUNT(*) as count FROM posts")
        return self.cursor.fetchone()["count"]

    # ----------------------------------------------------------------
    # EXPORT — JSON & CSV
    # ----------------------------------------------------------------

    def export_to_json(self, output_path=None):
        """Export all posts to a JSON file"""
        if output_path is None:
            output_path = "output/data/scraped_posts.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        posts = self.get_all_posts()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(posts)} posts to {output_path}")
        return output_path

    def export_to_csv(self, output_path=None):
        """Export all posts to a CSV file"""
        if output_path is None:
            output_path = "output/data/scraped_posts.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        posts = self.get_all_posts()
        if not posts:
            # Write empty CSV with headers so the deliverable file always exists
            fieldnames = [
                "id", "platform", "state", "text", "author", "date",
                "url", "likes", "shares", "keyword_used", "created_at",
            ]
        else:
            fieldnames = posts[0].keys()
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(posts)

        logger.info(f"Exported {len(posts)} posts to {output_path}")
        return output_path

    def export_sentiment_to_json(self, output_path=None):
        """Export all sentiment results with joined post data to JSON."""
        if output_path is None:
            output_path = "output/data/sentiment_results.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self.cursor.execute("""
            SELECT sr.*, p.text, p.platform, p.state, p.date, p.url
            FROM sentiment_results sr
            JOIN posts p ON sr.post_id = p.id
            ORDER BY p.state, sr.candidate_name, sr.sentiment_score DESC
        """)
        results = [dict(row) for row in self.cursor.fetchall()]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(results)} sentiment results to {output_path}")
        return output_path

    # ----------------------------------------------------------------
    # CLEANUP
    # ----------------------------------------------------------------

    def close(self):
        """Close the database connection."""
        self.conn.close()
        logger.debug("Database connection closed")
