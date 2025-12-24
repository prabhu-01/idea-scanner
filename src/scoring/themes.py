"""
Interest themes configuration for Idea Digest.

This file is the single source of truth for what topics the system cares about.
Themes are used for two purposes:
1. Tagging: Items are tagged with all matching themes (stored in IdeaItem.tags)
2. Scoring: Theme matches contribute to the interest score (weighted)

CUSTOMIZATION:

To add a new theme:
    1. Add a new key to INTEREST_THEMES with a descriptive lowercase name
    2. Add a list of keywords (lowercase) that indicate this theme
    3. Keywords are matched as substrings (e.g., "ml" matches "html" - be specific!)

To adjust scoring importance:
    1. Add the theme to THEME_WEIGHTS with a multiplier
    2. Higher weight = more contribution to final score
    3. Default weight is 1.0 if not specified
"""

# =============================================================================
# Interest Themes Configuration
# =============================================================================

# Mapping of theme name -> list of keywords (all lowercase)
# Keywords are matched case-insensitively against title and description
# Partial matches are allowed (e.g., "python" matches "pythonic")
INTEREST_THEMES: dict[str, list[str]] = {
    # AI and Machine Learning
    "ai-ml": [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "neural network",
        "gpt",
        "llm",
        "chatgpt",
        "openai",
        "anthropic",
        "claude",
        "transformer",
        "diffusion",
        "stable diffusion",
        "midjourney",
        "generative ai",
        "langchain",
        "vector database",
        "embeddings",
        "fine-tuning",
        "rag",
        "retrieval augmented",
    ],
    
    # Developer Tools and Infrastructure
    "developer-tools": [
        "developer tool",
        "dev tool",
        "ide",
        "code editor",
        "vscode",
        "vim",
        "neovim",
        "terminal",
        "cli",
        "command line",
        "git",
        "github",
        "gitlab",
        "devops",
        "ci/cd",
        "docker",
        "kubernetes",
        "terraform",
        "infrastructure",
        "api",
        "sdk",
        "framework",
        "library",
    ],
    
    # Programming Languages
    "programming": [
        "python",
        "javascript",
        "typescript",
        "rust",
        "golang",
        " go ",  # Space-padded to avoid matching "google"
        "swift",
        "kotlin",
        "java",
        "c++",
        "cpp",
        "haskell",
        "elixir",
        "ruby",
        "rails",
        "react",
        "vue",
        "svelte",
        "nextjs",
        "next.js",
        "compiler",
        "interpreter",
    ],
    
    # Startups and Business
    "startup": [
        "startup",
        "founder",
        "yc",
        "y combinator",
        "ycombinator",
        "venture",
        "funding",
        "seed round",
        "series a",
        "bootstrap",
        "saas",
        "b2b",
        "b2c",
        "product hunt",
        "launch",
        "mvp",
        "pivot",
        "growth",
        "acquisition",
    ],
    
    # Open Source
    "open-source": [
        "open source",
        "open-source",
        "opensource",
        "foss",
        "free software",
        "mit license",
        "apache license",
        "gpl",
        "contributor",
        "maintainer",
        "pull request",
        "issue tracker",
    ],
    
    # Security and Privacy
    "security": [
        "security",
        "cybersecurity",
        "encryption",
        "privacy",
        "vulnerability",
        "exploit",
        "hacking",
        "penetration",
        "zero-day",
        "authentication",
        "oauth",
        "jwt",
        "password",
        "2fa",
        "mfa",
        "firewall",
        "vpn",
    ],
    
    # Data and Analytics
    "data": [
        "database",
        "sql",
        "nosql",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "elasticsearch",
        "data engineering",
        "data science",
        "analytics",
        "visualization",
        "dashboard",
        "metrics",
        "etl",
        "data pipeline",
        "warehouse",
        "bigquery",
        "snowflake",
    ],
    
    # Web and Mobile
    "web-mobile": [
        "web app",
        "webapp",
        "mobile app",
        "ios app",
        "android app",
        "pwa",
        "responsive",
        "frontend",
        "backend",
        "full stack",
        "fullstack",
        "browser",
        "chrome",
        "firefox",
        "safari",
        "webassembly",
        "wasm",
    ],
    
    # Productivity and Tools
    "productivity": [
        "productivity",
        "automation",
        "workflow",
        "task management",
        "todo",
        "to-do",
        "notion",
        "obsidian",
        "note-taking",
        "calendar",
        "scheduling",
        "time tracking",
        "efficiency",
    ],
}


# =============================================================================
# Theme Weights (for scoring)
# =============================================================================

# Weight multiplier for each theme (default 1.0 if not specified)
# Higher weight = theme contributes more to final score
THEME_WEIGHTS: dict[str, float] = {
    "ai-ml": 1.5,           # AI/ML is hot right now, boost it
    "developer-tools": 1.3,  # Core interest area
    "programming": 1.0,      # Standard weight
    "startup": 1.2,          # Business relevance
    "open-source": 1.1,      # Community interest
    "security": 1.2,         # Important topic
    "data": 1.0,             # Standard weight
    "web-mobile": 0.9,       # Slightly lower (very broad)
    "productivity": 0.8,     # Lower priority
}


def get_theme_weight(theme: str) -> float:
    """
    Get the scoring weight for a theme.
    
    Args:
        theme: Theme name.
        
    Returns:
        Weight multiplier (default 1.0 if theme not in THEME_WEIGHTS).
    """
    return THEME_WEIGHTS.get(theme, 1.0)


def get_all_themes() -> list[str]:
    """
    Get list of all available theme names.
    
    Returns:
        List of theme names.
    """
    return list(INTEREST_THEMES.keys())

