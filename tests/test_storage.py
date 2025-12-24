"""
Tests for storage abstraction and implementations.

Tests the Storage interface contract, Airtable serialization,
idempotent behavior, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.models.idea_item import IdeaItem
from src.storage.base import Storage, UpsertResult
from src.storage.airtable import (
    AirtableStorage,
    MockAirtableStorage,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_item():
    """A basic IdeaItem for testing."""
    return IdeaItem(
        id="hn_12345",
        title="Test Article",
        description="A test description",
        url="https://example.com/article",
        source_name="hackernews",
        source_date=datetime(2025, 12, 23, 10, 0, 0),
        score=0.75,
        tags=["ai-ml", "programming"],
    )


@pytest.fixture
def sample_item_minimal():
    """An IdeaItem with only required fields."""
    return IdeaItem(
        title="Minimal Item",
        url="https://example.com/minimal",
        source_name="test",
    )


@pytest.fixture
def sample_items():
    """Multiple IdeaItems for batch testing."""
    return [
        IdeaItem(
            id="hn_11111",
            title="First Article",
            url="https://example.com/1",
            source_name="hackernews",
            score=0.9,
        ),
        IdeaItem(
            id="hn_22222",
            title="Second Article",
            url="https://example.com/2",
            source_name="hackernews",
            score=0.5,
        ),
        IdeaItem(
            id="hn_33333",
            title="Third Article",
            url="https://example.com/3",
            source_name="hackernews",
            score=0.3,
        ),
    ]


@pytest.fixture
def mock_storage():
    """A MockAirtableStorage instance for testing."""
    return MockAirtableStorage()


@pytest.fixture
def airtable_storage():
    """An AirtableStorage instance with test credentials."""
    return AirtableStorage(
        api_key="test_api_key",
        base_id="test_base_id",
        table_name="test_table",
    )


# =============================================================================
# Test Storage Interface Contract
# =============================================================================

class TestStorageInterface:
    """Tests for the Storage abstract base class."""
    
    def test_storage_is_abstract(self):
        """Storage cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Storage()
    
    def test_storage_requires_name_property(self):
        """Concrete storage must implement name property."""
        class IncompleteStorage(Storage):
            def upsert_items(self, items):
                return UpsertResult()
            def get_recent_items(self, days=7):
                return []
            def get_top_items(self, limit=10, min_score=0.0):
                return []
        
        with pytest.raises(TypeError):
            IncompleteStorage()
    
    def test_storage_requires_upsert_items(self):
        """Concrete storage must implement upsert_items."""
        class IncompleteStorage(Storage):
            @property
            def name(self):
                return "incomplete"
            def get_recent_items(self, days=7):
                return []
            def get_top_items(self, limit=10, min_score=0.0):
                return []
        
        with pytest.raises(TypeError):
            IncompleteStorage()
    
    def test_complete_storage_can_be_instantiated(self):
        """A complete Storage implementation can be instantiated."""
        class CompleteStorage(Storage):
            @property
            def name(self):
                return "complete"
            def upsert_items(self, items):
                return UpsertResult()
            def get_recent_items(self, days=7):
                return []
            def get_top_items(self, limit=10, min_score=0.0):
                return []
        
        storage = CompleteStorage()
        assert storage.name == "complete"


class TestUpsertResult:
    """Tests for UpsertResult dataclass."""
    
    def test_default_values(self):
        """UpsertResult has sensible defaults."""
        result = UpsertResult()
        assert result.inserted == 0
        assert result.updated == 0
        assert result.failed == 0
        assert result.errors == []
    
    def test_total_processed(self):
        """total_processed returns sum of inserted and updated."""
        result = UpsertResult(inserted=5, updated=3, failed=2)
        assert result.total_processed == 8
    
    def test_str_representation(self):
        """UpsertResult has readable string representation."""
        result = UpsertResult(inserted=5, updated=3, failed=2)
        assert "inserted=5" in str(result)
        assert "updated=3" in str(result)
        assert "failed=2" in str(result)


