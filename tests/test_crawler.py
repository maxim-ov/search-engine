"""Unit tests for src/crawler.py."""

import unittest
from unittest.mock import MagicMock, patch, call

import requests as req

from src.crawler import Page, _normalise_url, _same_domain, _extract, crawl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    """Return a mock requests.Response-like object."""
    resp = MagicMock()
    resp.text = html
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = req.HTTPError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _normalise_url
# ---------------------------------------------------------------------------

class TestNormaliseUrl(unittest.TestCase):

    def test_trailing_slash_stripped_from_path(self):
        self.assertEqual(
            _normalise_url("https://example.com/page/2/"),
            "https://example.com/page/2",
        )

    def test_root_path_preserved(self):
        # "/" must not become an empty path
        self.assertEqual(
            _normalise_url("https://example.com/"),
            "https://example.com/",
        )

    def test_scheme_lowercased(self):
        self.assertEqual(
            _normalise_url("HTTPS://example.com/page"),
            "https://example.com/page",
        )

    def test_host_lowercased(self):
        self.assertEqual(
            _normalise_url("https://EXAMPLE.COM/page"),
            "https://example.com/page",
        )

    def test_fragment_stripped(self):
        self.assertNotIn("#", _normalise_url("https://example.com/page#section"))

    def test_query_stripped(self):
        self.assertNotIn("?", _normalise_url("https://example.com/page?q=foo"))

    def test_different_trailing_slash_variants_equal(self):
        with_slash = _normalise_url("https://example.com/page/")
        without_slash = _normalise_url("https://example.com/page")
        self.assertEqual(with_slash, without_slash)

    def test_different_host_case_variants_equal(self):
        upper = _normalise_url("https://EXAMPLE.COM/page")
        lower = _normalise_url("https://example.com/page")
        self.assertEqual(upper, lower)


# ---------------------------------------------------------------------------
# _same_domain
# ---------------------------------------------------------------------------

class TestSameDomain(unittest.TestCase):

    def test_same_domain_returns_true(self):
        self.assertTrue(_same_domain(
            "https://quotes.toscrape.com/",
            "https://quotes.toscrape.com/page/2/",
        ))

    def test_different_domain_returns_false(self):
        self.assertFalse(_same_domain(
            "https://quotes.toscrape.com/",
            "https://example.com/page/",
        ))

    def test_subdomain_treated_as_different(self):
        self.assertFalse(_same_domain(
            "https://quotes.toscrape.com/",
            "https://sub.quotes.toscrape.com/",
        ))

    def test_same_domain_different_scheme(self):
        # http vs https share the same netloc, so netloc comparison passes
        self.assertTrue(_same_domain(
            "https://quotes.toscrape.com/",
            "http://quotes.toscrape.com/page/2/",
        ))


# ---------------------------------------------------------------------------
# _extract
# ---------------------------------------------------------------------------

class TestExtract(unittest.TestCase):

    def test_returns_page_namedtuple(self):
        page = _extract("https://example.com/", "<html><body>Hello</body></html>")
        self.assertIsInstance(page, Page)

    def test_text_extraction(self):
        html = "<html><body><p>Hello world</p></body></html>"
        page = _extract("https://example.com/", html)
        self.assertIn("Hello world", page.text)

    def test_script_tags_stripped(self):
        html = "<html><body><script>alert('xss')</script><p>Visible</p></body></html>"
        page = _extract("https://example.com/", html)
        self.assertNotIn("alert", page.text)
        self.assertIn("Visible", page.text)

    def test_style_tags_stripped(self):
        html = "<html><body><style>body { color: red; }</style><p>Text</p></body></html>"
        page = _extract("https://example.com/", html)
        self.assertNotIn("color", page.text)
        self.assertIn("Text", page.text)

    def test_noscript_tags_stripped(self):
        html = "<html><body><noscript>Enable JS</noscript><p>Main</p></body></html>"
        page = _extract("https://example.com/", html)
        self.assertNotIn("Enable JS", page.text)
        self.assertIn("Main", page.text)

    def test_relative_links_resolved_to_absolute(self):
        html = '<html><body><a href="/page/2/">Next</a></body></html>'
        page = _extract("https://quotes.toscrape.com/", html)
        # Trailing slash stripped by _normalise_url
        self.assertIn("https://quotes.toscrape.com/page/2", page.links)

    def test_absolute_links_preserved(self):
        html = '<html><body><a href="https://example.com/about">About</a></body></html>'
        page = _extract("https://example.com/", html)
        self.assertIn("https://example.com/about", page.links)

    def test_fragment_stripped_from_links(self):
        html = '<html><body><a href="/page/1/#section">Link</a></body></html>'
        page = _extract("https://quotes.toscrape.com/", html)
        self.assertIn("https://quotes.toscrape.com/page/1", page.links)
        self.assertNotIn("#section", "".join(page.links))

    def test_query_string_stripped_from_links(self):
        html = '<html><body><a href="/search?q=foo">Search</a></body></html>'
        page = _extract("https://quotes.toscrape.com/", html)
        self.assertNotIn("?q=foo", "".join(page.links))

    def test_no_links_returns_empty_list(self):
        html = "<html><body><p>No links here</p></body></html>"
        page = _extract("https://example.com/", html)
        self.assertEqual(page.links, [])

    def test_url_preserved_on_page(self):
        url = "https://quotes.toscrape.com/page/3/"
        page = _extract(url, "<html><body>x</body></html>")
        self.assertEqual(page.url, url)

    def test_empty_html(self):
        page = _extract("https://example.com/", "")
        self.assertEqual(page.text.strip(), "")
        self.assertEqual(page.links, [])


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------

