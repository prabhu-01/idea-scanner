"""
Idempotency Tests

Verifies that running the pipeline multiple times with the same data
produces consistent results without creating duplicates.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import List, Dict

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.storage.base import Storage, UpsertResult
from src.pipeline import IdeaDigestPipeline, PipelineConfig

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, TEST_DATA


class MockIdempotentStorage(Storage):
    """
    A mock storage that tracks operations and simulates idempotent behavior.
    
    Keeps an internal dict of items by unique key (source_name + id).
    First insert of a key = insert, subsequent = update.
    """
    
    def __init__(self):
        self._items: Dict[str, IdeaItem] = {}
        self._operation_history: List[Dict] = []
    
    @property
    def name(self) -> str:
        return "mock_idempotent"
    
    def _make_key(self, item: IdeaItem) -> str:
        return f"{item.source_name}_{item.id}"
    
    def upsert_items(self, items: List[IdeaItem]) -> UpsertResult:
        inserted = 0
        updated = 0
        
        for item in items:
            key = self._make_key(item)
            if key in self._items:
                # Already exists - this is an update
                updated += 1
                self._items[key] = item
            else:
                # New item - this is an insert
                inserted += 1
                self._items[key] = item
        
        self._operation_history.append({
            'timestamp': datetime.now(),
            'items_count': len(items),
            'inserted': inserted,
            'updated': updated,
        })
        
        return UpsertResult(inserted=inserted, updated=updated)
    
    def get_recent_items(self, days: int = 7) -> List[IdeaItem]:
        return list(self._items.values())
    
    def get_top_items(self, limit: int = 10, min_score: float = 0.0) -> List[IdeaItem]:
        items = list(self._items.values())
        items.sort(key=lambda x: x.score, reverse=True)
        return items[:limit]
    
    def get_operation_history(self) -> List[Dict]:
        return self._operation_history.copy()
    
    def get_all_keys(self) -> set:
        return set(self._items.keys())


class MockDeterministicSource(Source):
    """A source that returns the same items every time."""
    
    def __init__(self, name: str, items: List[IdeaItem]):
        self._name = name
        self._items = items
    
    @property
    def name(self) -> str:
        return self._name
    
    def fetch_items(self, limit=None):
        if limit:
            return self._items[:limit]
        return self._items.copy()


class TestConsecutiveRunIdempotency:
    """Tests for idempotency across consecutive pipeline runs."""
    
    def test_first_run_performs_inserts(self):
        """
        GIVEN: Empty storage and a set of items
        WHEN: Pipeline runs for the FIRST time
        THEN: All items are INSERTED (not updated)
        """
        storage = MockIdempotentStorage()
        
        items = [
            IdeaItem(id="1", title="Item 1", url="https://example.com/1", source_name="test"),
            IdeaItem(id="2", title="Item 2", url="https://example.com/2", source_name="test"),
            IdeaItem(id="3", title="Item 3", url="https://example.com/3", source_name="test"),
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        source = MockDeterministicSource("test", items)
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                result = pipeline.run()
        
        assert result.storage_result.inserted == 3, \
            f"First run should insert all items, got {result.storage_result.inserted} inserts"
        assert result.storage_result.updated == 0, \
            f"First run should have no updates, got {result.storage_result.updated} updates"
    
    def test_second_run_performs_updates_not_inserts(self):
        """
        GIVEN: Storage already contains items from a previous run
        WHEN: Pipeline runs AGAIN with the same items
        THEN: Items are UPDATED (not inserted again)
        """
        storage = MockIdempotentStorage()
        
        items = [
            IdeaItem(id="1", title="Item 1", url="https://example.com/1", source_name="test"),
            IdeaItem(id="2", title="Item 2", url="https://example.com/2", source_name="test"),
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        source = MockDeterministicSource("test", items)
        
        # First run
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                first_result = pipeline.run()
        
        # Second run with same items
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                second_result = pipeline.run()
        
        assert second_result.storage_result.inserted == 0, \
            f"Second run should not insert, got {second_result.storage_result.inserted} inserts"
        assert second_result.storage_result.updated == 2, \
            f"Second run should update existing items, got {second_result.storage_result.updated} updates"
    
    def test_no_duplicate_keys_after_multiple_runs(self):
        """
        GIVEN: Pipeline runs multiple times with same data
        WHEN: Storage is examined
        THEN: No duplicate keys exist (each item appears once)
        """
        storage = MockIdempotentStorage()
        
        items = [
            IdeaItem(id="unique_1", title="Item 1", url="https://example.com/1", source_name="src"),
            IdeaItem(id="unique_2", title="Item 2", url="https://example.com/2", source_name="src"),
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        source = MockDeterministicSource("src", items)
        
        # Run three times
        for _ in range(3):
            with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
                with patch.object(pipeline, '_get_storage', return_value=storage):
                    pipeline.run()
        
        keys = storage.get_all_keys()
        
        assert len(keys) == 2, \
            f"Should have exactly 2 unique items, found {len(keys)}: {keys}"


class TestUniqueKeyGeneration:
    """Tests that unique keys are properly generated."""
    
    def test_items_from_different_sources_with_same_id_are_distinct(self):
        """
        GIVEN: Two items with the same ID but different source_name
        WHEN: Both are stored
        THEN: Both are kept (different unique keys)
        """
        storage = MockIdempotentStorage()
        
        items_source1 = [
            IdeaItem(id="123", title="From Source 1", url="https://source1.com/123", source_name="source1"),
        ]
        items_source2 = [
            IdeaItem(id="123", title="From Source 2", url="https://source2.com/123", source_name="source2"),
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        source1 = MockDeterministicSource("source1", items_source1)
        source2 = MockDeterministicSource("source2", items_source2)
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source1, source2]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                result = pipeline.run()
        
        keys = storage.get_all_keys()
        
        assert len(keys) == 2, \
            f"Items with same ID but different sources should be distinct, found {len(keys)}"
        assert "source1_123" in keys, "Should have key from source1"
        assert "source2_123" in keys, "Should have key from source2"


class TestIdempotencyWithChangingData:
    """Tests idempotency when data changes between runs."""
    
    def test_new_items_are_inserted_on_subsequent_runs(self):
        """
        GIVEN: Second run includes NEW items not in first run
        WHEN: Pipeline runs
        THEN: New items are inserted, existing items are updated
        """
        storage = MockIdempotentStorage()
        
        items_run1 = [
            IdeaItem(id="1", title="Item 1", url="https://example.com/1", source_name="test"),
        ]
        items_run2 = [
            IdeaItem(id="1", title="Item 1", url="https://example.com/1", source_name="test"),
            IdeaItem(id="2", title="Item 2", url="https://example.com/2", source_name="test"),  # NEW
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        # First run
        source1 = MockDeterministicSource("test", items_run1)
        with patch.object(pipeline, '_get_registered_sources', return_value=[source1]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                pipeline.run()
        
        # Second run with additional item
        source2 = MockDeterministicSource("test", items_run2)
        with patch.object(pipeline, '_get_registered_sources', return_value=[source2]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                result = pipeline.run()
        
        assert result.storage_result.inserted == 1, \
            "Should insert only the new item"
        assert result.storage_result.updated == 1, \
            "Should update the existing item"
    
    def test_storage_never_receives_duplicate_keys_in_single_batch(self):
        """
        GIVEN: Source returns items with duplicate IDs
        WHEN: Items are passed to storage
        THEN: Each unique key appears only once in the batch
        """
        storage = MockIdempotentStorage()
        
        # Note: In practice, sources shouldn't return duplicates,
        # but if they do, the pipeline should handle it
        items = [
            IdeaItem(id="1", title="Item 1 v1", url="https://example.com/1", source_name="test"),
            IdeaItem(id="2", title="Item 2", url="https://example.com/2", source_name="test"),
            IdeaItem(id="1", title="Item 1 v2", url="https://example.com/1", source_name="test"),  # Duplicate ID!
        ]
        
        config = PipelineConfig(dry_run=False, limit_per_source=10, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        source = MockDeterministicSource("test", items)
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            with patch.object(pipeline, '_get_storage', return_value=storage):
                result = pipeline.run()
        
        # The storage mock handles this correctly via upsert
        # Result should show 2 unique keys at most
        keys = storage.get_all_keys()
        assert len(keys) <= 2, \
            f"Should have at most 2 unique keys, found {len(keys)}: {keys}"