# =============================================================================
# Test MockAirtableStorage
# =============================================================================

class TestMockAirtableStorage:
    """Tests for MockAirtableStorage implementation."""
    
    def test_name_property(self, mock_storage):
        """MockAirtableStorage has correct name."""
        assert mock_storage.name == "mock"
    
    def test_is_storage_subclass(self, mock_storage):
        """MockAirtableStorage is a proper Storage subclass."""
        assert isinstance(mock_storage, Storage)
    
    def test_upsert_new_items(self, mock_storage, sample_items):
        """New items are inserted."""
        result = mock_storage.upsert_items(sample_items)
        
        assert result.inserted == 3
        assert result.updated == 0
        assert result.failed == 0
        assert mock_storage.count() == 3
    
    def test_upsert_duplicate_items(self, mock_storage, sample_item):
        """Duplicate items are updated, not duplicated."""
        # Insert first time
        result1 = mock_storage.upsert_items([sample_item])
        assert result1.inserted == 1
        assert result1.updated == 0
        
        # Insert same item again
        result2 = mock_storage.upsert_items([sample_item])
        assert result2.inserted == 0
        assert result2.updated == 1
        
        # Should still only have 1 record
        assert mock_storage.count() == 1
    
    def test_get_recent_items(self, mock_storage, sample_items):
        """get_recent_items returns items within date range."""
        mock_storage.upsert_items(sample_items)
        
        recent = mock_storage.get_recent_items(days=7)
        assert len(recent) == 3
    
    def test_get_top_items(self, mock_storage, sample_items):
        """get_top_items returns items sorted by score."""
        mock_storage.upsert_items(sample_items)
        
        top = mock_storage.get_top_items(limit=2)
        assert len(top) == 2
        assert top[0].score >= top[1].score
        assert top[0].score == 0.9  # Highest score
    
    def test_get_top_items_min_score(self, mock_storage, sample_items):
        """get_top_items respects min_score filter."""
        mock_storage.upsert_items(sample_items)
        
        top = mock_storage.get_top_items(limit=10, min_score=0.6)
        assert len(top) == 1  # Only one item with score >= 0.6
        assert top[0].score == 0.9
    
    def test_get_item_by_key(self, mock_storage, sample_item):
        """get_item_by_key returns correct item."""
        mock_storage.upsert_items([sample_item])
        
        item = mock_storage.get_item_by_key("hn_12345")
        assert item is not None
        assert item.title == "Test Article"
    
    def test_get_item_by_key_not_found(self, mock_storage):
        """get_item_by_key returns None for unknown key."""
        item = mock_storage.get_item_by_key("nonexistent")
        assert item is None
    
    def test_clear(self, mock_storage, sample_items):
        """clear removes all records."""
        mock_storage.upsert_items(sample_items)
        assert mock_storage.count() == 3
        
        mock_storage.clear()
        assert mock_storage.count() == 0


# =============================================================================
# Test Airtable Serialization
# =============================================================================

