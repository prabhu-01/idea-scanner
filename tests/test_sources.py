"""
Tests for source abstraction and implementations.

Tests the Source interface contract, HackerNews parsing,
IdeaItem field mapping, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.sources.base import Source
from src.sources.hackernews import (
    HackerNewsSource,
    HN_TOP_STORIES_URL,
    HN_ITEM_URL,
    HN_ITEM_WEB_URL,
)
from src.models.idea_item import IdeaItem


# =============================================================================
# Test Source Interface Contract
# =============================================================================

class TestSourceInterface:
    """Tests for the Source abstract base class contract."""
    
    def test_source_is_abstract(self):
        """Source cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Source()
    
    def test_source_requires_name_property(self):
        """Concrete sources must implement name property."""
        # Create a class that only implements fetch_items
        class IncompleteSource(Source):
            def fetch_items(self, limit=None):
                return []
        
        with pytest.raises(TypeError):
            IncompleteSource()
    
    def test_source_requires_fetch_items_method(self):
        """Concrete sources must implement fetch_items method."""
        # Create a class that only implements name
        class IncompleteSource(Source):
            @property
            def name(self):
                return "incomplete"
        
        with pytest.raises(TypeError):
            IncompleteSource()
    
    def test_complete_source_can_be_instantiated(self):
        """A complete Source implementation can be instantiated."""
        class CompleteSource(Source):
            @property
            def name(self):
                return "complete"
            
            def fetch_items(self, limit=None):
                return []
        
        source = CompleteSource()
        assert source.name == "complete"
        assert source.fetch_items() == []
    
    def test_source_str_representation(self):
        """Source has useful string representation."""
        class TestSource(Source):
            @property
            def name(self):
                return "testsource"
            
            def fetch_items(self, limit=None):
                return []
        
        source = TestSource()
        assert "testsource" in str(source)


# =============================================================================
# Test HackerNewsSource
# =============================================================================

class TestHackerNewsSource:
    """Tests for HackerNewsSource implementation."""
    
    def test_name_property(self):
        """HackerNewsSource has correct name."""
        source = HackerNewsSource()
        assert source.name == "hackernews"
    
    def test_is_source_subclass(self):
        """HackerNewsSource is a proper Source subclass."""
        source = HackerNewsSource()
        assert isinstance(source, Source)


# =============================================================================
# Test HackerNews Response Parsing (Mocked)
# =============================================================================

