"""Unit tests for src/search.py."""

import unittest

from src.search import Search, SearchResult


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

# Hand-crafted index_data that mirrors what indexer.build() produces.
# Page layout (tokens):
#   /1  → "good friends good"   → good×2 @[0,2], friends×1 @[1]
#   /2  → "good life"           → good×1 @[0],   life×1 @[1]
#   /3  → "life friends"        → life×1 @[0],   friends×1 @[1]

FIXTURE: dict = {
    "index": {
        "good": {
            "https://example.com/1": {"frequency": 2, "positions": [0, 2]},
            "https://example.com/2": {"frequency": 1, "positions": [0]},
        },
        "friends": {
            "https://example.com/1": {"frequency": 1, "positions": [1]},
            "https://example.com/3": {"frequency": 1, "positions": [1]},
        },
        "life": {
            "https://example.com/2": {"frequency": 1, "positions": [1]},
            "https://example.com/3": {"frequency": 1, "positions": [0]},
        },
    },
    "pages": {
        "https://example.com/1": {"title": "Page One", "snippet": "good friends good"},
        "https://example.com/2": {"title": "Page Two", "snippet": "good life"},
        "https://example.com/3": {"title": "Page Three", "snippet": "life friends"},
    },
}


def _search() -> Search:
    return Search(FIXTURE)


# ---------------------------------------------------------------------------
# print_word
# ---------------------------------------------------------------------------

class TestPrintWord(unittest.TestCase):

    def test_found_word_shows_token_as_heading(self):
        output = _search().print_word("good")
        self.assertTrue(output.startswith("good:"))

    def test_found_word_lists_all_urls(self):
        output = _search().print_word("good")
        self.assertIn("https://example.com/1", output)
        self.assertIn("https://example.com/2", output)

    def test_found_word_shows_frequency(self):
        output = _search().print_word("good")
        self.assertIn("frequency=2", output)
        self.assertIn("frequency=1", output)

    def test_found_word_shows_positions(self):
        output = _search().print_word("good")
        self.assertIn("positions=[0, 2]", output)

    def test_not_found_word_returns_message(self):
        output = _search().print_word("nonsense")
        self.assertIn("not found", output)
        self.assertNotIn("frequency", output)

    def test_case_insensitive_lookup(self):
        upper = _search().print_word("GOOD")
        lower = _search().print_word("good")
        self.assertEqual(upper, lower)

    def test_punctuation_ignored_in_lookup(self):
        with_punct = _search().print_word("good!")
        plain = _search().print_word("good")
        self.assertEqual(with_punct, plain)

    def test_non_indexable_input_returns_message(self):
        output = _search().print_word("123")
        self.assertIn("no indexable characters", output)
        self.assertNotIn("frequency", output)

    def test_empty_string_returns_message(self):
        output = _search().print_word("")
        self.assertIn("no indexable characters", output)

    def test_output_is_string(self):
        self.assertIsInstance(_search().print_word("good"), str)


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------

class TestFind(unittest.TestCase):

    # --- return type and structure ---

    def test_returns_list(self):
        self.assertIsInstance(_search().find(["good"]), list)

    def test_results_are_search_result_instances(self):
        results = _search().find(["good"])
        self.assertTrue(all(isinstance(r, SearchResult) for r in results))

    def test_result_has_url_title_snippet_score(self):
        result = _search().find(["good"])[0]
        self.assertTrue(hasattr(result, "url"))
        self.assertTrue(hasattr(result, "title"))
        self.assertTrue(hasattr(result, "snippet"))
        self.assertTrue(hasattr(result, "score"))

    # --- single-term queries ---

    def test_single_term_returns_all_matching_pages(self):
        urls = {r.url for r in _search().find(["good"])}
        self.assertEqual(urls, {"https://example.com/1", "https://example.com/2"})

    def test_single_term_not_in_index_returns_empty(self):
        self.assertEqual(_search().find(["nonsense"]), [])

    # --- multi-term intersection ---

    def test_multi_term_returns_pages_with_all_terms(self):
        # "good" is in /1 and /2; "friends" is in /1 and /3 → intersection = /1
        results = _search().find(["good", "friends"])
        urls = [r.url for r in results]
        self.assertEqual(urls, ["https://example.com/1"])

    def test_multi_term_no_overlap_returns_empty(self):
        # "good" in /1,/2 — "life" in /2,/3 — "friends" in /1,/3 → no page has all three
        self.assertEqual(_search().find(["good", "life", "friends"]), [])

    def test_multi_term_partial_overlap_excluded(self):
        results = _search().find(["good", "friends"])
        urls = [r.url for r in results]
        self.assertNotIn("https://example.com/2", urls)  # has good but not friends
        self.assertNotIn("https://example.com/3", urls)  # has friends but not good

    # --- ranking ---

    def test_ranked_by_score_descending(self):
        # /1 has good×2, /2 has good×1 → /1 should rank first
        results = _search().find(["good"])
        self.assertEqual(results[0].url, "https://example.com/1")
        self.assertEqual(results[1].url, "https://example.com/2")

    def test_score_is_sum_of_term_frequencies(self):
        # /1: good×2 + friends×1 = 3
        results = _search().find(["good", "friends"])
        self.assertEqual(results[0].score, 3)

    def test_higher_frequency_page_ranks_first(self):
        results = _search().find(["good"])
        self.assertGreater(results[0].score, results[1].score)

    # --- case and punctuation ---

    def test_case_insensitive_query(self):
        lower = _search().find(["good"])
        upper = _search().find(["GOOD"])
        self.assertEqual([r.url for r in lower], [r.url for r in upper])

    def test_punctuation_in_query_ignored(self):
        plain = _search().find(["good"])
        punct = _search().find(["good!"])
        self.assertEqual([r.url for r in plain], [r.url for r in punct])

    # --- edge cases ---

    def test_empty_terms_list_returns_empty(self):
        self.assertEqual(_search().find([]), [])

    def test_non_indexable_terms_returns_empty(self):
        self.assertEqual(_search().find(["123", "456"]), [])

    def test_result_contains_page_title(self):
        results = _search().find(["good"])
        result = next(r for r in results if r.url == "https://example.com/1")
        self.assertEqual(result.title, "Page One")

    def test_result_contains_page_snippet(self):
        results = _search().find(["good"])
        result = next(r for r in results if r.url == "https://example.com/1")
        self.assertEqual(result.snippet, "good friends good")

    def test_empty_index_returns_empty(self):
        empty_search = Search({"index": {}, "pages": {}})
        self.assertEqual(empty_search.find(["good"]), [])


if __name__ == "__main__":
    unittest.main()
