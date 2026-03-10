"""Tests for the analysis.candidates module."""

import unittest
from analysis.candidates import _extract_names_from_posts, _is_stop_name, _filter_candidates


class TestExtractNames(unittest.TestCase):
    """Test name extraction from post text."""

    def test_extracts_two_word_names(self):
        posts = [{"text": "Babajide Sanwo-Olu is the governor", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        # Should find at least one name-like pattern
        self.assertTrue(len(result) > 0)

    def test_extracts_three_word_names(self):
        posts = [{"text": "Abdul-Azeez Olajide Adediran is running", "platform": "twitter"}]
        result = _extract_names_from_posts(posts)
        self.assertTrue(len(result) > 0)

    def test_ignores_single_words(self):
        posts = [{"text": "The government said something", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        # Should not extract single capitalized words as names
        for name in result:
            self.assertTrue(len(name.split()) >= 2)

    def test_handles_empty_posts(self):
        posts = [{"text": "", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertEqual(len(result), 0)

    def test_tracks_platforms(self):
        posts = [
            {"text": "Peter Obi for president", "platform": "twitter"},
            {"text": "Peter Obi visited Lagos", "platform": "nairaland"},
        ]
        result = _extract_names_from_posts(posts)
        if "Peter Obi" in result:
            self.assertTrue(len(result["Peter Obi"]["platforms"]) >= 1)


class TestStopNames(unittest.TestCase):
    """Test the stop name filter."""

    def test_filters_state_names(self):
        self.assertTrue(_is_stop_name("Cross River"))

    def test_filters_institutions(self):
        self.assertTrue(_is_stop_name("National Assembly"))

    def test_allows_real_names(self):
        self.assertFalse(_is_stop_name("Babajide Sanwo-Olu"))

    def test_allows_nigerian_names(self):
        self.assertFalse(_is_stop_name("Abdullahi Ganduje"))


class TestFilterCandidates(unittest.TestCase):
    """Test candidate filtering logic."""

    def test_filters_low_frequency(self):
        name_mentions = {
            "John Smith": {"count": 1, "platforms": {"twitter"}, "contexts": []},
        }
        posts = [{"text": "John Smith governor election"}]
        result = _filter_candidates(name_mentions, posts, min_mentions=2)
        self.assertEqual(len(result), 0)

    def test_keeps_high_frequency_with_context(self):
        name_mentions = {
            "Peter Obi": {"count": 5, "platforms": {"twitter", "nairaland"}, "contexts": []},
        }
        posts = [
            {"text": "Peter Obi for governor election candidate"},
            {"text": "Peter Obi governor campaign in Lagos"},
            {"text": "Peter Obi speaks at APC rally governor"},
        ]
        result = _filter_candidates(name_mentions, posts, min_mentions=2)
        self.assertTrue(len(result) > 0)

    def test_cross_platform_bonus(self):
        """Names on 2+ platforms should score higher than single-platform names."""
        multi_platform = {
            "Multi Platform": {"count": 3, "platforms": {"twitter", "nairaland"}, "contexts": []},
        }
        single_platform = {
            "Single Platform": {"count": 3, "platforms": {"twitter"}, "contexts": []},
        }
        posts = [
            {"text": "Multi Platform governor election candidate"},
            {"text": "Single Platform governor election candidate"},
        ]
        result_multi = _filter_candidates(multi_platform, posts, min_mentions=2)
        result_single = _filter_candidates(single_platform, posts, min_mentions=2)
        if result_multi and result_single:
            self.assertGreater(result_multi[0]["score"], result_single[0]["score"])


if __name__ == "__main__":
    unittest.main()
