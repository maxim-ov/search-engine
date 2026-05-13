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


def _same_domain(base: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def _extract(url: str, html: str) -> Page:
    """Parse HTML into visible text and absolute links."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    links = []
    for a in soup.find_all("a", href=True):
        absolute = urljoin(url, a["href"])
        # Strip fragments and query strings to avoid duplicate pages
        parsed = urlparse(absolute)._replace(fragment="", query="")
        links.append(parsed.geturl())

    return Page(url=url, text=text, links=links)


def crawl(start_url: str, politeness: float = POLITENESS_WINDOW) -> list[Page]:
    """BFS crawl of start_url, staying within the same domain.

    Args:
        start_url: The URL to begin crawling from.
        politeness: Seconds to wait between successive HTTP requests.

    Returns:
        List of Page objects for every successfully fetched page.
    """
    visited: set[str] = set()
    frontier: deque[str] = deque([start_url])
    pages: list[Page] = []

    session = requests.Session()
    session.headers["User-Agent"] = "COMP3011-SearchEngine/1.0"

    while frontier:
        url = frontier.popleft()

        if url in visited:
            continue
        visited.add(url)

        try:
            logger.info("Fetching %s", url)
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Skipping %s — %s", url, exc)
            time.sleep(politeness)
            continue

        page = _extract(url, response.text)
        pages.append(page)

        for link in page.links:
            if link not in visited and _same_domain(start_url, link):
                frontier.append(link)

        time.sleep(politeness)

    return pages
