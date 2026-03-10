"""Tests for the storage.database module."""

import os
import json
import unittest
import tempfile
from storage.database import Database


class TestDatabase(unittest.TestCase):
    """Test the SQLite database manager."""

    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_and_retrieve_posts(self):
        posts = [
            {
                "platform": "nairaland",
                "state": "Lagos",
                "text": "Test post about election",
                "author": "anon123",
                "date": "2025-01-15",
                "url": "https://nairaland.com/test",
                "likes": 10,
                "shares": 5,
                "keyword_used": "Lagos governor",
            }
        ]
        self.db.save_posts(posts)
        result = self.db.get_posts_by_state("Lagos")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["platform"], "nairaland")
        self.assertEqual(result[0]["text"], "Test post about election")

    def test_deduplication_not_enforced_at_db_level(self):
        """Posts are saved as-is; deduplication happens in scrapers."""
        post = {
            "platform": "twitter", "state": "Kano", "text": "Test",
            "author": "x", "date": "2025-01-01", "url": "https://t.co/1",
            "likes": 0, "shares": 0, "keyword_used": "Kano",
        }
        self.db.save_posts([post, post])
        result = self.db.get_all_posts()
        self.assertEqual(len(result), 2)

    def test_save_and_retrieve_candidate(self):
        self.db.save_candidate("Babajide Sanwo-Olu", "Lagos", 15, ["nairaland", "twitter"])
        result = self.db.get_candidates_by_state("Lagos")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Babajide Sanwo-Olu")
        self.assertEqual(result[0]["mention_count"], 15)

    def test_save_and_retrieve_sentiment(self):
        # First save a post so we have a valid post_id
        self.db.save_posts([{
            "platform": "twitter", "state": "Lagos", "text": "Great governor",
            "author": "x", "date": "2025-01-01", "url": "https://t.co/1",
            "likes": 0, "shares": 0, "keyword_used": "Lagos",
        }])
        posts = self.db.get_all_posts()
        post_id = posts[0]["id"]

        self.db.save_sentiment(post_id, "Babajide Sanwo-Olu", "positive", 0.85, 0.92)
        result = self.db.get_sentiment_for_candidate("Babajide Sanwo-Olu")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sentiment_label"], "positive")

    def test_post_count(self):
        self.assertEqual(self.db.get_post_count(), 0)
        self.db.save_posts([{
            "platform": "reddit", "state": "Lagos", "text": "Test",
            "author": "x", "date": "2025-01-01", "url": "https://reddit.com/1",
            "likes": 0, "shares": 0, "keyword_used": "Lagos",
        }])
        self.assertEqual(self.db.get_post_count(), 1)

    def test_export_json(self):
        self.db.save_posts([{
            "platform": "nairaland", "state": "Lagos", "text": "Export test",
            "author": "x", "date": "2025-01-01", "url": "https://nairaland.com/1",
            "likes": 5, "shares": 2, "keyword_used": "Lagos",
        }])
        output_path = os.path.join(self.temp_dir, "export.json")
        self.db.export_to_json(output_path)
        self.assertTrue(os.path.exists(output_path))
        with open(output_path) as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)

    def test_export_csv(self):
        self.db.save_posts([{
            "platform": "twitter", "state": "Kano", "text": "CSV test",
            "author": "x", "date": "2025-01-01", "url": "https://t.co/1",
            "likes": 0, "shares": 0, "keyword_used": "Kano",
        }])
        output_path = os.path.join(self.temp_dir, "export.csv")
        self.db.export_to_csv(output_path)
        self.assertTrue(os.path.exists(output_path))

    def test_export_csv_empty(self):
        """CSV export should create file with headers even when empty."""
        output_path = os.path.join(self.temp_dir, "empty.csv")
        self.db.export_to_csv(output_path)
        self.assertTrue(os.path.exists(output_path))

    def test_get_posts_mentioning(self):
        self.db.save_posts([
            {"platform": "nairaland", "state": "Lagos",
             "text": "Babajide Sanwo-Olu is good",
             "author": "x", "date": "2025-01-01", "url": "https://n.com/1",
             "likes": 0, "shares": 0, "keyword_used": "Lagos"},
            {"platform": "nairaland", "state": "Lagos",
             "text": "Traffic is bad in Lagos",
             "author": "y", "date": "2025-01-02", "url": "https://n.com/2",
             "likes": 0, "shares": 0, "keyword_used": "Lagos"},
        ])
        result = self.db.get_posts_mentioning("Sanwo-Olu", "Lagos")
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