class TestAirtableSerialization:
    """Tests for IdeaItem <-> Airtable conversion."""
    
    def test_item_to_airtable_fields_complete(self, sample_item):
        """Complete IdeaItem converts to all Airtable fields."""
        fields = AirtableStorage.item_to_airtable_fields(sample_item)
        
        assert fields["unique_key"] == "hn_12345"
        assert fields["item_id"] == "hn_12345"
        assert fields["title"] == "Test Article"
        assert fields["description"] == "A test description"
        assert fields["url"] == "https://example.com/article"
        assert fields["source_name"] == "hackernews"
        assert fields["score"] == 0.75
        assert fields["tags"] == ["ai-ml", "programming"]
        assert "source_date" in fields
        assert "created_at" in fields
        assert "updated_at" in fields
    
    def test_item_to_airtable_fields_minimal(self, sample_item_minimal):
        """Minimal IdeaItem converts without optional fields."""
        fields = AirtableStorage.item_to_airtable_fields(sample_item_minimal)
        
        assert "unique_key" in fields
        assert "title" in fields
        assert "url" in fields
        assert "source_name" in fields
        assert "description" not in fields  # Empty string not included
        assert "source_date" not in fields  # None not included
    
    def test_item_to_airtable_fields_empty_tags(self):
        """Empty tags list is not included in fields."""
        item = IdeaItem(
            title="No Tags",
            url="https://example.com",
            source_name="test",
            tags=[],
        )
        fields = AirtableStorage.item_to_airtable_fields(item)
        assert "tags" not in fields
    
    def test_airtable_record_to_item_complete(self):
        """Complete Airtable record converts to IdeaItem."""
        record = {
            "id": "rec123",
            "fields": {
                "unique_key": "hn_99999",
                "item_id": "hn_99999",
                "title": "From Airtable",
                "description": "A description",
                "url": "https://example.com",
                "source_name": "hackernews",
                "source_date": "2025-12-23T10:00:00",
                "score": 0.85,
                "tags": ["developer-tools"],
                "created_at": "2025-12-23T12:00:00",
                "updated_at": "2025-12-23T12:00:00",
            }
        }
        
        item = AirtableStorage.airtable_record_to_item(record)
        
        assert item is not None
        assert item.id == "hn_99999"
        assert item.title == "From Airtable"
        assert item.description == "A description"
        assert item.url == "https://example.com"
        assert item.source_name == "hackernews"
        assert item.score == 0.85
        assert item.tags == ["developer-tools"]
        assert item.source_date is not None
    
    def test_airtable_record_to_item_minimal(self):
        """Minimal Airtable record converts to IdeaItem."""
        record = {
            "id": "rec456",
            "fields": {
                "title": "Minimal",
                "url": "https://example.com",
                "source_name": "test",
            }
        }
        
        item = AirtableStorage.airtable_record_to_item(record)
        
        assert item is not None
        assert item.title == "Minimal"
        assert item.description == ""
        assert item.score == 0.0
        assert item.tags == []
    
    def test_airtable_record_to_item_missing_required(self):
        """Record missing required fields returns None."""
        record = {
            "id": "rec789",
            "fields": {
                "title": "Missing URL",
                # "url" is missing
                "source_name": "test",
            }
        }
        
        item = AirtableStorage.airtable_record_to_item(record)
        assert item is None
    
    def test_airtable_record_to_item_invalid_date(self):
        """Invalid date doesn't crash, just returns None for that field."""
        record = {
            "id": "rec111",
            "fields": {
                "title": "Bad Date",
                "url": "https://example.com",
                "source_name": "test",
                "source_date": "not-a-date",
            }
        }
        
        item = AirtableStorage.airtable_record_to_item(record)
        assert item is not None
        assert item.source_date is None


# =============================================================================
# Test Airtable Idempotent Upserts (Mocked)
# =============================================================================

