# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Web crawler that generates a representative accessibility sample (muestra IRA) of pages from a given website. The output is used as input for WCAG accessibility audits — it does not perform the accessibility analysis itself.

The sample must satisfy IRA requirements: minimum 15 pages, at least 10% selected randomly, mandatory coverage of functional types (home, form, navigation).

## Commands

### Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
python crawler.py --url https://www.example.com
python crawler.py --url https://www.example.com --depth 4 --min-pages 20 --output-dir ./results
python crawler.py --url https://www.example.com --no-confine  # crawl full domain, not just root path
python crawler.py --url https://www.example.com --exclude logout admin --log-level DEBUG
```

Key CLI flags:
- `--depth N` — max crawl depth (default: 3)
- `--max-crawled N` — hard cap on pages fetched (default: 200)
- `--min-pages N` — minimum sample size (default: 15)
- `--random-pct PCT` — minimum % of randomly selected pages (default: 10.0)
- `--delay SEC` — delay between requests in seconds (default: 1.0)
- `--timeout MS` — per-page timeout in milliseconds (default: 15000)
- `--no-confine` — crawl the full domain instead of only under the root path
- `--exclude PATTERN [PATTERN ...]` — additional URL exclusion patterns

### Outputs

Results are written to `./output/` (or `--output-dir`):
- `sample_<timestamp>.json` — structured page list with metadata
- `crawler_<timestamp>.log` — execution log with warnings

## Architecture

The pipeline is a sequential async flow with 5 phases, each in its own module:

```
crawler.py (entry)
  └─ src/main.py          parse_args → build_config → main_async
       ├─ src/core/crawler.py     Phase 3.1: BFS crawl with Playwright
       ├─ src/core/classifier.py  Phase 3.2: DOM-based functional classification
       ├─ src/core/selector.py    Phase 3.3+3.4: directed + random selection
       ├─ src/core/validator.py   Phase 3.5: validate and auto-adjust sample
       └─ src/io/exporter.py      Phase 4: write JSON + log
```

### Key data types ([src/models/](src/models/))

- `Config` — all runtime parameters; built from CLI args in `main.py`
- `PageRecord` — one crawled page: URL, depth, source URL, full HTML snapshot, HTTP status, functional types, selection mode
- `QueueItem` — BFS queue entry (URL + depth + source URL)
- `FunctionalType` — `Literal["home", "form", "navigation", "dynamic", "informational"]`
- `SelectionMode` — `Literal["directed", "random"]`
- `MANDATORY_TYPES` — `frozenset({"home", "form", "navigation"})` — types that must be present in the final sample

### Crawl phase ([src/core/crawler.py](src/core/crawler.py))

Uses Playwright Chromium headless so JS-rendered content is captured. BFS by depth level with a semaphore capping parallelism at 3 concurrent tabs. Scope is controlled by `confine_to_path`: when true (default), only URLs under the root path are followed; when false, the full domain is crawled.

### Classification phase ([src/core/classifier.py](src/core/classifier.py))

Classification is based on DOM structure, not URL patterns, to handle CMS-generated non-semantic URLs. A page can have multiple types simultaneously. The "informational" type is a fallback applied when no other type (or only "home") is detected. Form detection requires ≥2 interactive fields plus a submit element to filter out trivial search bars.

### Selection phase ([src/core/selector.py](src/core/selector.py))

Directed selection happens in priority order: (1) one page per mandatory type, (2) depth diversity, (3) pages with the most functional types to maximize complexity coverage. Random selection draws from the remaining pool after directed picks.

### URL utilities ([src/utils/url.py](src/utils/url.py))

Fragment stripping (`#anchor`) is the primary deduplication mechanism. `is_under_path` vs `is_same_domain` controls crawl scope.
