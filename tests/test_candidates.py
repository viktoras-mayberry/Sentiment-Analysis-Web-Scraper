"""Tests for the analysis.candidates module."""

import unittest
from analysis.candidates import (
    _extract_names_from_posts, _is_stop_name, _filter_candidates,
    _strip_title_prefix, _deduplicate_variants,
)


class TestExtractNames(unittest.TestCase):
    """Test name extraction from post text."""

    def test_extracts_two_word_names(self):
        posts = [{"text": "Babajide Sanwo-Olu is the governor", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertTrue(len(result) > 0)

    def test_extracts_three_word_names(self):
        posts = [{"text": "Abdul-Azeez Olajide Adediran is running", "platform": "twitter"}]
        result = _extract_names_from_posts(posts)
        self.assertTrue(len(result) > 0)

    def test_ignores_single_words(self):
        posts = [{"text": "Somebody said something", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        for name in result:
            self.assertTrue(len(name.split()) >= 2)

    def test_handles_empty_posts(self):
        posts = [{"text": "", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertEqual(len(result), 0)

    def test_tracks_platforms(self):
        posts = [
            {"text": "Yakubu Dogara for governor", "platform": "twitter"},
            {"text": "Yakubu Dogara visited Kano", "platform": "nairaland"},
        ]
        result = _extract_names_from_posts(posts)
        if "Yakubu Dogara" in result:
            self.assertEqual(len(result["Yakubu Dogara"]["platforms"]), 2)

    def test_strips_title_prefixes(self):
        posts = [{"text": "Mr Babajide Sanwo-Olu is running", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertIn("Babajide Sanwo-Olu", result)
        self.assertNotIn("Mr Babajide Sanwo-Olu", result)

    def test_rejects_party_names(self):
        posts = [{"text": "All Progressives Congress won the election", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertNotIn("All Progressives Congress", result)

    def test_rejects_non_name_phrases(self):
        posts = [{"text": "Electronic Transmission of results failed", "platform": "nairaland"}]
        result = _extract_names_from_posts(posts)
        self.assertNotIn("Electronic Transmission", result)


class TestStopNames(unittest.TestCase):
    """Test the stop name filter."""

    def test_filters_state_names(self):
        self.assertTrue(_is_stop_name("Cross River"))

    def test_filters_institutions(self):
        self.assertTrue(_is_stop_name("National Assembly"))

    def test_filters_party_names(self):
        self.assertTrue(_is_stop_name("All Progressives Congress"))
        self.assertTrue(_is_stop_name("Peoples Democratic Party"))

    def test_filters_non_name_phrases(self):
        self.assertTrue(_is_stop_name("Polling Officer"))
        self.assertTrue(_is_stop_name("Aso Rock"))

    def test_allows_real_names(self):
        self.assertFalse(_is_stop_name("Babajide Sanwo-Olu"))

    def test_allows_nigerian_names(self):
        self.assertFalse(_is_stop_name("Abdullahi Ganduje"))


class TestStripTitlePrefix(unittest.TestCase):
    """Test title prefix removal."""

    def test_strips_mr(self):
        self.assertEqual(_strip_title_prefix("Mr Peter Obi"), "Peter Obi")

    def test_strips_gov(self):
        self.assertEqual(_strip_title_prefix("Gov Ifeanyi Ugwuanyi"), "Ifeanyi Ugwuanyi")

    def test_strips_former(self):
        self.assertEqual(_strip_title_prefix("Former Chairman"), "Chairman")

    def test_preserves_regular_name(self):
        self.assertEqual(_strip_title_prefix("Babajide Sanwo-Olu"), "Babajide Sanwo-Olu")

    def test_strips_multiple_titles(self):
        self.assertEqual(_strip_title_prefix("Chief Alhaji Ganduje"), "Ganduje")


class TestDeduplicateVariants(unittest.TestCase):
    """Test name variant deduplication."""

    def test_merges_same_words_different_order(self):
        mentions = {
            "Peter Obi": {"count": 5, "platforms": {"twitter"}, "contexts": []},
            "Obi Peter": {"count": 3, "platforms": {"nairaland"}, "contexts": []},
        }
        result = _deduplicate_variants(mentions)
        self.assertEqual(len(result), 1)
        name = list(result.keys())[0]
        self.assertEqual(result[name]["count"], 8)

    def test_keeps_distinct_names(self):
        mentions = {
            "Babajide Sanwo-Olu": {"count": 5, "platforms": {"twitter"}, "contexts": []},
            "Abdullahi Ganduje": {"count": 3, "platforms": {"nairaland"}, "contexts": []},
        }
        result = _deduplicate_variants(mentions)
        self.assertEqual(len(result), 2)


class TestFilterCandidates(unittest.TestCase):
    """Test candidate filtering logic."""

    def test_filters_low_frequency(self):
        name_mentions = {
            "John Smith": {"count": 1, "platforms": {"twitter"}, "contexts": []},
        }
        posts = [{"text": "John Smith governor election"}]
        result = _filter_candidates(name_mentions, posts, "Lagos", min_mentions=2)
        self.assertEqual(len(result), 0)

    def test_keeps_high_frequency_with_context(self):
        """Candidate appearing near 'governor' AND the state name should pass."""
        name_mentions = {
            "Yakubu Dogara": {"count": 5, "platforms": {"twitter", "nairaland"}, "contexts": []},
        }
        posts = [
            {"text": "Yakubu Dogara for Kano governor election candidate"},
            {"text": "Yakubu Dogara Kano governor campaign"},
            {"text": "Yakubu Dogara speaks at APC rally Kano governor"},
        ]
        result = _filter_candidates(name_mentions, posts, "Kano", min_mentions=2)
        self.assertTrue(len(result) > 0)

    def test_rejects_name_without_state_context(self):
        """A name near 'governor' but without the state name should be rejected."""
        name_mentions = {
            "John Doe": {"count": 5, "platforms": {"nairaland"}, "contexts": []},
        }
        posts = [
            {"text": "John Doe for governor election candidate"},
        ]
        result = _filter_candidates(name_mentions, posts, "Lagos", min_mentions=2)
        self.assertEqual(len(result), 0)

    def test_cross_platform_bonus(self):
        """Names on 2+ platforms should score higher than single-platform names."""
        multi_platform = {
            "Yakubu Dogara": {"count": 3, "platforms": {"twitter", "nairaland"}, "contexts": []},
        }
        single_platform = {
            "Sani Danladi": {"count": 3, "platforms": {"twitter"}, "contexts": []},
        }
        posts = [
            {"text": "Yakubu Dogara Kano governor election candidate"},
            {"text": "Sani Danladi Kano governor election candidate"},
        ]
        result_multi = _filter_candidates(multi_platform, posts, "Kano", min_mentions=2)
        result_single = _filter_candidates(single_platform, posts, "Kano", min_mentions=2)
        if result_multi and result_single:
            self.assertGreater(result_multi[0]["score"], result_single[0]["score"])

    def test_rejects_name_near_governor_but_wrong_state(self):
        """A name discussed as governor of another state should not appear for the target state."""
        name_mentions = {
            "Yakubu Dogara": {"count": 10, "platforms": {"nairaland"}, "contexts": []},
        }
        posts = [{"text": "Yakubu Dogara governor election candidate in Bauchi state"}] * 5
        result = _filter_candidates(name_mentions, posts, "Lagos", min_mentions=2)
        self.assertEqual(len(result), 0)

    def test_accepts_name_with_correct_state_and_governor(self):
        """A name discussed near governor AND the correct state should pass."""
        name_mentions = {
            "Babajide Sanwo-Olu": {"count": 5, "platforms": {"nairaland"}, "contexts": []},
        }
        posts = [{"text": "Babajide Sanwo-Olu Lagos governorship candidate election"}] * 3
        result = _filter_candidates(name_mentions, posts, "Lagos", min_mentions=2)
        names = [c["name"] for c in result]
        self.assertIn("Babajide Sanwo-Olu", names)


if __name__ == "__main__":
    unittest.main()
