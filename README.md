# Search Engine — COMP3011 Coursework 2

A command-line search tool that crawls [quotes.toscrape.com](https://quotes.toscrape.com/), builds an inverted index, and lets you query it interactively with TF-IDF ranked results.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Design Decisions](#design-decisions)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Testing](#testing)
7. [Project Structure](#project-structure)
8. [Dependencies](#dependencies)

---

## Overview

This tool implements the three core components of a search engine:

- **Crawler** — BFS crawl of a target website, respecting a politeness window between requests.
- **Indexer** — builds an inverted index mapping each word to the pages it appears on, storing frequency and position data.
- **Search** — queries the index to find pages containing given terms, ranked by TF-IDF relevance.

---

## Architecture

```
quotes.toscrape.com
        │
        ▼
  ┌─────────────┐
  │   Crawler   │  BFS • politeness window • domain restriction
  └──────┬──────┘
         │  list[Page(url, text, links)]
         ▼
  ┌─────────────┐
  │   Indexer   │  tokenise • build inverted index • save/load JSON
  └──────┬──────┘
         │  {index: {word: {url: {frequency, positions}}}, pages: {url: {meta}}}
         ▼
  ┌─────────────┐
  │   Search    │  TF-IDF ranking • intersection • print/find commands
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  CLI Shell  │  build • load • print • find
  └─────────────┘
```

---

## Design Decisions

**Inverted index structure**

The index maps each token to a posting list of `{url: {frequency, positions}}`. Storing both frequency and positions enables TF-IDF scoring (uses frequency) and could support phrase-based or proximity queries in future (uses positions).

**Tokenisation**

`re.findall(r"[a-z]+", text.lower())` extracts only alphabetic runs after lowercasing. This handles case-insensitive search and strips punctuation and numbers in a single step without any manual character replacement.

**TF-IDF ranking**

Results are ranked by the sum of TF-IDF scores across all query terms:

- **TF** (term frequency) = `freq / token_count` — normalises for page length so long pages don't rank unfairly.
- **IDF** (inverse document frequency) = `log(N / df)` — down-weights common words that appear on nearly every page.

**URL normalisation**

All URLs are normalised before use as index keys: scheme and host are lowercased (RFC 3986), trailing slashes are stripped from non-root paths, and query strings and fragments are removed. This ensures `/page/1/` and `/page/1` are treated as the same page.

**Frontier deduplication (`seen` set)**

A `seen` set tracks both visited URLs and URLs already queued. A URL is added to `seen` at enqueue time, so the same URL can never appear in the BFS frontier more than once even if multiple pages link to it.

**JSON persistence**

The index is serialised to a single JSON file (`data/index.json`). JSON is human-readable (useful for inspection and debugging), requires no extra dependencies, and round-trips cleanly via Python's `json` module.

**Politeness window**

A configurable sleep (default 3 s) is enforced after every HTTP request, including failed ones, to avoid overwhelming the server. The parameter is injectable so tests can pass `politeness=0` and run instantly.

---

## Installation

**1. Clone the repository**

```bash
git clone <repository-url>
cd search-engine
```

**2. Create and activate a virtual environment** (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Usage

Start the interactive shell from the project root:

```bash
python src/main.py
```

### Commands

| Command | Description |
|---|---|
| `build` | Crawl the website, build the index, and save it to `data/index.json` |
| `load` | Load a previously built index from `data/index.json` |
| `print <word>` | Print the full inverted index entry for a word |
| `find <word> [word ...]` | Find all pages containing every listed word, ranked by TF-IDF |
| `help` | Show available commands |
| `quit` | Exit the shell |

### Examples

```
> build
Crawling https://quotes.toscrape.com/ ...
  [1] https://quotes.toscrape.com/
  [2] https://quotes.toscrape.com/page/2
  ...
Done. Indexed 1423 unique token(s) across 11 page(s). Saved to 'data/index.json'.

> load
Index loaded from 'data/index.json' (1423 token(s), 11 page(s)).

> print nonsense
nonsense:
  https://quotes.toscrape.com/page/2  frequency=1  positions=[47]

> find good friends
Pages containing: good, friends

  1. https://quotes.toscrape.com/page/3
     Quotes to Scrape
     Good friends, good books... [score: 0.0842]

  2. https://quotes.toscrape.com/page/7
     Quotes to Scrape
     A good friend is... [score: 0.0611]

> find nonsense
No pages found containing: nonsense

> find
Usage: find <word> [word ...]

> quit
Bye.
```

---

## Testing

Run the full test suite from the project root:

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a specific module:

```bash
pytest tests/test_crawler.py -v
pytest tests/test_indexer.py -v
pytest tests/test_search.py  -v
```

The test suite uses `unittest.mock` to patch HTTP requests, so all tests run offline and complete in under one second.

---

## Project Structure

```
search-engine/
├── src/
│   ├── crawler.py   — BFS crawler with URL normalisation and politeness window
│   ├── indexer.py   — tokeniser, inverted index builder, JSON save/load
│   ├── search.py    — TF-IDF ranking, print and find query logic
│   └── main.py      — interactive CLI shell (REPL)
├── tests/
│   ├── test_crawler.py
│   ├── test_indexer.py
│   └── test_search.py
├── data/
│   └── index.json   — compiled index (generated by `build`, submitted separately)
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| [requests](https://docs.python-requests.org/) | 2.32.3 | HTTP client for fetching pages |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) | 4.13.4 | HTML parsing and text extraction |

Install all dependencies with:

```bash
pip install -r requirements.txt
```
