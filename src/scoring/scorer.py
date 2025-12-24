"""
Scoring and tagging logic for Idea Digest.

Provides pure, side-effect-free functions to:
1. Extract matching themes from an IdeaItem (based on keywords)
2. Compute an interest score for an IdeaItem

All functions are deterministic and do not mutate input data.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import copy

from src.models.idea_item import IdeaItem
from src.scoring.themes import INTEREST_THEMES, get_theme_weight


# =============================================================================
# Scoring Configuration
# =============================================================================

# Maximum age in days for full recency bonus (items older get reduced bonus)
MAX_RECENCY_DAYS: int = 7

# Weight factors for scoring components (should sum to ~1.0 for interpretability)
# These can be tuned to adjust the importance of each factor
WEIGHT_THEMES: float = 0.4      # How much theme matches matter
WEIGHT_RECENCY: float = 0.3    # How much freshness matters
WEIGHT_POPULARITY: float = 0.3  # How much source popularity matters

# Default popularity score when source doesn't provide one
DEFAULT_POPULARITY: float = 0.3


# =============================================================================
# Result Data Structures
# =============================================================================

@dataclass
class ScoringResult:
    """
    Result of scoring an IdeaItem.
    
    Contains the computed score, matched themes, and component breakdowns
    for transparency and debugging.
    
    Attributes:
        score: Final interest score (0.0 to 1.0).
        themes: List of matched theme names.
        theme_score: Component score from theme matching (0.0 to 1.0).
        recency_score: Component score from recency (0.0 to 1.0).
        popularity_score: Component score from source popularity (0.0 to 1.0).
    """
    score: float
    themes: list[str]
    theme_score: float
    recency_score: float
    popularity_score: float


# =============================================================================
# Theme Extraction
# =============================================================================

def extract_themes(item: IdeaItem) -> list[str]:
    """
    Extract matching themes from an IdeaItem by analyzing its title and description.
    
    Matching rules:
    - Case-insensitive comparison
    - Partial matches allowed (keyword can appear anywhere in text)
    - A theme matches if ANY of its keywords are found
    - Returns deduplicated list of matching theme names
    
    This is a pure function - it does not modify the input item.
    
    Args:
        item: The IdeaItem to analyze.
        
    Returns:
        List of matched theme names (may be empty).
    
    Example:
        >>> item = IdeaItem(title="New Python ML Library", ...)
        >>> extract_themes(item)
        ['ai-ml', 'programming']
    """
    # Combine title and description for searching
    # Use empty string if description is None or missing
    text = f"{item.title} {item.description or ''}".lower()
    
    matched_themes = []
    
    for theme_name, keywords in INTEREST_THEMES.items():
        for keyword in keywords:
            if keyword.lower() in text:
                matched_themes.append(theme_name)
                break  # One match is enough for this theme
    
    return matched_themes


def extract_themes_with_keywords(item: IdeaItem) -> dict[str, list[str]]:
    """
    Extract matching themes with the specific keywords that matched.
    
    Useful for debugging and understanding why a theme was assigned.
    
    Args:
        item: The IdeaItem to analyze.
        
    Returns:
        Dict mapping theme name -> list of matched keywords.
    
    Example:
        >>> item = IdeaItem(title="Python and Machine Learning", ...)
        >>> extract_themes_with_keywords(item)
        {'ai-ml': ['machine learning'], 'programming': ['python']}
    """
    text = f"{item.title} {item.description or ''}".lower()
    
    matches: dict[str, list[str]] = {}
    
    for theme_name, keywords in INTEREST_THEMES.items():
        matched_keywords = []
        for keyword in keywords:
            if keyword.lower() in text:
                matched_keywords.append(keyword)
        
        if matched_keywords:
            matches[theme_name] = matched_keywords
    
    return matches


# =============================================================================
# Scoring Functions
# =============================================================================

def compute_theme_score(themes: list[str]) -> float:
    """
    Compute the theme component of the score.
    
    Formula:
    - Base: 0.2 per matched theme (capped at 1.0)
    - Multiplied by average theme weight
    
    Rationale:
    - More theme matches = broader appeal = higher score
    - Theme weights allow prioritizing certain topics
    - Cap at 1.0 to keep component normalized
    
    Args:
        themes: List of matched theme names.
        
    Returns:
        Theme score component (0.0 to 1.0).
    """
    if not themes:
        return 0.0
    
    # Base score: 0.2 per theme, max 1.0
    base_score = min(len(themes) * 0.2, 1.0)
    
    # Apply average weight of matched themes
    avg_weight = sum(get_theme_weight(t) for t in themes) / len(themes)
    
    # Final score capped at 1.0
    return min(base_score * avg_weight, 1.0)


def compute_recency_score(source_date: Optional[datetime], now: Optional[datetime] = None) -> float:
    """
    Compute the recency component of the score.
    
    Formula:
    - Items from today: 1.0
    - Items from MAX_RECENCY_DAYS ago: 0.0
    - Linear decay between these points
    - Items older than MAX_RECENCY_DAYS: 0.0
    - Items with no date: DEFAULT_POPULARITY (0.3)
    
    Rationale:
    - Fresh content is more interesting
    - Linear decay is simple and predictable
    - Don't penalize too harshly - even old interesting content has value
    
    Args:
        source_date: When the item was posted on the source.
        now: Current time (for testing). Defaults to datetime.now().
        
    Returns:
        Recency score component (0.0 to 1.0).
    """
    if source_date is None:
        return DEFAULT_POPULARITY  # Unknown age, use neutral default
    
    if now is None:
        now = datetime.now()
    
    # Calculate age in days
    age_delta = now - source_date
    age_days = age_delta.total_seconds() / (24 * 60 * 60)
    
    # Future dates (shouldn't happen) get full score
    if age_days < 0:
        return 1.0
    
    # Linear decay from 1.0 to 0.0 over MAX_RECENCY_DAYS
    if age_days >= MAX_RECENCY_DAYS:
        return 0.0
    
    return 1.0 - (age_days / MAX_RECENCY_DAYS)


def compute_popularity_score(item: IdeaItem) -> float:
    """
    Extract and normalize popularity signal from the item.
    
    We look at the description field which contains HN metadata like:
    "by username | 150 points | 42 comments"
    
    Formula:
    - Extract points if available
    - Normalize: 100 points = 0.5, 500+ points = 1.0
    - If no points found: DEFAULT_POPULARITY (0.3)
    
    Rationale:
    - Source popularity (upvotes/points) indicates community interest
    - Logarithmic-ish scaling (not linear) because:
      - 10 points vs 50 points is significant
      - 500 points vs 1000 points is less significant
    
    Args:
        item: The IdeaItem to analyze.
        
    Returns:
        Popularity score component (0.0 to 1.0).
    """
    description = item.description or ""
    
    # Try to extract points from description (e.g., "150 points")
    points = _extract_points_from_description(description)
    
    if points is None:
        return DEFAULT_POPULARITY
    
    # Normalize points to 0-1 range
    # 0 points = 0.0, 100 points = 0.5, 500+ points = 1.0
    if points <= 0:
        return 0.0
    elif points >= 500:
        return 1.0
    else:
        # Scale: 0-100 -> 0.0-0.5, 100-500 -> 0.5-1.0
        if points <= 100:
            return points / 200  # 100 points = 0.5
        else:
            return 0.5 + ((points - 100) / 800)  # 500 points = 1.0


def _extract_points_from_description(description: str) -> Optional[int]:
    """
    Extract point count from description string.
    
    Looks for patterns like "150 points" or "42 points".
    
    Args:
        description: Item description string.
        
    Returns:
        Point count if found, None otherwise.
    """
    import re
    
    match = re.search(r"(\d+)\s*points?", description, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def compute_interest_score(item: IdeaItem, now: Optional[datetime] = None) -> ScoringResult:
    """
    Compute the overall interest score for an IdeaItem.
    
    This is the main scoring function that combines all components.
    
    Formula:
        final_score = (WEIGHT_THEMES * theme_score) +
                      (WEIGHT_RECENCY * recency_score) +
                      (WEIGHT_POPULARITY * popularity_score)
    
    Where:
        - theme_score: Based on keyword matches (0.2 per theme, weighted)
        - recency_score: Based on age (linear decay over 7 days)
        - popularity_score: Based on source points (normalized)
    
    Default weights: themes=0.4, recency=0.3, popularity=0.3
    
    Rationale:
    - Theme match is most important (is this relevant to our interests?)
    - Recency and popularity are equal secondary factors
    - All components normalized to 0-1, final score also 0-1
    - Transparent breakdown allows tuning and debugging
    
    This is a pure function - it does not modify the input item.
    
    Args:
        item: The IdeaItem to score.
        now: Current time for recency calculation (for testing).
        
    Returns:
        ScoringResult with final score, themes, and component breakdown.
    
    Example:
        >>> result = compute_interest_score(item)
        >>> print(f"Score: {result.score:.2f}, Themes: {result.themes}")
    """
    # Extract themes
    themes = extract_themes(item)
    
    # Compute individual components
    theme_score = compute_theme_score(themes)
    recency_score = compute_recency_score(item.source_date, now)
    popularity_score = compute_popularity_score(item)
    
    # Combine with weights
    final_score = (
        WEIGHT_THEMES * theme_score +
        WEIGHT_RECENCY * recency_score +
        WEIGHT_POPULARITY * popularity_score
    )
    
    # Ensure final score is in valid range
    final_score = max(0.0, min(1.0, final_score))
    
    return ScoringResult(
        score=final_score,
        themes=themes,
        theme_score=theme_score,
        recency_score=recency_score,
        popularity_score=popularity_score,
    )


def score_item(item: IdeaItem, now: Optional[datetime] = None) -> IdeaItem:
    """
    Score an IdeaItem and return a new copy with updated score and tags.
    
    This is a convenience function that:
    1. Computes the interest score
    2. Creates a deep copy of the item
    3. Updates the copy's score and tags
    4. Returns the copy (original is unchanged)
    
    Use this when you want a scored IdeaItem directly.
    Use compute_interest_score() when you want the detailed breakdown.
    
    This is a pure function - it does not modify the input item.
    
    Args:
        item: The IdeaItem to score.
        now: Current time for recency calculation (for testing).
        
    Returns:
        New IdeaItem with updated score and tags.
    """
    result = compute_interest_score(item, now)
    
    # Create deep copy to avoid mutation
    scored_item = copy.deepcopy(item)
    
    # Update the copy (using internal assignment to avoid validation)
    scored_item.score = result.score
    scored_item.tags = result.themes.copy()
    scored_item.updated_at = datetime.now()
    
    return scored_item

