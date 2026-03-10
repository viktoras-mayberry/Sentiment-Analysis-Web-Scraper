"""Tests for the analysis.profiler module."""

import unittest
from analysis.profiler import (
    _calculate_sentiment_summary,
    _calculate_platform_breakdown,
    _get_top_excerpts,
    _extract_themes,
    _infer_demographics,
    _calculate_engagement,
)


class TestSentimentSummary(unittest.TestCase):
    """Test sentiment summary calculation."""

    def test_empty_data(self):
        result = _calculate_sentiment_summary([])
        self.assertEqual(result["overall_score"], 0.0)
        self.assertEqual(result["total_analyzed"], 0)

    def test_all_positive(self):
        data = [
            {"sentiment_score": 0.8, "sentiment_label": "positive"},
            {"sentiment_score": 0.6, "sentiment_label": "positive"},
        ]
        result = _calculate_sentiment_summary(data)
        self.assertGreater(result["overall_score"], 0)
        self.assertEqual(result["positive_pct"], 100.0)

    def test_mixed_sentiment(self):
        data = [
            {"sentiment_score": 0.8, "sentiment_label": "positive"},
            {"sentiment_score": -0.6, "sentiment_label": "negative"},
            {"sentiment_score": 0.0, "sentiment_label": "neutral"},
        ]
        result = _calculate_sentiment_summary(data)
        self.assertEqual(result["total_analyzed"], 3)
        self.assertAlmostEqual(result["positive_pct"], 33.3, places=1)


class TestPlatformBreakdown(unittest.TestCase):
    """Test platform-level sentiment breakdown."""

    def test_empty_data(self):
        result = _calculate_platform_breakdown([])
        self.assertEqual(result, {})

    def test_groups_by_platform(self):
        data = [
            {"platform": "twitter", "sentiment_score": 0.5, "sentiment_label": "positive"},
            {"platform": "nairaland", "sentiment_score": -0.3, "sentiment_label": "negative"},
        ]
        result = _calculate_platform_breakdown(data)
        self.assertIn("twitter", result)
        self.assertIn("nairaland", result)
        self.assertGreater(result["twitter"]["score"], result["nairaland"]["score"])


class TestTopExcerpts(unittest.TestCase):
    """Test excerpt extraction."""

    def test_returns_correct_count(self):
        data = [
            {"sentiment_label": "positive", "sentiment_score": 0.9, "text": "Great!", "platform": "twitter", "date": "2025-01-01"},
            {"sentiment_label": "positive", "sentiment_score": 0.7, "text": "Good work", "platform": "nairaland", "date": "2025-01-02"},
            {"sentiment_label": "negative", "sentiment_score": -0.5, "text": "Bad", "platform": "reddit", "date": "2025-01-03"},
        ]
        result = _get_top_excerpts(data, "positive", n=2)
        self.assertEqual(len(result), 2)

    def test_filters_by_label(self):
        data = [
            {"sentiment_label": "positive", "sentiment_score": 0.9, "text": "Great!", "platform": "twitter", "date": "2025-01-01"},
            {"sentiment_label": "negative", "sentiment_score": -0.8, "text": "Terrible", "platform": "twitter", "date": "2025-01-02"},
        ]
        result = _get_top_excerpts(data, "negative", n=5)
        self.assertEqual(len(result), 1)
        self.assertIn("Terrible", result[0]["text"])

    def test_truncates_long_text(self):
        data = [
            {"sentiment_label": "positive", "sentiment_score": 0.5,
             "text": "A" * 300, "platform": "twitter", "date": "2025-01-01"},
        ]
        result = _get_top_excerpts(data, "positive", n=1)
        self.assertTrue(len(result[0]["text"]) <= 210)  # 200 + "..."


class TestThemeExtraction(unittest.TestCase):
    """Test theme extraction from posts."""

    def test_extracts_common_words(self):
        posts = [
            {"text": "infrastructure development in Lagos is improving"},
            {"text": "infrastructure roads and bridges are great"},
            {"text": "infrastructure projects completed this year"},
        ]
        result = _extract_themes(posts, "Some Name")
        theme_words = [t["theme"] for t in result]
        self.assertIn("infrastructure", theme_words)

    def test_excludes_candidate_name(self):
        posts = [{"text": "Babajide is doing well Babajide is great"}]
        result = _extract_themes(posts, "Babajide Test")
        theme_words = [t["theme"] for t in result]
        self.assertNotIn("babajide", theme_words)

    def test_handles_empty_posts(self):
        result = _extract_themes([], "Name")
        self.assertEqual(result, [])


class TestDemographicInsights(unittest.TestCase):
    """Test demographic inference from posts."""

    def test_tracks_platform_audience(self):
        posts = [
            {"text": "John Doe is great governor", "platform": "twitter"},
            {"text": "John Doe for governor", "platform": "twitter"},
            {"text": "John Doe candidate", "platform": "nairaland"},
        ]
        result = _infer_demographics(posts, "John Doe")
        self.assertIn("twitter", result["platform_audience"])
        self.assertEqual(result["platform_audience"]["twitter"]["posts"], 2)

    def test_detects_youth_indicator(self):
        posts = [
            {"text": "John Doe supports youth empowerment as governor", "platform": "twitter"},
            {"text": "John Doe connects with young voters", "platform": "nairaland"},
        ]
        result = _infer_demographics(posts, "John Doe")
        categories = [s["category"] for s in result["support_indicators"]]
        self.assertIn("youth", categories)

    def test_handles_empty_posts(self):
        result = _infer_demographics([], "Name")
        self.assertEqual(result["support_indicators"], [])


class TestEngagement(unittest.TestCase):
    """Test engagement metrics calculation."""

    def test_sums_likes_and_shares(self):
        posts = [
            {"likes": 10, "shares": 5},
            {"likes": 20, "shares": 10},
        ]
        result = _calculate_engagement(posts)
        self.assertEqual(result["total_likes"], 30)
        self.assertEqual(result["total_shares"], 15)
        self.assertEqual(result["avg_likes"], 15.0)

    def test_handles_empty(self):
        result = _calculate_engagement([])
        self.assertEqual(result["total_likes"], 0)


if __name__ == "__main__":
    unittest.main()
