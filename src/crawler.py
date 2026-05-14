"""Web crawler for quotes.toscrape.com."""

import time
import logging
from collections import deque
from typing import NamedTuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

POLITENESS_WINDOW = 6  # seconds between requests


class Page(NamedTuple):
    url: str
    text: str
    links: list[str]


def _normalise_url(url: str) -> str:
    """Return a canonical form of url for deduplication.

    - Lowercases scheme and host (RFC 3986: these are case-insensitive)
    - Strips query strings and fragments
    - Removes trailing slashes from the path so /page/1 and /page/1/ are
      the same key (the root path "/" is left unchanged)
    """
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    normalised = p._replace(
        scheme=p.scheme.lower(),
        netloc=p.netloc.lower(),
        path=path,
        query="",
        fragment="",
    )
    return normalised.geturl()


def _same_domain(base: str, url: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()


def _extract(url: str, html: str) -> Page:
    """Parse HTML into visible text and absolute links."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    links = []
    for a in soup.find_all("a", href=True):
        absolute = urljoin(url, a["href"])
        links.append(_normalise_url(absolute))

    return Page(url=url, text=text, links=links)


def crawl(
    start_url: str,
    politeness: float = POLITENESS_WINDOW,
) -> list[Page]:
    """BFS crawl of start_url, staying within the same domain.

    Args:
        start_url: The URL to begin crawling from.
        politeness: Seconds to wait between successive HTTP requests.

    Returns:
        List of Page objects for every successfully fetched page.
    """
    start_url = _normalise_url(start_url)
    # `seen` covers both visited pages and URLs already queued, preventing
    # the same URL from appearing in the frontier more than once.
    seen: set[str] = {start_url}
    frontier: deque[str] = deque([start_url])
    pages: list[Page] = []

    session = requests.Session()
    session.headers["User-Agent"] = "COMP3011-SearchEngine/1.0"

    while frontier:
        url = frontier.popleft()

        try:
            print(f"  [{len(pages) + 1}] {url}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"  Skipping {url} — {exc}")
            time.sleep(politeness)
            continue

        page = _extract(url, response.text)
        pages.append(page)

        for link in page.links:
            if link not in seen and _same_domain(start_url, link):
                seen.add(link)
                frontier.append(link)

        time.sleep(politeness)

    return pages
