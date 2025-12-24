# Idea Digest

A daily idea discovery and digest system that aggregates products, projects, and discussions from multiple platforms, scores them by relevance, persists them to Airtable, and generates human-readable daily digests.

## Purpose

Idea Digest solves the problem of information overload: instead of manually checking Product Hunt, Hacker News, and GitHub every day, it automatically fetches new items, filters them by your interests, and delivers a curated summary.

**Key capabilities:**
- Fetch from multiple sources in a single run
- Score items by theme relevance, recency, and popularity
- Deduplicate across runs (idempotent storage)
- Generate Markdown digests grouped by topic
- Run manually, via cron, or via GitHub Actions

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              IDEA DIGEST PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                      │
│   │ Product Hunt│   │ Hacker News │   │   GitHub    │    ◀── SOURCES       │
│   │    (RSS)    │   │ (Firebase)  │   │ (Scraping)  │                      │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                      │
│          │                 │                 │                              │
│          └────────────────┬┴─────────────────┘                              │
│                           ▼                                                 │
│                    ┌─────────────┐                                          │
│                    │  IdeaItem   │   ◀── Normalized data model              │
│                    │  (dataclass)│                                          │
│                    └──────┬──────┘                                          │
│                           │                                                 │
│                           ▼                                                 │
│   ┌───────────────────────────────────────────────────────────┐            │
│   │                      SCORING ENGINE                        │            │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │            │
│   │  │   Themes    │  │   Recency   │  │   Popularity    │    │            │
│   │  │  (keywords) │  │ (age decay) │  │   (points)      │    │            │
│   │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘    │            │
│   │         └────────────────┼──────────────────┘             │            │
│   │                          ▼                                 │            │
│   │            score = 0.4×theme + 0.3×recency + 0.3×popularity│           │
│   └───────────────────────────┬───────────────────────────────┘            │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────┐                                      │
│                    │    STORAGE      │   ◀── Airtable (or mock)            │
│                    │ (upsert/dedup)  │                                      │
│                    └────────┬────────┘                                      │
│                             │                                               │
│                             ▼                                               │
│                    ┌─────────────────┐                                      │
│                    │     DIGEST      │   ◀── Markdown output               │
│                    │   (generator)   │       digests/YYYY-MM-DD.md         │
│                    └─────────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Sources** fetch raw data from external APIs (HN Firebase, PH RSS, GitHub HTML)
2. **Normalization** converts source-specific formats into `IdeaItem` dataclasses
3. **Scoring** assigns a 0.0–1.0 score based on theme keywords, age, and popularity
4. **Storage** upserts items to Airtable, deduplicating by `source_name + id`
5. **Digest** reads scored items and generates a grouped Markdown summary

---

## Project Structure

```
proj/
├── main.py                  # CLI entry point
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── .github/workflows/       # GitHub Actions automation
│   └── daily-digest.yml     # Daily scheduled workflow
├── docs/
│   └── scheduling.md        # Detailed automation guide
├── digests/                 # Generated digest files (gitignored)
├── src/
│   ├── config/              # Environment and settings
│   │   └── config.py        # Loads .env, exposes typed variables
│   ├── models/
│   │   └── idea_item.py     # Core IdeaItem dataclass
│   ├── sources/             # Data fetchers
│   │   ├── base.py          # Abstract Source interface
│   │   ├── hackernews.py    # Hacker News (Firebase API)
│   │   ├── producthunt.py   # Product Hunt (RSS feed)
│   │   └── github_trending.py  # GitHub (HTML scraping)
│   ├── scoring/             # Relevance scoring
│   │   ├── themes.py        # Theme definitions and keywords
│   │   └── scorer.py        # Pure scoring functions
│   ├── storage/             # Persistence layer
│   │   ├── base.py          # Abstract Storage interface
│   │   └── airtable.py      # Airtable + mock implementations
│   ├── digest/              # Output generation
│   │   └── generator.py     # Markdown digest builder
│   └── pipeline.py          # Orchestrates the full flow
└── tests/                   # pytest test suite
```

### Why Each Module Exists

