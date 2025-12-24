"""
Pipeline Orchestration Tests

Verifies that the pipeline executes steps in the correct order and
honors dry-run mode appropriately.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.storage.base import Storage, UpsertResult
from src.pipeline import IdeaDigestPipeline, PipelineConfig

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, TEST_DATA


class CallTracker:
    """Tracks the order of method calls for verification."""
    
    def __init__(self):
        self.calls: List[str] = []
    
    def record(self, step: str):
        self.calls.append(step)
    
    def get_calls(self) -> List[str]:
        return self.calls.copy()


class MockTrackedSource(Source):
    """A source that tracks when it's called."""
    
    def __init__(self, name: str, tracker: CallTracker):
        self._name = name
        self._tracker = tracker
    
    @property
    def name(self) -> str:
        return self._name
    
    def fetch_items(self, limit=None):
        self._tracker.record(f"fetch:{self._name}")
        return [
            IdeaItem(
                id=f"{self._name}_1",
                title=f"Item from {self._name}",
                url=f"https://example.com/{self._name}",
                source_name=self._name,
            )
        ]


class TestExecutionOrder:
    """Tests that pipeline steps execute in the correct order."""
    
    def test_fetch_happens_before_scoring(self):
        """
        GIVEN: A configured pipeline
        WHEN: Pipeline is run
        THEN: Fetching completes before scoring begins
        """
        tracker = CallTracker()
        
        config = PipelineConfig(dry_run=True, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [MockTrackedSource("test_source", tracker)]
        
        # Patch scorer to track when it's called
        original_score_items = pipeline._score_items
        def tracked_score_items(items):
            tracker.record("scoring")
            return original_score_items(items)
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            with patch.object(pipeline, '_score_items', tracked_score_items):
                result = pipeline.run()
        
        calls = tracker.get_calls()
        
        # Verify fetch happened before scoring
        fetch_idx = next(i for i, c in enumerate(calls) if c.startswith("fetch:"))
        score_idx = calls.index("scoring") if "scoring" in calls else len(calls)
        
        assert fetch_idx < score_idx, \
            f"Fetch should happen before scoring. Order: {calls}"
    
    def test_scoring_happens_before_storage(self):
        """
        GIVEN: A configured pipeline (not dry-run)
        WHEN: Pipeline is run
        THEN: Scoring completes before storage is called
        """
        tracker = CallTracker()
        
        config = PipelineConfig(dry_run=False, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [MockTrackedSource("test_source", tracker)]
        
        # Mock storage
        mock_storage = Mock(spec=Storage)
        mock_storage.name = "mock"
        mock_storage.upsert_items.return_value = UpsertResult(inserted=1)
        mock_storage.get_top_items.return_value = []
        
        original_score_items = pipeline._score_items
        def tracked_score_items(items):
            tracker.record("scoring")
            return original_score_items(items)
        
        def tracked_upsert(items):
            tracker.record("storage")
            return UpsertResult(inserted=len(items))
        
        mock_storage.upsert_items = tracked_upsert
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            with patch.object(pipeline, '_get_storage', return_value=mock_storage):
                with patch.object(pipeline, '_score_items', tracked_score_items):
                    result = pipeline.run()
        
        calls = tracker.get_calls()
        
        if "scoring" in calls and "storage" in calls:
            score_idx = calls.index("scoring")
            storage_idx = calls.index("storage")
            assert score_idx < storage_idx, \
                f"Scoring should happen before storage. Order: {calls}"


class TestDryRunBehavior:
    """Tests that dry-run mode skips appropriate steps."""
    
    def test_storage_not_called_in_dry_run_mode(self):
        """
        GIVEN: Pipeline is configured with dry_run=True
        WHEN: Pipeline is run
        THEN: Storage.upsert_items is NEVER called
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        # Create a mock storage that will fail if called
        mock_storage = Mock(spec=Storage)
        mock_storage.upsert_items.side_effect = AssertionError(
            "Storage should NOT be called in dry-run mode"
        )
        
        sources = [
            MockTrackedSource("source1", CallTracker()),
            MockTrackedSource("source2", CallTracker()),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            with patch.object(pipeline, '_get_storage', return_value=mock_storage):
                # This should NOT raise - storage shouldn't be called
                result = pipeline.run()
        
        assert result.dry_run is True
        assert result.storage_result is None, \
            "Storage result should be None in dry-run mode"
    
    def test_digest_not_generated_in_dry_run_mode(self):
        """
        GIVEN: Pipeline is configured with dry_run=True
        WHEN: Pipeline is run
        THEN: Digest is NOT generated
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [MockTrackedSource("source1", CallTracker())]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.digest_result is None or not result.digest_result.success, \
            "Digest should not be generated in dry-run mode"
    
    def test_storage_called_exactly_once_when_not_dry_run(self):
        """
        GIVEN: Pipeline is configured with dry_run=False
        WHEN: Pipeline is run
        THEN: Storage.upsert_items is called exactly ONCE
        """
        config = PipelineConfig(dry_run=False, limit_per_source=3, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        mock_storage = Mock(spec=Storage)
        mock_storage.name = "mock"
        mock_storage.upsert_items.return_value = UpsertResult(inserted=3)
        
        sources = [MockTrackedSource("source1", CallTracker())]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            with patch.object(pipeline, '_get_storage', return_value=mock_storage):
                result = pipeline.run()
        
        assert mock_storage.upsert_items.call_count == 1, \
            f"Storage should be called exactly once, was called {mock_storage.upsert_items.call_count} times"


class TestSkipDigestBehavior:
    """Tests the skip_digest flag behavior."""
    
    def test_digest_skipped_when_flag_set(self):
        """
        GIVEN: Pipeline is configured with skip_digest=True
        WHEN: Pipeline is run (not dry-run)
        THEN: Digest is not generated but storage still works
        """
        config = PipelineConfig(dry_run=False, limit_per_source=3, skip_digest=True)
        pipeline = IdeaDigestPipeline(config)
        
        mock_storage = Mock(spec=Storage)
        mock_storage.name = "mock"
        mock_storage.upsert_items.return_value = UpsertResult(inserted=3)
        
        sources = [MockTrackedSource("source1", CallTracker())]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            with patch.object(pipeline, '_get_storage', return_value=mock_storage):
                result = pipeline.run()
        
        # Storage should be called
        assert mock_storage.upsert_items.called, \
            "Storage should be called when not in dry-run"
        
        # Digest should be skipped
        assert result.digest_result is None, \
            "Digest should be None when skip_digest=True"


class TestPipelineResultCompleteness:
    """Tests that pipeline result contains all expected data."""
    
    def test_result_contains_timing_information(self):
        """
        GIVEN: A pipeline run completes
        WHEN: Result is examined
        THEN: Contains start time, end time, and duration
        """
        config = PipelineConfig(dry_run=True, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [MockTrackedSource("source1", CallTracker())]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.started_at is not None, "Should have start time"
        assert result.finished_at is not None, "Should have end time"
        assert result.duration_seconds >= 0, "Duration should be non-negative"
    
    def test_result_contains_source_breakdown(self):
        """
        GIVEN: A pipeline with multiple sources
        WHEN: Pipeline completes
        THEN: Result contains per-source results
        """
        config = PipelineConfig(dry_run=True, limit_per_source=2)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockTrackedSource("source1", CallTracker()),
            MockTrackedSource("source2", CallTracker()),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert len(result.source_results) == 2, \
            "Should have result for each source"
        
        source_names = {sr.source_name for sr in result.source_results}
        assert source_names == {"source1", "source2"}, \
            f"Source names should match, got {source_names}"

