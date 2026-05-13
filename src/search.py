"""Query logic: print and find commands."""

import logging
from dataclasses import dataclass

from src.indexer import tokenise

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    score: int  # sum of term frequencies across all query terms


class Search:
    """Executes queries against a loaded index."""

    def __init__(self, index_data: dict) -> None:
        self._index: dict[str, dict[str, dict]] = index_data["index"]
        self._pages: dict[str, dict] = index_data["pages"]

    def print_word(self, word: str) -> str:
        """Return a formatted string showing the posting list for a word.

        Args:
            word: The word to look up (case-insensitive).

        Returns:
            A human-readable string of the posting list, or a not-found message.
        """
        token = tokenise(word)
        if not token:
            return f"'{word}' contains no indexable characters."

        key = token[0]
        postings = self._index.get(key)
        if not postings:
            return f"'{key}' not found in index."

        lines = [f"{key}:"]
        for url, stats in postings.items():
            freq = stats["frequency"]
            positions = stats["positions"]
            lines.append(f"  {url}  frequency={freq}  positions={positions}")
        return "\n".join(lines)

    def find(self, terms: list[str]) -> list[SearchResult]:
        """Find pages containing all query terms, ranked by total frequency.

        Args:
            terms: Raw query terms (case-insensitive, punctuation ignored).

        Returns:
            List of SearchResult ordered by descending relevance score.
            Empty list if no terms are indexable or no pages match all terms.
        """
        tokens = [t for term in terms for t in tokenise(term)]
        if not tokens:
            return []

        # Collect the set of URLs that contain every token (intersection)
        matching_urls: set[str] | None = None
        for token in tokens:
            postings = self._index.get(token, {})
            urls_for_token = set(postings.keys())
            if matching_urls is None:
                matching_urls = urls_for_token
            else:
                matching_urls &= urls_for_token

        if not matching_urls:
            return []

        results = []
        for url in matching_urls:
            score = sum(
                self._index[token][url]["frequency"]
                for token in tokens
                if url in self._index.get(token, {})
            )
            meta = self._pages.get(url, {})
            results.append(SearchResult(
                url=url,
                title=meta.get("title", ""),
                snippet=meta.get("snippet", ""),
                score=score,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