| Module | Responsibility | Design Rationale |
|--------|----------------|------------------|
| `config` | Load environment, expose settings | Centralized configuration avoids scattered `os.getenv()` calls |
| `models` | Define `IdeaItem` dataclass | Single data structure ensures consistency across all modules |
| `sources` | Fetch from external platforms | Abstract interface allows adding new sources without changing pipeline |
| `scoring` | Compute relevance scores | Pure functions (no side effects) make scoring testable and predictable |
| `storage` | Persist to Airtable | Abstract interface allows swapping backends (SQLite, Postgres, etc.) |
| `digest` | Generate Markdown output | Separation from storage allows different output formats |
| `pipeline` | Orchestrate execution | Single entry point for CLI, cron, and GitHub Actions |

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- An Airtable account (free tier works)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/idea-digest.git
cd idea-digest

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
# Required:
#   AIRTABLE_API_KEY=your_api_key
#   AIRTABLE_BASE_ID=your_base_id
```

### First Run

```bash
# Test with dry-run (no writes)
python main.py --dry-run --verbose --limit-per-source 3

# Full run (fetches, scores, stores, generates digest)
python main.py
```

Your first digest will appear at `digests/YYYY-MM-DD.md`.

---

## How It Works

Here's what happens when you run `python main.py`:

### Step 1: Configuration Loading

The pipeline starts by loading settings from `.env` via python-dotenv. Key settings include API keys, rate limits, and defaults.

```
.env → config.py → AIRTABLE_API_KEY, DEFAULT_LIMIT_PER_SOURCE, etc.
```

### Step 2: Source Instantiation

Three source classes are created:
- `HackerNewsSource` — reads from Firebase API
- `ProductHuntSource` — parses RSS feed
- `GitHubTrendingSource` — scrapes HTML page

Each implements the `Source` interface with a `fetch_items()` method.

### Step 3: Fetching

Each source fetches up to `--limit-per-source` items (default: 20). Fetching is sequential with polite delays (`SCRAPE_DELAY`) to avoid rate limits.

```
HN API → [item, item, ...] → normalize → [IdeaItem, IdeaItem, ...]
```

If a source fails (network error, rate limit), it returns an empty list and the pipeline continues with other sources.

### Step 4: Scoring

Each `IdeaItem` is passed through the scoring engine:

1. **Theme extraction**: Keywords in title/description are matched against `INTEREST_THEMES`
2. **Recency calculation**: Linear decay from 1.0 (today) to 0.0 (7+ days old)
3. **Popularity extraction**: HN points normalized (100 points = 0.5, 500+ = 1.0)

Final score: `0.4 × theme + 0.3 × recency + 0.3 × popularity`

### Step 5: Storage

Scored items are upserted to Airtable:
- **New items**: Inserted with all fields
- **Existing items**: Updated if score changed
- **Deduplication key**: `source_name + id` (e.g., `hackernews_12345`)

### Step 6: Digest Generation

Items from storage are:
1. Grouped by matched themes
2. Sorted by score (descending) within each group
3. Rendered to Markdown with summary statistics

Output: `digests/2025-12-24.md`

### Step 7: Summary

The pipeline prints a summary showing sources fetched, items processed, storage results, and digest location.

---

## Customization Guide

### Adding a New Source

1. **Create a new file** in `src/sources/`:

```python
# src/sources/reddit.py
from src.sources.base import Source
from src.models.idea_item import IdeaItem

class RedditSource(Source):
    @property
    def name(self) -> str:
        return "reddit"
    
    def fetch_items(self, limit: int | None = None) -> list[IdeaItem]:
        # Fetch from Reddit API
        # Return list of IdeaItem instances
        pass
```

2. **Register in `__init__.py`**:

```python
# src/sources/__init__.py
from .reddit import RedditSource
```

3. **Add to pipeline** in `src/pipeline.py`:

```python
sources = [
    HackerNewsSource(),
    ProductHuntSource(),
    GitHubTrendingSource(),
    RedditSource(),  # Add here
]
```

### Tuning Scoring Themes

Edit `src/scoring/themes.py`:

```python
INTEREST_THEMES = {
    "ai-ml": ["gpt", "llm", "machine learning", ...],
    
    # Add a new theme
    "security": [
        "vulnerability",
        "exploit",
        "cybersecurity",
        "penetration testing",
    ],
}

