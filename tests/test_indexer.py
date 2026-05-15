"""Unit tests for src/indexer.py."""

import json
import tempfile
import unittest
from pathlib import Path

from src.crawler import Page
from src.indexer import tokenise, build, save, load


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page(url: str, text: str) -> Page:
    return Page(url=url, text=text, links=[])


# ---------------------------------------------------------------------------
# tokenise
# ---------------------------------------------------------------------------

class TestTokenise(unittest.TestCase):

    def test_basic_split(self):
        self.assertEqual(tokenise("hello world"), ["hello", "world"])

    def test_lowercased(self):
        self.assertEqual(tokenise("Hello WORLD"), ["hello", "world"])

    def test_punctuation_stripped(self):
        self.assertEqual(tokenise("it's good, isn't it?"), ["it", "s", "good", "isn", "t", "it"])

    def test_numbers_stripped(self):
        self.assertEqual(tokenise("page 42 of 100"), ["page", "of"])

    def test_empty_string(self):
        self.assertEqual(tokenise(""), [])

    def test_only_punctuation(self):
        self.assertEqual(tokenise("!!! --- ..."), [])

    def test_only_numbers(self):
        self.assertEqual(tokenise("123 456"), [])

    def test_mixed_alphanumeric(self):
        # "h2o" → only the alpha runs: "h" and "o"
        self.assertEqual(tokenise("h2o"), ["h", "o"])

    def test_preserves_order(self):
        self.assertEqual(tokenise("the quick brown fox"), ["the", "quick", "brown", "fox"])

    def test_extra_whitespace(self):
        self.assertEqual(tokenise("  hello   world  "), ["hello", "world"])


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

class TestBuild(unittest.TestCase):

    def test_returns_index_and_pages_keys(self):
        result = build([])
        self.assertIn("index", result)
        self.assertIn("pages", result)

    def test_empty_pages_returns_empty_index(self):
        result = build([])
        self.assertEqual(result["index"], {})
        self.assertEqual(result["pages"], {})

    def test_single_word_indexed(self):
        pages = [_page("https://example.com/", "hello")]
        result = build(pages)
        self.assertIn("hello", result["index"])

    def test_frequency_counted(self):
        pages = [_page("https://example.com/", "good good good")]
        result = build(pages)
        self.assertEqual(result["index"]["good"]["https://example.com/"]["frequency"], 3)

    def test_positions_recorded(self):
        pages = [_page("https://example.com/", "the quick the")]
        result = build(pages)
        self.assertEqual(
            result["index"]["the"]["https://example.com/"]["positions"], [0, 2]
        )

    def test_positions_are_token_indices_not_char_offsets(self):
        # "hello world hello" → tokens [hello=0, world=1, hello=2]
        pages = [_page("https://example.com/", "hello world hello")]
        result = build(pages)
        self.assertEqual(
            result["index"]["hello"]["https://example.com/"]["positions"], [0, 2]
        )
        self.assertEqual(
            result["index"]["world"]["https://example.com/"]["positions"], [1]
        )

    def test_case_insensitive_indexing(self):
        pages = [_page("https://example.com/", "Good good GOOD")]
        result = build(pages)
        self.assertIn("good", result["index"])
        self.assertNotIn("Good", result["index"])
        self.assertNotIn("GOOD", result["index"])
        self.assertEqual(result["index"]["good"]["https://example.com/"]["frequency"], 3)

    def test_word_across_multiple_pages(self):
        pages = [
            _page("https://example.com/1", "hello world"),
            _page("https://example.com/2", "hello again"),
        ]
        result = build(pages)
        self.assertIn("https://example.com/1", result["index"]["hello"])
        self.assertIn("https://example.com/2", result["index"]["hello"])

    def test_word_unique_to_one_page(self):
        pages = [
            _page("https://example.com/1", "unique word"),
            _page("https://example.com/2", "other content"),
        ]
        result = build(pages)
        self.assertNotIn("https://example.com/2", result["index"]["unique"])

    def test_page_metadata_stored(self):
        pages = [_page("https://example.com/", "Hello world")]
        result = build(pages)
        self.assertIn("https://example.com/", result["pages"])
        meta = result["pages"]["https://example.com/"]
        self.assertIn("title", meta)
        self.assertIn("snippet", meta)
        self.assertIn("token_count", meta)

    def test_token_count_stored(self):
        pages = [_page("https://example.com/", "hello world foo")]
        result = build(pages)
        self.assertEqual(result["pages"]["https://example.com/"]["token_count"], 3)

    def test_token_count_zero_for_empty_text(self):
        pages = [_page("https://example.com/", "")]
        result = build(pages)
        self.assertEqual(result["pages"]["https://example.com/"]["token_count"], 0)

    def test_snippet_content(self):
        pages = [_page("https://example.com/", "Hello world")]
        result = build(pages)
        self.assertIn("Hello world", result["pages"]["https://example.com/"]["snippet"])

    def test_snippet_truncated_to_200_chars(self):
        long_text = "word " * 100  # 500 chars
        pages = [_page("https://example.com/", long_text)]
        result = build(pages)
        self.assertLessEqual(len(result["pages"]["https://example.com/"]["snippet"]), 200)

    def test_punctuation_not_indexed(self):
        pages = [_page("https://example.com/", "hello, world!")]
        result = build(pages)
        self.assertNotIn("hello,", result["index"])
        self.assertNotIn("world!", result["index"])
        self.assertIn("hello", result["index"])
        self.assertIn("world", result["index"])

    def test_multiple_pages_all_appear_in_pages_meta(self):
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        pages = [_page(url, "some text") for url in urls]
        result = build(pages)
        for url in urls:
            self.assertIn(url, result["pages"])


# ---------------------------------------------------------------------------
# save and load
# ---------------------------------------------------------------------------

class TestSaveLoad(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name) / "index.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _sample_data(self) -> dict:
        pages = [
            _page("https://example.com/1", "hello world"),
            _page("https://example.com/2", "hello again"),
        ]
        return build(pages)

    def test_save_creates_file(self):
        save(self._sample_data(), self.tmp_path)
        self.assertTrue(self.tmp_path.exists())

    def test_save_creates_parent_directory(self):
        nested = Path(self._tmpdir.name) / "subdir" / "nested" / "index.json"
        save(self._sample_data(), nested)
        self.assertTrue(nested.exists())

    def test_save_writes_valid_json(self):
        save(self._sample_data(), self.tmp_path)
        with open(self.tmp_path) as f:
            data = json.load(f)
        self.assertIn("index", data)
        self.assertIn("pages", data)

    def test_load_returns_same_data(self):
        original = self._sample_data()
        save(original, self.tmp_path)
        loaded = load(self.tmp_path)
        self.assertEqual(original, loaded)

    def test_load_raises_if_file_missing(self):
        with self.assertRaises(FileNotFoundError):
            load(Path(self._tmpdir.name) / "nonexistent.json")

    def test_round_trip_preserves_frequency(self):
        original = self._sample_data()
        save(original, self.tmp_path)
        loaded = load(self.tmp_path)
        self.assertEqual(
            loaded["index"]["hello"]["https://example.com/1"]["frequency"],
            original["index"]["hello"]["https://example.com/1"]["frequency"],
        )

    def test_round_trip_preserves_positions(self):
        original = self._sample_data()
        save(original, self.tmp_path)
        loaded = load(self.tmp_path)
        self.assertEqual(
            loaded["index"]["hello"]["https://example.com/1"]["positions"],
            original["index"]["hello"]["https://example.com/1"]["positions"],
        )


if __name__ == "__main__":
    unittest.main()
