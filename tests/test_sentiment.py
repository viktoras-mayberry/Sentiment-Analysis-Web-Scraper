"""Tests for the analysis.sentiment module."""

import unittest
from analysis.sentiment import SentimentAnalyzer


class TestSentimentAnalyzer(unittest.TestCase):
    """Test the sentiment analysis system."""

    @classmethod
    def setUpClass(cls):
        """Initialize analyzer once for all tests."""
        cls.analyzer = SentimentAnalyzer()

    def test_returns_dict_with_required_keys(self):
        result = self.analyzer.analyze("This is a test.")
        self.assertIn("label", result)
        self.assertIn("score", result)
        self.assertIn("confidence", result)

    def test_label_is_valid(self):
        result = self.analyzer.analyze("Great work by the governor!")
        self.assertIn(result["label"], ["positive", "negative", "neutral"])

    def test_score_in_range(self):
        result = self.analyzer.analyze("Terrible performance in office.")
        self.assertGreaterEqual(result["score"], -1.0)
        self.assertLessEqual(result["score"], 1.0)

    def test_positive_text(self):
        result = self.analyzer.analyze(
            "The governor has done excellent work. Infrastructure improved greatly."
        )
        # Should lean positive (or at least not strongly negative)
        self.assertGreaterEqual(result["score"], -0.3)

    def test_negative_text(self):
        result = self.analyzer.analyze(
            "Terrible corruption and failure. The worst governor ever."
        )
        # Should lean negative (or at least not strongly positive)
        self.assertLessEqual(result["score"], 0.3)

    def test_handles_empty_string(self):
        result = self.analyzer.analyze("")
        self.assertEqual(result["label"], "neutral")

    def test_handles_none(self):
        result = self.analyzer.analyze(None)
        self.assertEqual(result["label"], "neutral")

    def test_handles_long_text(self):
        """Should handle texts longer than 1000 chars without error."""
        long_text = "This is a test. " * 200
        result = self.analyzer.analyze(long_text)
        self.assertIn("label", result)

    def test_batch_analysis(self):
        texts = ["Good governor", "Bad leadership", "Neutral statement"]
        results = self.analyzer.analyze_batch(texts)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("label", r)
            self.assertIn("score", r)


class TestSentimentAnalyzerPidgin(unittest.TestCase):
    """Test handling of Nigerian Pidgin English."""

    @classmethod
    def setUpClass(cls):
        cls.analyzer = SentimentAnalyzer()

    def test_pidgin_positive(self):
        """Should handle Pidgin text without crashing."""
        result = self.analyzer.analyze("Dis governor don try well well for our state")
        self.assertIn("label", result)

    def test_pidgin_negative(self):
        result = self.analyzer.analyze("E no do anything for us. Na failure be this one")
        self.assertIn("label", result)


if __name__ == "__main__":
    unittest.main()
