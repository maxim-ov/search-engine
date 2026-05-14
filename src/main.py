"""Interactive CLI shell for the search engine."""

import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports resolve whether
# the script is run as `python src/main.py` or `python -m src.main`.
sys.path.insert(0, str(Path(__file__).parent.parent))

import src.indexer as indexer
from src.crawler import crawl
from src.search import Search

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

START_URL = "https://quotes.toscrape.com/"

HELP_TEXT = """\
Commands:
  build              Crawl the website, build the index, and save it to disk.
  load               Load a previously built index from disk.
  print <word>       Print the inverted index entry for a word.
  find <word> ...    Find pages containing all listed words.
  help               Show this message.
  quit               Exit the shell.\
"""


def _require_index(search: Search | None) -> bool:
    """Print an error and return False if no index is loaded yet."""
    if search is None:
        print("No index loaded. Run 'build' or 'load' first.")
        return False
    return True


def run_shell(
    start_url: str = START_URL,
    index_path=indexer.INDEX_PATH,
) -> None:
    """Start the interactive REPL loop."""
    search: Search | None = None

    print("Search Engine — type 'help' for available commands.")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not raw:
            continue

        parts = raw.split()
        command = parts[0].lower()
        args = parts[1:]

        if command == "build":
            print(f"Crawling {start_url} ...")
            pages = crawl(start_url)
            print(f"Crawled {len(pages)} page(s). Building index ...")
            index_data = indexer.build(pages)
            indexer.save(index_data, index_path)
            search = Search(index_data)
            print(
                f"Done. Indexed {len(index_data['index'])} unique token(s) "
                f"across {len(index_data['pages'])} page(s). "
                f"Saved to '{index_path}'."
            )

        elif command == "load":
            try:
                index_data = indexer.load(index_path)
                search = Search(index_data)
                print(
                    f"Index loaded from '{index_path}' "
                    f"({len(index_data['index'])} token(s), "
                    f"{len(index_data['pages'])} page(s))."
                )
            except FileNotFoundError as exc:
                print(f"Error: {exc}")

        elif command == "print":
            if not _require_index(search):
                continue
            if not args:
                print("Usage: print <word>")
                continue
            print(search.print_word(args[0]))

        elif command == "find":
            if not _require_index(search):
                continue
            if not args:
                print("Usage: find <word> [word ...]")
                continue
            results = search.find(args)
            if not results:
                print(f"No pages found containing: {', '.join(args)}")
            else:
                print(f"Pages containing: {', '.join(args)}\n")
                for i, result in enumerate(results, start=1):
                    print(f"  {i}. {result.url}")
                    if result.title:
                        print(f"     {result.title}")
                    if result.snippet:
                        print(f"     {result.snippet[:120]} ...")
                    print(f"     [score: {result.score}]")

        elif command in ("help", "?"):
            print(HELP_TEXT)

        elif command in ("quit", "exit", "q"):
            print("Bye.")
            break

        else:
            print(f"Unknown command '{command}'. Type 'help' for available commands.")


if __name__ == "__main__":
    run_shell()