class TestAirtableIdempotentUpserts:
    """Tests for idempotent upsert behavior with mocked API."""
    
    def test_upsert_new_item_creates_record(self, airtable_storage, sample_item):
        """New item creates a new Airtable record."""
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_create_record') as mock_create:
            
            mock_find.return_value = None  # Item doesn't exist
            mock_create.return_value = (True, "")
            
            result = airtable_storage.upsert_items([sample_item])
            
            assert result.inserted == 1
            assert result.updated == 0
            mock_create.assert_called_once()
    
    def test_upsert_existing_item_updates_record(self, airtable_storage, sample_item):
        """Existing item updates the Airtable record."""
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_update_record') as mock_update:
            
            mock_find.return_value = ("rec123", {"title": "Old Title"})
            mock_update.return_value = (True, "")
            
            result = airtable_storage.upsert_items([sample_item])
            
            assert result.inserted == 0
            assert result.updated == 1
            mock_update.assert_called_once_with("rec123", sample_item)
    
    def test_upsert_handles_create_failure(self, airtable_storage, sample_item):
        """Failed create is counted in failed."""
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_create_record') as mock_create:
            
            mock_find.return_value = None
            mock_create.return_value = (False, "Network error")
            
            result = airtable_storage.upsert_items([sample_item])
            
            assert result.inserted == 0
            assert result.failed == 1
            assert len(result.errors) == 1
            assert "Network error" in result.errors[0]
    
    def test_upsert_handles_update_failure(self, airtable_storage, sample_item):
        """Failed update is counted in failed."""
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_update_record') as mock_update:
            
            mock_find.return_value = ("rec123", {})
            mock_update.return_value = (False, "API error")
            
            result = airtable_storage.upsert_items([sample_item])
            
            assert result.updated == 0
            assert result.failed == 1
            assert len(result.errors) == 1
    
    def test_upsert_multiple_items_mixed_results(self, airtable_storage, sample_items):
        """Multiple items can have mixed insert/update/fail results."""
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_create_record') as mock_create, \
             patch.object(airtable_storage, '_update_record') as mock_update:
            
            # First item: new (insert)
            # Second item: exists (update)
            # Third item: new but fails
            mock_find.side_effect = [
                None,
                ("rec222", {}),
                None,
            ]
            mock_create.side_effect = [
                (True, ""),
                (False, "Rate limited"),
            ]
            mock_update.return_value = (True, "")
            
            result = airtable_storage.upsert_items(sample_items)
            
            assert result.inserted == 1
            assert result.updated == 1
            assert result.failed == 1
    
    def test_upsert_idempotent_behavior(self, airtable_storage, sample_item):
        """Running upsert twice with same item should update second time."""
        call_count = 0
        
        def mock_find_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # First call: not found
            return ("rec123", {})  # Second call: found
        
        with patch.object(airtable_storage, '_find_by_unique_key') as mock_find, \
             patch.object(airtable_storage, '_create_record') as mock_create, \
             patch.object(airtable_storage, '_update_record') as mock_update:
            
            mock_find.side_effect = mock_find_side_effect
            mock_create.return_value = (True, "")
            mock_update.return_value = (True, "")
            
            # First upsert
            result1 = airtable_storage.upsert_items([sample_item])
            assert result1.inserted == 1
            
            # Second upsert
            result2 = airtable_storage.upsert_items([sample_item])
            assert result2.updated == 1


# =============================================================================
# Test Airtable API Calls (Mocked)
# =============================================================================