class TestHackerNewsResponseParsing:
    """Tests for HN API response parsing with mocked network calls."""
    
    @pytest.fixture
    def source(self):
        """Create a HackerNewsSource instance."""
        return HackerNewsSource()
    
    @pytest.fixture
    def sample_story_ids(self):
        """Sample top story IDs response."""
        return [101, 102, 103, 104, 105]
    
    @pytest.fixture
    def sample_item_data(self):
        """Sample HN item data."""
        return {
            "id": 101,
            "type": "story",
            "title": "Show HN: A Cool New Project",
            "url": "https://example.com/project",
            "by": "testuser",
            "time": 1703318400,  # 2023-12-23 12:00:00 UTC
            "score": 150,
            "descendants": 42,
        }
    
    def test_fetch_items_success(self, source, sample_story_ids, sample_item_data):
        """Test successful fetch with mocked API responses."""
        with patch("src.sources.hackernews.requests.get") as mock_get:
            # Set up mock responses
            mock_response_ids = Mock()
            mock_response_ids.json.return_value = sample_story_ids
            mock_response_ids.raise_for_status = Mock()
            
            mock_response_item = Mock()
            mock_response_item.json.return_value = sample_item_data
            mock_response_item.raise_for_status = Mock()
            
            # First call returns IDs, subsequent calls return item data
            mock_get.side_effect = [mock_response_ids] + [mock_response_item] * 5
            
            items = source.fetch_items(limit=5)
            
            assert len(items) == 5
            assert all(isinstance(item, IdeaItem) for item in items)
    
    def test_fetch_items_respects_limit(self, source, sample_story_ids, sample_item_data):
        """Test that fetch_items respects the limit parameter."""
        with patch("src.sources.hackernews.requests.get") as mock_get:
            mock_response_ids = Mock()
            mock_response_ids.json.return_value = sample_story_ids
            mock_response_ids.raise_for_status = Mock()
            
            mock_response_item = Mock()
            mock_response_item.json.return_value = sample_item_data
            mock_response_item.raise_for_status = Mock()
            
            mock_get.side_effect = [mock_response_ids] + [mock_response_item] * 2
            
            items = source.fetch_items(limit=2)
            
            assert len(items) == 2
    
    def test_fetch_returns_empty_on_network_error(self, source):
        """Test graceful handling of network errors."""
        with patch("src.sources.hackernews.requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            items = source.fetch_items(limit=5)
            
            assert items == []
    
    def test_fetch_returns_empty_on_invalid_json(self, source):
        """Test graceful handling of invalid JSON response."""
        with patch("src.sources.hackernews.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            items = source.fetch_items(limit=5)
            
            assert items == []


# =============================================================================
# Test IdeaItem Field Mapping
# =============================================================================

class TestHackerNewsFieldMapping:
    """Tests for correct mapping of HN fields to IdeaItem fields."""
    
    @pytest.fixture
    def source(self):
        return HackerNewsSource()
    
    def test_basic_field_mapping(self, source):
        """Test that all fields are mapped correctly."""
        raw_item = {
            "id": 12345,
            "title": "Test Article Title",
            "url": "https://example.com/article",
            "by": "author123",
            "time": 1703318400,
            "score": 200,
            "descendants": 50,
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is not None
        assert item.id == "hn_12345"
        assert item.title == "Test Article Title"
        assert item.url == "https://example.com/article"
        assert item.source_name == "hackernews"
        assert item.source_date is not None
        assert "author123" in item.description
        assert "200 points" in item.description
        assert "50 comments" in item.description
    
    def test_url_fallback_to_hn_discussion(self, source):
        """Test that items without URL fall back to HN discussion page."""
        raw_item = {
            "id": 99999,
            "title": "Ask HN: What's your favorite tool?",
            "by": "curious_dev",
            "time": 1703318400,
            # No "url" field - this is an Ask HN post
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is not None
        assert item.url == HN_ITEM_WEB_URL.format(item_id=99999)
        assert "news.ycombinator.com" in item.url
    
    def test_timestamp_parsing(self, source):
        """Test that Unix timestamp is correctly converted to datetime."""
        raw_item = {
            "id": 11111,
            "title": "Timestamp Test",
            "url": "https://example.com",
            "time": 1703318400,  # 2023-12-23 12:00:00 UTC
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is not None
        assert item.source_date is not None
        assert isinstance(item.source_date, datetime)
    
    def test_description_with_all_fields(self, source):
        """Test description includes all available metadata."""
        raw_item = {
            "id": 22222,
            "title": "Full Item",
            "url": "https://example.com",
            "by": "poster",
            "score": 100,
            "descendants": 25,
        }
        
        item = source._normalize_item(raw_item)
        
        assert "by poster" in item.description
        assert "100 points" in item.description
        assert "25 comments" in item.description
    
    def test_description_with_missing_fields(self, source):
        """Test description handles missing optional fields."""
        raw_item = {
            "id": 33333,
            "title": "Minimal Item",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is not None
        assert item.description == ""
    
    def test_title_whitespace_stripped(self, source):
        """Test that title whitespace is stripped."""
        raw_item = {
            "id": 44444,
            "title": "  Padded Title  ",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item.title == "Padded Title"
    
    def test_initial_score_is_zero(self, source):
        """Test that IdeaItem score starts at 0.0 (scoring comes later)."""
        raw_item = {
            "id": 55555,
            "title": "Score Test",
            "url": "https://example.com",
            "score": 500,  # HN score, not our score
        }
        
        item = source._normalize_item(raw_item)
        
        # Our IdeaItem score should be 0.0, not the HN score
        assert item.score == 0.0
    
    def test_initial_tags_empty(self, source):
        """Test that IdeaItem tags start empty (tagging comes later)."""
        raw_item = {
            "id": 66666,
            "title": "Tags Test",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item.tags == []


# =============================================================================
# Test Malformed/Incomplete Item Handling
# =============================================================================

class TestHackerNewsMalformedItems:
    """Tests for graceful handling of malformed or incomplete items."""
    
    @pytest.fixture
    def source(self):
        return HackerNewsSource()
    
    def test_missing_id_returns_none(self, source):
        """Items without id are skipped."""
        raw_item = {
            "title": "No ID Item",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is None
    
    def test_missing_title_returns_none(self, source):
        """Items without title are skipped."""
        raw_item = {
            "id": 77777,
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is None
    
    def test_empty_title_returns_none(self, source):
        """Items with empty title are skipped."""
        raw_item = {
            "id": 88888,
            "title": "",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is None
    
    def test_whitespace_only_title_returns_none(self, source):
        """Items with whitespace-only title are skipped."""
        raw_item = {
            "id": 88889,
            "title": "   ",
            "url": "https://example.com",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is None
    
    def test_none_input_returns_none(self, source):
        """None input is handled gracefully."""
        item = source._normalize_item(None)
        
        assert item is None
    
    def test_empty_dict_returns_none(self, source):
        """Empty dict is handled gracefully."""
        item = source._normalize_item({})
        
        assert item is None
    
    def test_non_dict_input_returns_none(self, source):
        """Non-dict input is handled gracefully."""
        assert source._normalize_item("not a dict") is None
        assert source._normalize_item([1, 2, 3]) is None
        assert source._normalize_item(12345) is None
    
    def test_invalid_timestamp_handled(self, source):
        """Invalid timestamp doesn't crash, just results in None source_date."""
        raw_item = {
            "id": 99998,
            "title": "Bad Timestamp",
            "url": "https://example.com",
            "time": "not a timestamp",
        }
        
        item = source._normalize_item(raw_item)
        
        assert item is not None
        assert item.source_date is None
    
    def test_mixed_valid_invalid_items_in_batch(self, source):
        """When fetching, valid items are kept and invalid ones skipped."""
        valid_item = {
            "id": 11111,
            "title": "Valid Item",
            "url": "https://example.com",
        }
        invalid_item_no_title = {
            "id": 22222,
            "url": "https://example.com",
        }
        invalid_item_no_id = {
            "title": "No ID",
            "url": "https://example.com",
        }
        
        with patch("src.sources.hackernews.requests.get") as mock_get:
            mock_response_ids = Mock()
            mock_response_ids.json.return_value = [11111, 22222, 33333]
            mock_response_ids.raise_for_status = Mock()
            
            def item_response(item_data):
                mock = Mock()
                mock.json.return_value = item_data
                mock.raise_for_status = Mock()
                return mock
            
            mock_get.side_effect = [
                mock_response_ids,
                item_response(valid_item),
                item_response(invalid_item_no_title),
                item_response(invalid_item_no_id),
            ]
            
            items = source.fetch_items(limit=3)
            
            # Only the valid item should be in the result
            assert len(items) == 1
            assert items[0].title == "Valid Item"

