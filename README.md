# Idea Digest

<div align="center">

**An intelligent idea discovery platform that aggregates, analyzes, and surfaces the best ideas from across the web.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Airtable](https://img.shields.io/badge/storage-Airtable-yellow.svg)](https://airtable.com)
[![Groq AI](https://img.shields.io/badge/AI-Groq-purple.svg)](https://groq.com)

</div>

---

## 🎯 Overview

Idea Digest solves the problem of **information overload**. Instead of manually checking Product Hunt, Hacker News, and GitHub every day, it automatically:

- **Fetches** trending ideas from multiple platforms
- **Scores** items by relevance, recency, and engagement
- **Stores** everything in Airtable with deduplication
- **Generates** daily Markdown digests
- **Provides** a modern web dashboard with AI-powered analysis

### Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **Multi-Source Aggregation** | Product Hunt, Hacker News, GitHub Trending |
| 🤖 **AI-Powered Analysis** | Deep insights using Groq's LLaMA 3.3 (free) |
| 👤 **Maker Information** | Creator profiles, bios, and social links |
| 📊 **Smart Scoring** | Theme matching, recency decay, popularity signals |
| 🌐 **Modern Web Dashboard** | Beautiful UI with real-time filtering |
| 📝 **Daily Digests** | Auto-generated Markdown summaries |
| ☁️ **Airtable Storage** | Free tier friendly with auto-cleanup |

---

## 🖥️ Screenshots

### Dashboard
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  📊 29 ideas  │  ● 10 HN  ● 10 PH  ● 9 GH          Last sync: 2h ago  48/1200  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ ═══ HN ════  │  │ ═══ PH ════  │  │ ═══ GH ════  │  │ ═══ GH ════  │       │
│  │              │  │              │  │              │  │              │       │
│  │ Title...     │  │ Title...     │  │ Title...     │  │ Title...     │       │
│  │ Description  │  │ Description  │  │ Description  │  │ Description  │       │
│  │              │  │              │  │              │  │              │       │
│  │ ▲284  💬52   │  │ ▲847  💬23   │  │ ⭐12.4k +89  │  │ ⭐3.2k  +156 │       │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### AI Analysis Modal
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                              [✕]                │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  PRODUCT HUNT                                                              │ │
│  │  AI Tool for Developers                                                    │ │
│  │  ▲ 847 Upvotes   💬 23 Comments                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  [Avatar]  John Doe · Founder & CEO                            [🔗] [𝕏]   │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  🤖 AI ANALYSIS                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  This tool revolutionizes developer workflows by...                       │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐                             │
│  │ Problem Solved      │  │ Target Audience     │                             │
│  │ Automates tedious..│  │ Developers who...   │                             │
│  └─────────────────────┘  └─────────────────────┘                             │
│                                                                                 │
│  [← Back to Dashboard]                              [View Original →]          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           IDEA DIGEST ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   DATA SOURCES                           WEB LAYER                              │
│   ════════════                           ═════════                              │
│   ┌─────────────┐                        ┌─────────────────────────────────┐   │
│   │ Product Hunt│ ──┐                    │         Flask Dashboard         │   │
│   │ (GraphQL)   │   │                    │  ┌─────────────────────────┐    │   │
│   └─────────────┘   │                    │  │     Stats Bar           │    │   │
│   ┌─────────────┐   │   ┌──────────┐     │  ├─────────────────────────┤    │   │
│   │ Hacker News │ ──┼──▶│ Pipeline │     │  │     Ideas Grid          │    │   │
│   │ (Firebase)  │   │   └────┬─────┘     │  ├─────────────────────────┤    │   │
│   └─────────────┘   │        │           │  │   AI Analysis Modal     │    │   │
│   ┌─────────────┐   │        ▼           │  └─────────────────────────┘    │   │
│   │   GitHub    │ ──┘   ┌──────────┐     └──────────────┬──────────────────┘   │
│   │ (Scraping)  │       │ Scoring  │                    │                      │
│   └─────────────┘       └────┬─────┘                    │                      │
│                              │                          ▼                      │
│                              ▼                    ┌───────────┐                │
│                        ┌──────────┐               │  Groq AI  │                │
│                        │ Airtable │◀──────────────│  (LLaMA)  │                │
│                        │ Storage  │               └───────────┘                │
│                        └────┬─────┘                                            │
│                             │                                                  │
│                             ▼                                                  │
│                       ┌──────────┐                                             │
│                       │ Markdown │                                             │
│                       │ Digests  │                                             │
│                       └──────────┘                                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Sources** → Fetch from external APIs (HN Firebase, PH GraphQL, GitHub HTML)
2. **Normalization** → Convert to unified `IdeaItem` model with maker info
3. **Scoring** → Calculate relevance (theme × recency × popularity)
4. **Storage** → Upsert to Airtable with deduplication
5. **Dashboard** → Display with filters, metrics, AI analysis
6. **Digest** → Generate daily Markdown summary

---

## 📁 Project Structure

```
idea-digest/
├── main.py                      # CLI entry point
├── requirements.txt             # Python dependencies
├── .env                         # Environment configuration (gitignored)
├── README.md                    # This file
│
├── src/
│   ├── config/
│   │   └── config.py            # Environment loading, typed settings
│   │
│   ├── models/
│   │   └── idea_item.py         # IdeaItem dataclass with maker fields
│   │
│   ├── sources/                 # Data fetchers
│   │   ├── base.py              # Abstract Source interface
│   │   ├── hackernews.py        # HN Firebase API
│   │   ├── producthunt.py       # PH GraphQL API
│   │   └── github_trending.py   # GitHub HTML scraping
│   │
│   ├── scoring/
│   │   ├── themes.py            # Interest themes and keywords
│   │   └── scorer.py            # Scoring algorithms
│   │
│   ├── storage/
│   │   └── airtable.py          # Airtable CRUD + free tier management
│   │
│   ├── services/
│   │   └── ai_summarizer.py     # Groq AI integration
│   │
│   ├── digest/
│   │   └── generator.py         # Markdown digest builder
│   │
│   └── pipeline.py              # Orchestrates full pipeline
│
├── web/
│   ├── app.py                   # Flask application
│   └── templates/
│       ├── base.html            # Base template with styles
│       ├── index.html           # Dashboard page
│       ├── digests.html         # Digests list
│       └── digest.html          # Single digest view
│
├── digests/                     # Generated digest files
│   └── YYYY-MM-DD.md
│
└── tests/                       # Test suite
    └── ...
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Airtable account** (free tier works)
- **Groq API key** (free at [console.groq.com](https://console.groq.com)) — optional, for AI features

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/idea-digest.git
cd idea-digest

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```bash
# =============================================================================
# REQUIRED
# =============================================================================

# Airtable (get from https://airtable.com/create/tokens)
AIRTABLE_API_KEY=pat_xxxxxxxxxxxxx
AIRTABLE_BASE_ID=appxxxxxxxxxxxxx
AIRTABLE_TABLE_NAME=Ideas

# =============================================================================
# OPTIONAL - API Keys for Enhanced Features
# =============================================================================

# Product Hunt (https://www.producthunt.com/v2/oauth/applications)
PRODUCT_HUNT_TOKEN=your_token_here

# GitHub (https://github.com/settings/tokens) - for higher rate limits
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx

# Groq AI (https://console.groq.com) - for AI analysis
GROQ_API_KEY=gsk_xxxxxxxxxxxxx

# =============================================================================
# OPTIONAL - Pipeline Settings
# =============================================================================

DEFAULT_LIMIT_PER_SOURCE=10
REQUEST_TIMEOUT=30
SCRAPE_DELAY=2.0

# Airtable free tier management
AIRTABLE_MAX_RECORDS=1000
AIRTABLE_RETENTION_DAYS=30
AIRTABLE_AUTO_CLEANUP=true
```

### First Run

```bash
# Test with dry-run (no writes)
python3 main.py --dry-run --verbose --limit 3

# Full pipeline run
python3 main.py --verbose

# Check results
ls digests/
```

### Start the Dashboard

```bash
# Run the web server
python3 -m web.app

# Open in browser
open http://localhost:5001
```

---

## 📊 IdeaItem Data Model

Each idea is stored as an `IdeaItem` with the following fields:

```python
@dataclass
class IdeaItem:
    # Core fields
    id: str                    # Unique ID (e.g., "hn_12345")
    title: str                 # Idea title
    description: str           # Description/tagline
    url: str                   # Link to original
    source_name: str           # "hackernews" | "producthunt" | "github"
    source_date: datetime      # When posted on source
    score: float               # Relevance score (0.0-1.0)
    tags: list[str]            # Matched themes
    
    # Platform metrics
    points: int                # HN: upvotes
    votes: int                 # PH: upvotes
    comments_count: int        # HN/PH: comments
    stars: int                 # GitHub: total stars
    stars_today: int           # GitHub: stars gained today
    language: str              # GitHub: programming language
    
    # Maker information
    maker_name: str            # Creator's name
    maker_username: str        # Platform username
    maker_url: str             # Profile URL
    maker_avatar: str          # Avatar image URL
    maker_bio: str             # Short bio/headline
    maker_twitter: str         # Twitter handle
```

---

## 🤖 AI Integration

Idea Digest uses **Groq** (free tier) for AI-powered analysis:

### Features

| Feature | Description |
|---------|-------------|
| **Deep Analysis** | Summary, problem solved, target audience, unique value |
| **Impact Assessment** | Low/Medium/High potential impact rating |
| **Tag Suggestions** | AI-generated topic tags |
| **Maker Insights** | Analysis of creator background (when available) |
| **Page Insights** | Trends analysis across all visible ideas |

### API Endpoints

```
POST /api/ai/analyze     # Deep analysis of single idea
POST /api/ai/insights    # Trends from multiple ideas
POST /api/ai/summarize   # Quick summary
GET  /api/ai/status      # Check if AI is configured
```

### Example Response

```json
{
  "success": true,
  "analysis": {
    "summary": "This tool revolutionizes...",
    "problem_solved": "Eliminates manual...",
    "target_audience": "Developers who...",
    "unique_value": "First solution to...",
    "potential_impact": "High - addresses a $10B market",
    "tags": ["developer-tools", "automation", "ai-ml"],
    "maker_insight": "Founded by ex-Google engineer..."
  }
}
```

---

## 🔄 Source Integrations

### Hacker News

- **API**: Firebase Hacker News API (public, no auth)
- **Data**: Top/Best stories with points, comments, author
- **Rate Limit**: ~500 requests/day recommended

### Product Hunt

- **API**: GraphQL API (requires token)
- **Data**: Daily launches with votes, comments, makers
- **Rate Limit**: 450 requests/day (free tier)

### GitHub Trending

- **Method**: HTML scraping (no API key needed)
- **Data**: Trending repos with stars, language, description
- **Rate Limit**: Respectful scraping with delays

---

## 🛠️ CLI Reference

```bash
# Basic usage
python3 main.py [OPTIONS]

# Options
--limit N              # Items per source (default: 10)
--sources SRC [SRC...] # Specific sources only
--dry-run              # Skip storage writes
--verbose              # Detailed output
--quiet                # Errors only

# Digest options
--skip-digest          # Skip digest generation
--digest-limit N       # Max items in digest
--digest-days N        # Days to include

# Storage management
--storage-stats        # Show record count
--cleanup              # Manual cleanup
--cleanup-days N       # Retention for cleanup

# Info
--show-config          # Display configuration
--version              # Show version
--help                 # Show help
```

### Examples

```bash
# Fetch 15 items from each source
python3 main.py --limit 15 --verbose

# Only fetch from GitHub
python3 main.py --sources github

# Check storage status
python3 main.py --storage-stats

# Clear old records
python3 main.py --cleanup --cleanup-days 7
```

---

## 🌐 Web Dashboard

### Routes

| Route | Description |
|-------|-------------|
| `/` | Main dashboard with idea grid |
| `/digests` | List of generated digests |
| `/digest/<date>` | View specific digest |
| `/api/stats` | Storage statistics |
| `/api/ai/*` | AI analysis endpoints |

### Filtering

The dashboard supports filtering by:
- **Source**: All, Hacker News, Product Hunt, GitHub
- **Tag**: AI/ML, Developer Tools, etc.
- **Sort**: Score, Date, Source
- **Time**: Today, 3 days, 7 days, 2 weeks, month

---

## 📈 Scoring Algorithm

Items are scored using a weighted formula:

```
score = 0.4 × theme_score + 0.3 × recency_score + 0.3 × popularity_score
```

| Component | Calculation |
|-----------|-------------|
| **Theme** | Keyword matching against interest themes (0-1) |
| **Recency** | Linear decay: 1.0 (today) → 0.0 (7+ days) |
| **Popularity** | Normalized engagement (points/votes/stars) |

### Interest Themes

```python
INTEREST_THEMES = {
    "ai-ml": ["gpt", "llm", "machine learning", "neural", ...],
    "developer-tools": ["api", "sdk", "cli", "devtools", ...],
    "startup": ["saas", "b2b", "founder", "mvp", ...],
    "open-source": ["github", "open source", "oss", ...],
    # ... more themes
}
```

---

## 🗄️ Airtable Setup

### Required Columns

The following columns are auto-created if using the API:

| Column | Type | Description |
|--------|------|-------------|
| `unique_key` | Text | Deduplication key |
| `title` | Text | Idea title |
| `description` | Long text | Description |
| `url` | URL | Link to source |
| `source_name` | Single select | Platform name |
| `score` | Number | Relevance score |
| `tags` | Multiple select | Matched themes |
| `points` | Number | HN points |
| `votes` | Number | PH votes |
| `stars` | Number | GitHub stars |
| `maker_name` | Text | Creator name |
| `maker_avatar` | URL | Avatar URL |
| ... | ... | ... |

### Free Tier Management

Airtable's free tier allows 1,200 records. Idea Digest auto-manages this:

- **Auto-cleanup**: Deletes records older than `AIRTABLE_RETENTION_DAYS`
- **Threshold**: Triggers when approaching `AIRTABLE_MAX_RECORDS`
- **Manual**: `python3 main.py --cleanup --cleanup-days 7`

---

## 🔧 Customization

### Adding a New Source

1. Create `src/sources/your_source.py`:

```python
from src.sources.base import Source
from src.models.idea_item import IdeaItem

class YourSource(Source):
    @property
    def name(self) -> str:
        return "yoursource"
    
    def fetch_items(self, limit: int = 10) -> list[IdeaItem]:
        # Fetch and return IdeaItems
        pass
```

2. Register in `src/sources/__init__.py`
3. Add to pipeline in `src/pipeline.py`

### Modifying Scoring

Edit `src/scoring/themes.py` to add themes:

```python
INTEREST_THEMES["your-theme"] = [
    "keyword1",
    "keyword2",
    ...
]
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_scoring.py -v
```

---

## 📅 Automation

### GitHub Actions

The included workflow (`.github/workflows/daily-digest.yml`) runs daily at 9 AM UTC.

**Required Secrets**:
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `GROQ_API_KEY` (optional)

### Cron

```bash
# Add to crontab
0 9 * * * cd /path/to/idea-digest && python3 main.py >> logs/digest.log 2>&1
```

---

## 🐛 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `AIRTABLE_API_KEY not configured` | Missing env var | Add to `.env` |
| `422 Unprocessable Entity` | Missing Airtable columns | Run pipeline once to auto-create |
| `Rate limit exceeded` | Too many API calls | Reduce `--limit` or add delays |
| `AI not configured` | Missing `GROQ_API_KEY` | Add key or AI features disabled |
| `No items fetched` | Source failures | Check with `--sources X --verbose` |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Hacker News API](https://github.com/HackerNews/API)
- [Product Hunt API](https://api.producthunt.com/v2/docs)
- [Groq](https://groq.com) for free AI inference
- [Airtable](https://airtable.com) for database hosting

---

<div align="center">

**Built with ❤️ for idea enthusiasts**

[Report Bug](https://github.com/yourusername/idea-digest/issues) · [Request Feature](https://github.com/yourusername/idea-digest/issues)

</div>
