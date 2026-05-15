"""Builds, saves, and loads the inverted index."""

import json
import re
import logging
from pathlib import Path

from src.crawler import Page

logger = logging.getLogger(__name__)

INDEX_PATH = Path("data/index.json")
SNIPPET_LENGTH = 200


def tokenise(text: str) -> list[str]:
    """Lowercase and split text into alphabetic tokens, discarding punctuation.

    Args:
        text: Raw visible text from a page.

    Returns:
        Ordered list of tokens.
    """
    return re.findall(r"[a-z]+", text.lower())


def build(pages: list[Page]) -> dict:
    """Build an inverted index from a list of crawled pages.

    The returned dict has two top-level keys:

    - ``index``: maps each token to a dict of {url: {frequency, positions}}
    - ``pages``: maps each url to {title, snippet, token_count}

    Args:
        pages: Pages returned by the crawler.

    Returns:
        Index dict ready to be passed to ``save`` or ``Search``.
    """
    index: dict[str, dict[str, dict]] = {}
    page_meta: dict[str, dict] = {}

    for page in pages:
        tokens = tokenise(page.text)

        for position, token in enumerate(tokens):
            entry = index.setdefault(token, {})
            if page.url not in entry:
                entry[page.url] = {"frequency": 0, "positions": []}
            entry[page.url]["frequency"] += 1
            entry[page.url]["positions"].append(position)

        title = page.text.split("\n")[0][:80].strip()
        snippet = page.text[:SNIPPET_LENGTH].strip()
        page_meta[page.url] = {
            "title": title,
            "snippet": snippet,
            "token_count": len(tokens),
        }

    logger.info("Indexed %d tokens across %d pages", len(index), len(pages))
    return {"index": index, "pages": page_meta}


def save(index_data: dict, path: Path = INDEX_PATH) -> None:
    """Serialise the index dict to a JSON file.

    Args:
        index_data: Dict produced by ``build``.
        path: Destination file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    logger.info("Index saved to %s", path)


def load(path: Path = INDEX_PATH) -> dict:
    """Load a previously saved index from disk.

    Args:
        path: Path to the JSON index file.

    Returns:
        Index dict with ``index`` and ``pages`` keys.

    Raises:
        FileNotFoundError: If no index file exists at ``path``.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No index found at '{path}'. Run 'build' first."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Index loaded from %s", path)
    return data