PAGE_1_HTML = """
<html><body>
  <p>Page one content</p>
  <a href="/page/2/">Next</a>
  <a href="https://external.com/">External</a>
</body></html>
"""

PAGE_2_HTML = """
<html><body>
  <p>Page two content</p>
  <a href="/">Home</a>
</body></html>
"""


class TestCrawl(unittest.TestCase):

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_returns_list_of_pages(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.return_value = _mock_response(PAGE_1_HTML)

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        self.assertIsInstance(pages, list)
        self.assertTrue(all(isinstance(p, Page) for p in pages))

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_bfs_follows_internal_links(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),   # https://quotes.toscrape.com/
            _mock_response(PAGE_2_HTML),   # https://quotes.toscrape.com/page/2/
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        urls = [p.url for p in pages]
        self.assertIn("https://quotes.toscrape.com/", urls)
        self.assertIn("https://quotes.toscrape.com/page/2", urls)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_does_not_follow_external_links(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.return_value = _mock_response(PAGE_1_HTML)

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        urls = [p.url for p in pages]
        self.assertNotIn("https://external.com/", urls)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_does_not_visit_same_url_twice(self, MockSession, mock_sleep):
        # PAGE_2_HTML links back to "/" — should not re-fetch it
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),
            _mock_response(PAGE_2_HTML),
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        visited_urls = [p.url for p in pages]
        self.assertEqual(len(visited_urls), len(set(visited_urls)))
        self.assertEqual(session.get.call_count, 2)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_http_error_skipped_crawl_continues(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),        # start page — OK
            _mock_response("", status_code=404), # page/2/ — 404
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        # Only the start page should be returned; the 404 is skipped
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].url, "https://quotes.toscrape.com/")

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_connection_error_skipped_crawl_continues(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),
            req.ConnectionError("refused"),
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        self.assertEqual(len(pages), 1)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_timeout_skipped_crawl_continues(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),
            req.Timeout("timed out"),
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        self.assertEqual(len(pages), 1)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_politeness_sleep_called_each_request(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(PAGE_1_HTML),
            _mock_response(PAGE_2_HTML),
        ]

        crawl("https://quotes.toscrape.com/", politeness=6)

        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(6)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_politeness_sleep_called_on_error(self, MockSession, mock_sleep):
        import requests as req
        session = MockSession.return_value
        session.get.side_effect = req.ConnectionError("refused")

        crawl("https://quotes.toscrape.com/", politeness=6)

        mock_sleep.assert_called_once_with(6)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_empty_site_returns_empty_list(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.side_effect = req.ConnectionError("refused")

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        self.assertEqual(pages, [])

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_user_agent_header_set(self, MockSession, mock_sleep):
        session = MockSession.return_value
        session.get.return_value = _mock_response("<html><body></body></html>")

        crawl("https://quotes.toscrape.com/", politeness=0)

        # session.headers is a MagicMock; verify __setitem__ was called with User-Agent
        session.headers.__setitem__.assert_any_call("User-Agent", unittest.mock.ANY)
        set_value = session.headers.__setitem__.call_args[0][1]
        self.assertIn("COMP3011", set_value)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_same_url_different_trailing_slash_not_fetched_twice(self, MockSession, mock_sleep):
        # Both /page/2/ and /page/2 normalise to the same URL — only one fetch
        html = """
        <html><body>
          <a href="/page/2/">With slash</a>
          <a href="/page/2">Without slash</a>
        </body></html>
        """
        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(html),
            _mock_response("<html><body>Page 2</body></html>"),
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        self.assertEqual(session.get.call_count, 2)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.Session")
    def test_url_linked_from_multiple_pages_fetched_only_once(self, MockSession, mock_sleep):
        # /shared is linked from both /a and /b — should only be fetched once
        root = """
        <html><body>
          <a href="/a">A</a>
          <a href="/b">B</a>
        </body></html>
        """
        page_a = '<html><body><a href="/shared">Shared</a></body></html>'
        page_b = '<html><body><a href="/shared">Shared</a></body></html>'
        page_shared = "<html><body>Shared content</body></html>"

        session = MockSession.return_value
        session.get.side_effect = [
            _mock_response(root),
            _mock_response(page_a),
            _mock_response(page_b),
            _mock_response(page_shared),
        ]

        pages = crawl("https://quotes.toscrape.com/", politeness=0)

        fetched_urls = [call.args[0] for call in session.get.call_args_list]
        shared_fetches = [u for u in fetched_urls if u.endswith("/shared")]
        self.assertEqual(len(shared_fetches), 1)


if __name__ == "__main__":
    unittest.main()
