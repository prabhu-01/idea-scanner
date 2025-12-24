"""
Scoring module.

Tags and scores ideas based on relevance, recency, and engagement.
"""

from src.scoring.themes import (
    INTEREST_THEMES,
    THEME_WEIGHTS,
    get_theme_weight,
    get_all_themes,
)

from src.scoring.scorer import (
    extract_themes,
    extract_themes_with_keywords,
    compute_theme_score,
    compute_recency_score,
    compute_popularity_score,
    compute_interest_score,
    score_item,
    ScoringResult,
)

__all__ = [
    # Theme configuration
    "INTEREST_THEMES",
    "THEME_WEIGHTS",
    "get_theme_weight",
    "get_all_themes",
    # Scoring functions
    "extract_themes",
    "extract_themes_with_keywords",
    "compute_theme_score",
    "compute_recency_score",
    "compute_popularity_score",
    "compute_interest_score",
    "score_item",
    "ScoringResult",
]


