"""
Data sources module.

Fetchers for external platforms: Product Hunt, Hacker News, GitHub Trending.
"""

from src.sources.base import Source
from src.sources.hackernews import HackerNewsSource
from src.sources.producthunt import ProductHuntSource
from src.sources.github_trending import GitHubTrendingSource

__all__ = [
    "Source",
    "HackerNewsSource",
    "ProductHuntSource",
    "GitHubTrendingSource",
]