class TestAirtableAPICalls:
    """Tests for Airtable API request/response handling."""
    
    def test_find_by_unique_key_found(self, airtable_storage):
        """_find_by_unique_key returns record when found."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "records": [
                {"id": "rec123", "fields": {"title": "Test"}}
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch("src.storage.airtable.requests.get") as mock_get:
            mock_get.return_value = mock_response
            
            result = airtable_storage._find_by_unique_key("hn_12345")
            
            assert result is not None
            assert result[0] == "rec123"
    
    def test_find_by_unique_key_not_found(self, airtable_storage):
        """_find_by_unique_key returns None when not found."""
        mock_response = Mock()
        mock_response.json.return_value = {"records": []}
        mock_response.raise_for_status = Mock()
        
        with patch("src.storage.airtable.requests.get") as mock_get:
            mock_get.return_value = mock_response
            
            result = airtable_storage._find_by_unique_key("nonexistent")
            
            assert result is None
    
    def test_find_by_unique_key_network_error(self, airtable_storage):
        """_find_by_unique_key returns None on network error."""
        with patch("src.storage.airtable.requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = airtable_storage._find_by_unique_key("hn_12345")
            
            assert result is None
    
    def test_create_record_success(self, airtable_storage, sample_item):
        """_create_record returns success on 200."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "rec123"}
        mock_response.raise_for_status = Mock()
        
        with patch("src.storage.airtable.requests.post") as mock_post:
            mock_post.return_value = mock_response
            
            success, error = airtable_storage._create_record(sample_item)
            
            assert success is True
            assert error == ""
    
    def test_create_record_failure(self, airtable_storage, sample_item):
        """_create_record returns failure on error."""
        with patch("src.storage.airtable.requests.post") as mock_post:
            mock_post.side_effect = Exception("API error")
            
            success, error = airtable_storage._create_record(sample_item)
            
            assert success is False
            assert "API error" in error
    
    def test_update_record_success(self, airtable_storage, sample_item):
        """_update_record returns success on 200."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "rec123"}
        mock_response.raise_for_status = Mock()
        
        with patch("src.storage.airtable.requests.patch") as mock_patch:
            mock_patch.return_value = mock_response
            
            success, error = airtable_storage._update_record("rec123", sample_item)
            
            assert success is True
            assert error == ""
    
    def test_list_records_with_filter(self, airtable_storage):
        """_list_records passes filter formula to API."""
        mock_response = Mock()
        mock_response.json.return_value = {"records": []}
        mock_response.raise_for_status = Mock()
        
        with patch("src.storage.airtable.requests.get") as mock_get:
            mock_get.return_value = mock_response
            
            airtable_storage._list_records(filter_formula="{score} >= 0.5")
            
            # Verify filter was passed
            call_args = mock_get.call_args
            params = call_args.kwargs.get("params", {})
            assert "filterByFormula" in params


# =============================================================================
# Test Missing Fields and Edge Cases
# =============================================================================

class TestMissingFieldsHandling:
    """Tests for handling missing or null fields."""
    
    def test_upsert_item_with_none_description(self, mock_storage):
        """Item with None description can be stored."""
        item = IdeaItem(
            title="No Description",
            url="https://example.com",
            source_name="test",
        )
        item.description = None
        
        result = mock_storage.upsert_items([item])
        assert result.inserted == 1
    
    def test_upsert_item_with_none_source_date(self, mock_storage):
        """Item with None source_date can be stored."""
        item = IdeaItem(
            title="No Date",
            url="https://example.com",
            source_name="test",
        )
        
        result = mock_storage.upsert_items([item])
        assert result.inserted == 1
    
    def test_serialization_with_empty_string_description(self):
        """Empty string description is not included in Airtable fields."""
        item = IdeaItem(
            title="Empty Description",
            description="",
            url="https://example.com",
            source_name="test",
        )
        
        fields = AirtableStorage.item_to_airtable_fields(item)
        assert "description" not in fields
    
    def test_serialization_preserves_score_zero(self):
        """Score of 0.0 is preserved in serialization."""
        item = IdeaItem(
            title="Zero Score",
            url="https://example.com",
            source_name="test",
            score=0.0,
        )
        
        fields = AirtableStorage.item_to_airtable_fields(item)
        assert fields["score"] == 0.0


# =============================================================================
# Test Configuration Validation
# =============================================================================

class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_missing_api_key_raises(self):
        """Missing API key raises ValueError."""
        storage = AirtableStorage(
            api_key="",
            base_id="test_base",
            table_name="test_table",
        )
        
        with pytest.raises(ValueError) as exc_info:
            storage._validate_config()
        
        assert "AIRTABLE_API_KEY" in str(exc_info.value)
    
    def test_missing_base_id_raises(self):
        """Missing base ID raises ValueError."""
        storage = AirtableStorage(
            api_key="test_key",
            base_id="",
            table_name="test_table",
        )
        
        with pytest.raises(ValueError) as exc_info:
            storage._validate_config()
        
        assert "AIRTABLE_BASE_ID" in str(exc_info.value)
    
    def test_missing_table_name_raises(self):
        """Missing table name raises ValueError."""
        storage = AirtableStorage(
            api_key="test_key",
            base_id="test_base",
            table_name="",
        )
        
        with pytest.raises(ValueError) as exc_info:
            storage._validate_config()
        
        assert "AIRTABLE_TABLE_NAME" in str(exc_info.value)
    
    def test_valid_config_passes(self):
        """Valid configuration passes validation."""
        storage = AirtableStorage(
            api_key="test_key",
            base_id="test_base",
            table_name="test_table",
        )
        
        # Should not raise
        storage._validate_config()

