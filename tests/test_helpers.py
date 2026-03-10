"""Tests for the utils.helpers module."""

import unittest
from utils.helpers import clean_text, anonymize_author, parse_date


class TestCleanText(unittest.TestCase):
    """Test the text cleaning utility."""

    def test_removes_extra_whitespace(self):
        result = clean_text("hello   world")
        self.assertNotIn("   ", result)

    def test_strips_leading_trailing(self):
        result = clean_text("  hello  ")
        self.assertEqual(result, "hello")

    def test_handles_empty_string(self):
        result = clean_text("")
        self.assertEqual(result, "")

    def test_handles_none(self):
        result = clean_text(None)
        self.assertEqual(result, "")

    def test_preserves_meaningful_text(self):
        text = "Governor Sanwo-Olu is doing well"
        result = clean_text(text)
        self.assertIn("Sanwo-Olu", result)


class TestAnonymizeAuthor(unittest.TestCase):
    """Test the author anonymization utility."""

    def test_returns_hash_string(self):
        result = anonymize_author("real_user_name")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_consistent_hashing(self):
        """Same input should always produce same hash."""
        result1 = anonymize_author("user123")
        result2 = anonymize_author("user123")
        self.assertEqual(result1, result2)

    def test_different_inputs_different_hashes(self):
        result1 = anonymize_author("user_a")
        result2 = anonymize_author("user_b")
        self.assertNotEqual(result1, result2)

    def test_handles_empty_string(self):
        result = anonymize_author("")
        self.assertIsInstance(result, str)


class TestExtractDate(unittest.TestCase):
    """Test the date extraction utility."""

    def test_parses_standard_date(self):
        result = parse_date("2025-01-15")
        self.assertIsNotNone(result)

    def test_handles_invalid_date(self):
        result = parse_date("not a date")
        # Should return None for unparseable dates without crashing
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
