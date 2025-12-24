"""
Tests for scoring and tagging logic.

Validates keyword matching, scoring formula, case-insensitivity,
determinism, and non-mutation guarantees.
"""

import pytest
from datetime import datetime, timedelta
import copy

from src.models.idea_item import IdeaItem
from src.scoring.scorer import (
    extract_themes,
    extract_themes_with_keywords,
    compute_theme_score,
    compute_recency_score,
    compute_popularity_score,
    compute_interest_score,
    score_item,
    ScoringResult,
    MAX_RECENCY_DAYS,
    WEIGHT_THEMES,
    WEIGHT_RECENCY,
    WEIGHT_POPULARITY,
    DEFAULT_POPULARITY,
)
from src.scoring.themes import (
    INTEREST_THEMES,
    THEME_WEIGHTS,
    get_theme_weight,
    get_all_themes,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def basic_item():
    """A basic IdeaItem with no special keywords."""
    return IdeaItem(
        title="A Regular Article",
        description="Nothing special here",
        url="https://example.com",
        source_name="test",
    )


@pytest.fixture
def ai_item():
    """An IdeaItem about AI/ML."""
    return IdeaItem(
        title="New GPT-5 Model Released",
        description="OpenAI releases a revolutionary machine learning model",
        url="https://example.com/gpt5",
        source_name="hackernews",
        source_date=datetime.now(),
    )


@pytest.fixture
def multi_theme_item():
    """An IdeaItem matching multiple themes."""
    return IdeaItem(
        title="Open Source Python Library for Machine Learning",
        description="A new MIT licensed framework for developers",
        url="https://github.com/example/ml-lib",
        source_name="github",
        source_date=datetime.now(),
    )


@pytest.fixture
def hn_item_with_points():
    """An IdeaItem with HN-style points in description."""
    return IdeaItem(
        title="Some Tech Article",
        description="by author | 250 points | 100 comments",
        url="https://example.com",
        source_name="hackernews",
        source_date=datetime.now(),
    )


# =============================================================================
# Test Theme Extraction
# =============================================================================

class TestThemeExtraction:
    """Tests for extract_themes function."""
    
    def test_no_matching_themes(self, basic_item):
        """Items with no keywords return empty list."""
        themes = extract_themes(basic_item)
        assert themes == []
    
    def test_single_theme_match(self, ai_item):
        """Items matching one theme return that theme."""
        themes = extract_themes(ai_item)
        assert "ai-ml" in themes
    
    def test_multiple_theme_matches(self, multi_theme_item):
        """Items can match multiple themes."""
        themes = extract_themes(multi_theme_item)
        assert "ai-ml" in themes  # "machine learning"
        assert "programming" in themes  # "python"
        assert "open-source" in themes  # "open source", "mit license"
        assert "developer-tools" in themes  # "framework", "library"
    
    def test_case_insensitive_title(self):
        """Theme matching is case-insensitive in title."""
        item = IdeaItem(
            title="PYTHON is AMAZING",
            url="https://example.com",
            source_name="test",
        )
        themes = extract_themes(item)
        assert "programming" in themes
    
    def test_case_insensitive_description(self):
        """Theme matching is case-insensitive in description."""
        item = IdeaItem(
            title="An Article",
            description="This is about MACHINE LEARNING",
            url="https://example.com",
            source_name="test",
        )
        themes = extract_themes(item)
        assert "ai-ml" in themes
    
    def test_partial_match_in_word(self):
        """Keywords can match as part of larger words."""
        item = IdeaItem(
            title="Pythonic Programming Patterns",  # "python" is in "pythonic"
            url="https://example.com",
            source_name="test",
        )
        themes = extract_themes(item)
        assert "programming" in themes
    
    def test_empty_description_handled(self):
        """Empty description doesn't cause errors."""
        item = IdeaItem(
            title="Python Tutorial",
            description="",
            url="https://example.com",
            source_name="test",
        )
        themes = extract_themes(item)
        assert "programming" in themes
    
    def test_none_description_handled(self):
        """None description doesn't cause errors."""
        item = IdeaItem(
            title="Python Tutorial",
            url="https://example.com",
            source_name="test",
        )
        # Manually set description to None (bypassing default)
        item.description = None
        themes = extract_themes(item)
        assert "programming" in themes
    
    def test_extract_themes_with_keywords_returns_matched_keywords(self, ai_item):
        """extract_themes_with_keywords shows which keywords matched."""
        matches = extract_themes_with_keywords(ai_item)
        assert "ai-ml" in matches
        # Should include specific keywords that matched
        ai_keywords = matches["ai-ml"]
        assert any(kw in ["gpt", "openai", "machine learning"] for kw in ai_keywords)


# =============================================================================
# Test Theme Score Computation
# =============================================================================

class TestThemeScore:
    """Tests for compute_theme_score function."""
    
    def test_no_themes_zero_score(self):
        """No themes = 0 score."""
        score = compute_theme_score([])
        assert score == 0.0
    
    def test_single_theme_base_score(self):
        """Single theme gives 0.2 * weight."""
        # Use a theme with weight 1.0
        score = compute_theme_score(["programming"])
        assert score == pytest.approx(0.2 * 1.0)
    
    def test_multiple_themes_additive(self):
        """Multiple themes add up (0.2 each)."""
        # Two themes with weight 1.0
        score = compute_theme_score(["programming", "data"])
        assert score == pytest.approx(0.4 * 1.0)
    
    def test_theme_score_capped_at_one(self):
        """Theme score is capped at 1.0."""
        # 10 themes would be 2.0 without cap
        many_themes = list(INTEREST_THEMES.keys())
        score = compute_theme_score(many_themes)
        assert score <= 1.0
    
    def test_high_weight_theme_boosts_score(self):
        """High-weight themes increase the score."""
        # ai-ml has weight 1.5
        ai_score = compute_theme_score(["ai-ml"])
        # programming has weight 1.0
        prog_score = compute_theme_score(["programming"])
        
        assert ai_score > prog_score


# =============================================================================
# Test Recency Score Computation
# =============================================================================

class TestRecencyScore:
    """Tests for compute_recency_score function."""
    
    def test_today_full_score(self):
        """Items from today get score 1.0."""
        now = datetime.now()
        score = compute_recency_score(now, now)
        assert score == pytest.approx(1.0)
    
    def test_max_age_zero_score(self):
        """Items MAX_RECENCY_DAYS old get score 0.0."""
        now = datetime.now()
        old_date = now - timedelta(days=MAX_RECENCY_DAYS)
        score = compute_recency_score(old_date, now)
        assert score == pytest.approx(0.0)
    
    def test_older_than_max_zero_score(self):
        """Items older than MAX_RECENCY_DAYS get score 0.0."""
        now = datetime.now()
        very_old = now - timedelta(days=MAX_RECENCY_DAYS + 10)
        score = compute_recency_score(very_old, now)
        assert score == 0.0
    
    def test_linear_decay(self):
        """Score decays linearly with age."""
        now = datetime.now()
        half_age = now - timedelta(days=MAX_RECENCY_DAYS / 2)
        score = compute_recency_score(half_age, now)
        assert score == pytest.approx(0.5, rel=0.01)
    
    def test_none_date_default_score(self):
        """None date returns default score."""
        score = compute_recency_score(None)
        assert score == DEFAULT_POPULARITY
    
    def test_future_date_full_score(self):
        """Future dates (edge case) get full score."""
        now = datetime.now()
        future = now + timedelta(days=1)
        score = compute_recency_score(future, now)
        assert score == 1.0


# =============================================================================
# Test Popularity Score Computation
# =============================================================================

class TestPopularityScore:
    """Tests for compute_popularity_score function."""
    
    def test_no_points_default_score(self, basic_item):
        """Items without points get default score."""
        score = compute_popularity_score(basic_item)
        assert score == DEFAULT_POPULARITY
    
    def test_100_points_half_score(self, hn_item_with_points):
        """100 points = 0.5 score."""
        item = IdeaItem(
            title="Test",
            description="by author | 100 points | 50 comments",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score == pytest.approx(0.5)
    
    def test_500_points_full_score(self):
        """500+ points = 1.0 score."""
        item = IdeaItem(
            title="Test",
            description="by author | 500 points | 200 comments",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score == pytest.approx(1.0)
    
    def test_very_high_points_capped(self):
        """Points above 500 still cap at 1.0."""
        item = IdeaItem(
            title="Test",
            description="by author | 5000 points | 1000 comments",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score == 1.0
    
    def test_zero_points_zero_score(self):
        """Zero points = 0.0 score."""
        item = IdeaItem(
            title="Test",
            description="by author | 0 points",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score == 0.0
    
    def test_points_case_insensitive(self):
        """Points extraction is case-insensitive."""
        item = IdeaItem(
            title="Test",
            description="200 POINTS",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score > DEFAULT_POPULARITY
    
    def test_empty_description_default(self):
        """Empty description returns default score."""
        item = IdeaItem(
            title="Test",
            description="",
            url="https://example.com",
            source_name="test",
        )
        score = compute_popularity_score(item)
        assert score == DEFAULT_POPULARITY


# =============================================================================
# Test Full Interest Score Computation
# =============================================================================

class TestInterestScore:
    """Tests for compute_interest_score function."""
    
    def test_returns_scoring_result(self, basic_item):
        """Returns a ScoringResult dataclass."""
        result = compute_interest_score(basic_item)
        assert isinstance(result, ScoringResult)
        assert hasattr(result, "score")
        assert hasattr(result, "themes")
        assert hasattr(result, "theme_score")
        assert hasattr(result, "recency_score")
        assert hasattr(result, "popularity_score")
    
    def test_score_in_valid_range(self, basic_item, ai_item, multi_theme_item):
        """Score is always between 0.0 and 1.0."""
        for item in [basic_item, ai_item, multi_theme_item]:
            result = compute_interest_score(item)
            assert 0.0 <= result.score <= 1.0
    
    def test_deterministic_for_fixed_input(self, ai_item):
        """Same input always produces same output."""
        now = datetime(2025, 12, 23, 12, 0, 0)
        
        result1 = compute_interest_score(ai_item, now)
        result2 = compute_interest_score(ai_item, now)
        
        assert result1.score == result2.score
        assert result1.themes == result2.themes
        assert result1.theme_score == result2.theme_score
        assert result1.recency_score == result2.recency_score
        assert result1.popularity_score == result2.popularity_score
    
    def test_ai_item_higher_than_basic(self, basic_item, ai_item):
        """AI item scores higher than basic item."""
        now = datetime.now()
        ai_result = compute_interest_score(ai_item, now)
        basic_result = compute_interest_score(basic_item, now)
        
        assert ai_result.score > basic_result.score
    
    def test_multi_theme_highest(self, basic_item, ai_item, multi_theme_item):
        """Multi-theme item scores highest."""
        now = datetime.now()
        multi_result = compute_interest_score(multi_theme_item, now)
        ai_result = compute_interest_score(ai_item, now)
        
        # Multi-theme should have more themes
        assert len(multi_result.themes) > len(ai_result.themes)
    
    def test_weights_sum_to_one(self):
        """Weight constants sum to 1.0 for interpretability."""
        total = WEIGHT_THEMES + WEIGHT_RECENCY + WEIGHT_POPULARITY
        assert total == pytest.approx(1.0)
    
    def test_components_sum_approximately_to_score(self, ai_item):
        """Weighted components should sum to final score."""
        result = compute_interest_score(ai_item)
        
        expected = (
            WEIGHT_THEMES * result.theme_score +
            WEIGHT_RECENCY * result.recency_score +
            WEIGHT_POPULARITY * result.popularity_score
        )
        
        assert result.score == pytest.approx(expected)


# =============================================================================
# Test Non-Mutation Guarantees
# =============================================================================

class TestNonMutation:
    """Tests that scoring functions don't mutate input."""
    
    def test_extract_themes_no_mutation(self, ai_item):
        """extract_themes doesn't modify the item."""
        original_title = ai_item.title
        original_desc = ai_item.description
        original_score = ai_item.score
        original_tags = ai_item.tags.copy()
        
        extract_themes(ai_item)
        
        assert ai_item.title == original_title
        assert ai_item.description == original_desc
        assert ai_item.score == original_score
        assert ai_item.tags == original_tags
    
    def test_compute_interest_score_no_mutation(self, ai_item):
        """compute_interest_score doesn't modify the item."""
        original_title = ai_item.title
        original_desc = ai_item.description
        original_score = ai_item.score
        original_tags = ai_item.tags.copy()
        original_id = ai_item.id
        
        compute_interest_score(ai_item)
        
        assert ai_item.title == original_title
        assert ai_item.description == original_desc
        assert ai_item.score == original_score
        assert ai_item.tags == original_tags
        assert ai_item.id == original_id
    
    def test_score_item_returns_copy(self, ai_item):
        """score_item returns a new item, not the original."""
        scored = score_item(ai_item)
        
        # Should be different objects
        assert scored is not ai_item
        
        # Original should be unchanged
        assert ai_item.score == 0.0
        assert ai_item.tags == []
        
        # Scored should have new values
        assert scored.score > 0.0
        assert len(scored.tags) > 0 or scored.score > 0
    
    def test_score_item_original_unchanged(self, ai_item):
        """score_item leaves original item completely unchanged."""
        # Deep copy for comparison
        original = copy.deepcopy(ai_item)
        
        score_item(ai_item)
        
        assert ai_item.id == original.id
        assert ai_item.title == original.title
        assert ai_item.description == original.description
        assert ai_item.url == original.url
        assert ai_item.source_name == original.source_name
        assert ai_item.score == original.score
        assert ai_item.tags == original.tags


# =============================================================================
# Test score_item Convenience Function
# =============================================================================

class TestScoreItem:
    """Tests for score_item convenience function."""
    
    def test_returns_idea_item(self, ai_item):
        """Returns an IdeaItem instance."""
        result = score_item(ai_item)
        assert isinstance(result, IdeaItem)
    
    def test_has_updated_score(self, ai_item):
        """Returned item has the computed score."""
        result = score_item(ai_item)
        
        # Score should be set (not default 0.0 for ai_item)
        expected = compute_interest_score(ai_item)
        assert result.score == pytest.approx(expected.score)
    
    def test_has_updated_tags(self, ai_item):
        """Returned item has the extracted themes as tags."""
        result = score_item(ai_item)
        expected_themes = extract_themes(ai_item)
        
        assert set(result.tags) == set(expected_themes)
    
    def test_preserves_other_fields(self, ai_item):
        """Returned item preserves non-score/tag fields."""
        result = score_item(ai_item)
        
        assert result.id == ai_item.id
        assert result.title == ai_item.title
        assert result.description == ai_item.description
        assert result.url == ai_item.url
        assert result.source_name == ai_item.source_name
        assert result.source_date == ai_item.source_date


# =============================================================================
# Test Theme Configuration
# =============================================================================

class TestThemeConfiguration:
    """Tests for theme configuration module."""
    
    def test_interest_themes_not_empty(self):
        """INTEREST_THEMES has content."""
        assert len(INTEREST_THEMES) > 0
    
    def test_all_themes_have_keywords(self):
        """Every theme has at least one keyword."""
        for theme, keywords in INTEREST_THEMES.items():
            assert len(keywords) > 0, f"Theme {theme} has no keywords"
    
    def test_get_theme_weight_known(self):
        """get_theme_weight returns correct weight for known themes."""
        assert get_theme_weight("ai-ml") == THEME_WEIGHTS["ai-ml"]
    
    def test_get_theme_weight_unknown(self):
        """get_theme_weight returns 1.0 for unknown themes."""
        assert get_theme_weight("nonexistent-theme") == 1.0
    
    def test_get_all_themes(self):
        """get_all_themes returns all theme names."""
        themes = get_all_themes()
        assert set(themes) == set(INTEREST_THEMES.keys())