# Adjust theme importance
THEME_WEIGHTS = {
    "ai-ml": 1.2,        # Boost AI content
    "security": 1.1,     # Slightly boost security
    "default": 1.0,      # Everything else
}
```

### Changing Scoring Weights

Edit `src/scoring/scorer.py`:

```python
# Adjust component weights (should sum to ~1.0)
WEIGHT_THEMES = 0.5      # Increase theme importance
WEIGHT_RECENCY = 0.25    # Decrease recency importance
WEIGHT_POPULARITY = 0.25
```

### Using a Different Storage Backend

1. **Create a new storage class**:

```python
# src/storage/sqlite.py
from src.storage.base import Storage, UpsertResult

class SQLiteStorage(Storage):
    @property
    def name(self) -> str:
        return "sqlite"
    
    def upsert_items(self, items):
        # Implement SQLite upsert
        pass
    
    # ... implement other methods
```

2. **Use in pipeline**:

```python
# In src/pipeline.py or via dependency injection
storage = SQLiteStorage(db_path="ideas.db")
```

### Adjusting Digest Output

Edit `src/digest/generator.py`:

- Change `_theme_emoji()` to customize section emojis
- Modify `_format_item()` to change item layout
- Override `_generate_content()` for entirely different formats

---

## Operational Guide

### Manual Runs

```bash
# Full pipeline
python main.py

# Dry-run (no storage/digest writes)
python main.py --dry-run

# Specific sources only
python main.py --sources hackernews github

# Limit items (faster testing)
python main.py --limit-per-source 5

# Verbose output (see what's happening)
python main.py --verbose

# Show current configuration
python main.py --show-config
```

### Scheduled Runs (Cron)

Add to your crontab (`crontab -e`):

```cron
# Daily at 9 AM
0 9 * * * cd /path/to/idea-digest && python main.py >> /var/log/idea-digest.log 2>&1
```

**View logs:**
```bash
tail -f /var/log/idea-digest.log
```

### Scheduled Runs (GitHub Actions)

The workflow at `.github/workflows/daily-digest.yml` runs daily at 9 AM UTC.

**Required secrets** (Settings → Secrets → Actions):
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`

**Manual trigger:**
1. Go to Actions tab
2. Select "Daily Idea Digest"
3. Click "Run workflow"

**View logs:**
1. Click on a workflow run
2. Expand steps to see output

### Where to Look for Failures

| Environment | Logs Location |
|-------------|---------------|
| Manual run | Terminal output (`--verbose` for detail) |
| Local cron | `/var/log/idea-digest.log` or syslog |
| GitHub Actions | Actions tab → workflow run → step output |

**Common issues:**

| Error | Cause | Fix |
|-------|-------|-----|
| `AIRTABLE_API_KEY is not configured` | Missing env var | Add to `.env` or GitHub Secrets |
| `Network error` | API unavailable | Retry later, check rate limits |
| `No items fetched` | All sources failed | Check individual sources with `--sources` |

---

## Running Tests

```bash
# All tests
pytest tests/

# With verbose output
pytest tests/ -v

# Specific module
pytest tests/test_scoring.py -v

# With coverage
pytest tests/ --cov=src
```

---

## CLI Reference

```
usage: idea-digest [-h] [--dry-run] [--limit-per-source N]
                   [--since-days {daily,weekly,monthly}]
                   [--sources SOURCE [SOURCE ...]] [--digest-limit N]
                   [--digest-days N] [--skip-digest] [--verbose] [--quiet]
                   [--show-config] [--version]

Options:
  --dry-run, -n           Skip storage and digest writes
  --limit-per-source N    Max items per source (default: 20)
  --sources SOURCE...     Fetch from specific sources only
  --since-days            GitHub trending timeframe (daily/weekly/monthly)
  --digest-limit N        Max items in digest (default: 50)
  --digest-days N         Days to include in digest (default: 1)
  --skip-digest           Skip digest generation
  --verbose, -v           Detailed progress output
  --quiet, -q             Errors only
  --show-config           Display current configuration
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass: `pytest tests/`
5. Submit a pull request

---

## License

MIT License — see LICENSE file for details.
