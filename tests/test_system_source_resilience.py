"""
Source Resilience Tests

Verifies that the pipeline continues running when individual sources fail,
and that failures are properly reported without halting execution.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.pipeline import IdeaDigestPipeline, PipelineConfig, PipelineResult

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, TEST_DATA


class MockSuccessSource(Source):
    """A source that always succeeds with predictable items."""
    
    def __init__(self, name: str, items_to_return: int = 3):
        self._name = name
        self._items_to_return = items_to_return
    
    @property
    def name(self) -> str:
        return self._name
    
    def fetch_items(self, limit=None):
        count = min(limit or self._items_to_return, self._items_to_return)
        return [
            IdeaItem(
                id=f"{self._name}_{i}",
                title=f"Item {i} from {self._name}",
                url=f"https://example.com/{self._name}/{i}",
                source_name=self._name,
                description=f"Description for item {i}",
            )
            for i in range(count)
        ]


class MockFailingSource(Source):
    """A source that always raises an exception."""
    
    def __init__(self, name: str, exception_type: type = Exception, message: str = "Simulated failure"):
        self._name = name
        self._exception_type = exception_type
        self._message = message
    
    @property
    def name(self) -> str:
        return self._name
    
    def fetch_items(self, limit=None):
        raise self._exception_type(self._message)


class TestPipelineContinuesOnSourceFailure:
    """Tests that pipeline continues when sources fail."""
    
    def test_pipeline_continues_when_one_source_fails(self):
        """
        GIVEN: Three sources where one raises an exception
        WHEN: Pipeline is run
        THEN: Other sources are still fetched successfully
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        # Replace sources with our mocks
        sources = [
            MockSuccessSource("source1", items_to_return=3),
            MockFailingSource("source2", message="Network timeout"),
            MockSuccessSource("source3", items_to_return=2),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        # Should have results from both successful sources
        assert result.total_items_fetched >= 5, \
            f"Expected items from successful sources, got {result.total_items_fetched}"
        
        # Should have recorded the failure
        assert result.sources_failed == 1, \
            f"Expected 1 failed source, got {result.sources_failed}"
        
        # Should have recorded successes
        assert result.sources_succeeded == 2, \
            f"Expected 2 successful sources, got {result.sources_succeeded}"
    
    def test_pipeline_continues_when_first_source_fails(self):
        """
        GIVEN: The FIRST source in the list fails
        WHEN: Pipeline is run
        THEN: Subsequent sources are still processed
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockFailingSource("first_source"),
            MockSuccessSource("second_source", items_to_return=3),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.sources_succeeded >= 1, \
            "Pipeline should continue after first source fails"
        assert result.total_items_fetched >= 3, \
            "Should have items from the successful source"
    
    def test_pipeline_continues_when_last_source_fails(self):
        """
        GIVEN: The LAST source in the list fails
        WHEN: Pipeline is run
        THEN: Previous sources' results are preserved
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockSuccessSource("first_source", items_to_return=3),
            MockFailingSource("last_source"),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.sources_succeeded == 1, \
            "First source should succeed"
        assert result.total_items_fetched >= 3, \
            "Should preserve items from successful source"


class TestFailureSummaryAccuracy:
    """Tests that failure summaries accurately reflect what happened."""
    
    def test_summary_reflects_partial_success(self):
        """
        GIVEN: Pipeline run where some sources fail
        WHEN: Summary is generated
        THEN: Summary shows correct counts for success and failure
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockSuccessSource("working1", items_to_return=2),
            MockFailingSource("broken"),
            MockSuccessSource("working2", items_to_return=3),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        summary = result.to_summary()
        
        # Summary should contain success indicators for working sources
        assert "working1" in summary.lower() or "2" in summary, \
            "Summary should mention successful sources"
        
        # Summary should indicate failure
        assert result.sources_failed == 1, \
            "Should track failure count"
    
    def test_failed_source_error_is_recorded(self):
        """
        GIVEN: A source fails with a specific error message
        WHEN: Pipeline completes
        THEN: The error message is preserved in the result
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        error_message = "Connection refused to API endpoint"
        sources = [
            MockFailingSource("api_source", message=error_message),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        # Find the source result for the failed source
        failed_results = [sr for sr in result.source_results if not sr.success]
        
        assert len(failed_results) == 1, "Should have one failed result"
        assert error_message in failed_results[0].error, \
            f"Error message should be preserved, got: {failed_results[0].error}"


class TestDifferentExceptionTypes:
    """Tests handling of various exception types."""
    
    def test_network_timeout_does_not_halt_pipeline(self):
        """
        GIVEN: A source raises a timeout-like exception
        WHEN: Pipeline is run
        THEN: Pipeline continues without crashing
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockFailingSource("timeout_source", TimeoutError, "Connection timed out"),
            MockSuccessSource("healthy_source"),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.sources_succeeded >= 1, \
            "Timeout in one source should not halt others"
    
    def test_value_error_does_not_halt_pipeline(self):
        """
        GIVEN: A source raises a ValueError (data parsing error)
        WHEN: Pipeline is run
        THEN: Pipeline continues without crashing
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockFailingSource("parse_error_source", ValueError, "Invalid JSON response"),
            MockSuccessSource("healthy_source"),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.sources_succeeded >= 1, \
            "ValueError in one source should not halt others"
    
    def test_all_sources_failing_produces_valid_result(self):
        """
        GIVEN: ALL sources fail
        WHEN: Pipeline is run
        THEN: A valid result is returned (not an exception)
        """
        config = PipelineConfig(dry_run=True, limit_per_source=3)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockFailingSource("source1"),
            MockFailingSource("source2"),
            MockFailingSource("source3"),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert isinstance(result, PipelineResult), \
            "Should return a valid result even when all sources fail"
        assert result.total_items_fetched == 0, \
            "Should have zero items when all fail"
        assert result.sources_failed == 3, \
            "Should track all three failures"

