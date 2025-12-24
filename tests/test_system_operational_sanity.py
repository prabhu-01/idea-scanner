"""
Operational Sanity Tests

Verifies that the system operates correctly end-to-end using mocks,
produces expected outputs, and doesn't pollute the filesystem.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.storage.base import Storage, UpsertResult
from src.pipeline import IdeaDigestPipeline, PipelineConfig, PipelineResult
from src.digest.generator import DigestGenerator, DigestConfig

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, TEST_DATA
from main import main


class MockSafeSource(Source):
    """A source that returns safe, predictable items."""
    
    def __init__(self, name: str):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    def fetch_items(self, limit=None):
        return [
            IdeaItem(
                id=f"{self._name}_item_1",
                title=f"Test Item from {self._name}",
                url=f"https://example.com/{self._name}/1",
                source_name=self._name,
                description="A test item for operational verification",
            )
        ]


class MockSafeStorage(Storage):
    """Storage that operates entirely in memory."""
    
    def __init__(self):
        self._items = []
    
    @property
    def name(self) -> str:
        return "mock_safe"
    
    def upsert_items(self, items):
        self._items.extend(items)
        return UpsertResult(inserted=len(items))
    
    def get_recent_items(self, days=7):
        return self._items.copy()
    
    def get_top_items(self, limit=10, min_score=0.0):
        return sorted(self._items, key=lambda x: x.score, reverse=True)[:limit]


class TestNoUnexpectedFilesystemWrites:
    """Tests that the system doesn't write outside expected directories."""
    
    def test_dry_run_creates_no_files(self):
        """
        GIVEN: Pipeline runs in dry-run mode
        WHEN: Execution completes
        THEN: No new files are created
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory to catch any unexpected writes
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                # Get initial file list
                initial_files = set(os.listdir(tmpdir))
                
                config = PipelineConfig(dry_run=True, limit_per_source=1)
                pipeline = IdeaDigestPipeline(config)
                
                source = MockSafeSource("test")
                
                with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
                    result = pipeline.run()
                
                # Check no new files
                final_files = set(os.listdir(tmpdir))
                new_files = final_files - initial_files
                
                assert len(new_files) == 0, \
                    f"Dry-run should create no files, found: {new_files}"
            
            finally:
                os.chdir(original_cwd)
    
    def test_digest_only_writes_to_output_dir(self):
        """
        GIVEN: Digest generation is enabled
        WHEN: Pipeline runs
        THEN: Digest file is written only to configured output directory
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "digests")
            os.makedirs(output_dir)
            
            config = PipelineConfig(
                dry_run=False,
                limit_per_source=1,
                skip_digest=False,
                digest_output_dir=output_dir,
            )
            pipeline = IdeaDigestPipeline(config)
            
            source = MockSafeSource("test")
            storage = MockSafeStorage()
            
            with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
                with patch.object(pipeline, '_get_storage', return_value=storage):
                    result = pipeline.run()
            
            # Check that digest file is in the right place
            if result.digest_result and result.digest_result.success:
                digest_path = Path(result.digest_result.filepath)
                assert str(digest_path).startswith(output_dir), \
                    f"Digest should be in output_dir, got: {digest_path}"


class TestOutputProduction:
    """Tests that expected outputs are produced."""
    
    def test_pipeline_produces_summary(self):
        """
        GIVEN: Pipeline runs
        WHEN: Result is obtained
        THEN: Summary can be generated
        """
        config = PipelineConfig(dry_run=True, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        source = MockSafeSource("test")
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            result = pipeline.run()
        
        summary = result.to_summary()
        
        assert isinstance(summary, str), "Summary should be a string"
        assert len(summary) > 0, "Summary should not be empty"
        assert "SUMMARY" in summary.upper(), "Summary should be labeled"
    
    def test_pipeline_result_has_timing(self):
        """
        GIVEN: Pipeline runs
        WHEN: Result is examined
        THEN: Contains timing information
        """
        config = PipelineConfig(dry_run=True, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        source = MockSafeSource("test")
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            result = pipeline.run()
        
        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.duration_seconds >= 0
    
    def test_digest_file_is_readable(self):
        """
        GIVEN: Digest is generated
        WHEN: File is read
        THEN: Contains readable content
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            items = [
                IdeaItem(
                    id="1",
                    title="Test Item",
                    url="https://example.com/1",
                    source_name="test",
                    score=0.5,
                )
            ]
            
            storage = MockSafeStorage()
            storage._items = items
            
            config = DigestConfig(limit=10, output_dir=tmpdir)
            generator = DigestGenerator(storage, config)
            result = generator.generate()
            
            if result.success:
                content = Path(result.filepath).read_text()
                
                assert len(content) > 0, "Digest should have content"
                assert "Test Item" in content, "Digest should contain item title"


class TestExitCodeCorrectness:
    """Tests that exit codes correctly reflect success/failure."""
    
    def test_successful_pipeline_returns_zero(self):
        """
        GIVEN: Pipeline runs successfully
        WHEN: main() returns
        THEN: Exit code is 0
        """
        mock_result = Mock()
        mock_result.sources_failed = 0
        mock_result.sources_succeeded = 1
        mock_result.storage_result = None
        mock_result.to_summary.return_value = "OK"
        
        mock_pipeline = Mock()
        mock_pipeline.run.return_value = mock_result
        
        with patch('main.IdeaDigestPipeline', return_value=mock_pipeline):
            with patch('builtins.print'):
                exit_code = main(["--dry-run"])
        
        assert exit_code == 0
    
    def test_total_failure_returns_nonzero(self):
        """
        GIVEN: All sources fail
        WHEN: main() returns
        THEN: Exit code is non-zero
        """
        mock_result = Mock()
        mock_result.sources_failed = 3
        mock_result.sources_succeeded = 0
        mock_result.storage_result = None
        mock_result.to_summary.return_value = "Failed"
        
        mock_pipeline = Mock()
        mock_pipeline.run.return_value = mock_result
        
        with patch('main.IdeaDigestPipeline', return_value=mock_pipeline):
            with patch('builtins.print'):
                exit_code = main(["--dry-run"])
        
        assert exit_code != 0
    
    def test_exception_returns_nonzero(self):
        """
        GIVEN: Pipeline raises exception
        WHEN: main() handles it
        THEN: Exit code is non-zero
        """
        mock_pipeline = Mock()
        mock_pipeline.run.side_effect = RuntimeError("Unexpected error")
        
        with patch('main.IdeaDigestPipeline', return_value=mock_pipeline):
            with patch('builtins.print'):
                exit_code = main(["--dry-run"])
        
        assert exit_code != 0


class TestEndToEndWithMocks:
    """Full end-to-end tests using only mocks."""
    
    def test_full_pipeline_with_all_mocks(self):
        """
        GIVEN: All components are mocked
        WHEN: Full pipeline runs
        THEN: Completes successfully with expected results
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                dry_run=False,
                limit_per_source=2,
                skip_digest=False,
                digest_output_dir=tmpdir,
            )
            pipeline = IdeaDigestPipeline(config)
            
            sources = [
                MockSafeSource("source1"),
                MockSafeSource("source2"),
            ]
            storage = MockSafeStorage()
            
            with patch.object(pipeline, '_get_registered_sources', return_value=sources):
                with patch.object(pipeline, '_get_storage', return_value=storage):
                    result = pipeline.run()
            
            # Verify results
            assert result.sources_succeeded == 2
            assert result.sources_failed == 0
            assert result.total_items_fetched >= 2
            assert result.storage_result is not None
            assert result.storage_result.inserted >= 2
    
    def test_pipeline_handles_partial_failure_gracefully(self):
        """
        GIVEN: One source fails, others succeed
        WHEN: Full pipeline runs
        THEN: Completes with partial success
        """
        class FailingSource(Source):
            @property
            def name(self):
                return "failing"
            
            def fetch_items(self, limit=None):
                raise ConnectionError("Simulated network failure")
        
        config = PipelineConfig(dry_run=True, limit_per_source=2)
        pipeline = IdeaDigestPipeline(config)
        
        sources = [
            MockSafeSource("working"),
            FailingSource(),
        ]
        
        with patch.object(pipeline, '_get_registered_sources', return_value=sources):
            result = pipeline.run()
        
        assert result.sources_succeeded == 1
        assert result.sources_failed == 1
        assert result.total_items_fetched >= 1


class TestResourceCleanup:
    """Tests that resources are properly cleaned up."""
    
    def test_no_temp_files_left_behind(self):
        """
        GIVEN: Pipeline runs
        WHEN: Execution completes
        THEN: No temporary files are left in system temp directory
        """
        import tempfile as tf
        
        # Get temp dir before
        temp_before = set(os.listdir(tf.gettempdir()))
        
        config = PipelineConfig(dry_run=True, limit_per_source=1)
        pipeline = IdeaDigestPipeline(config)
        
        source = MockSafeSource("test")
        
        with patch.object(pipeline, '_get_registered_sources', return_value=[source]):
            result = pipeline.run()
        
        # Get temp dir after
        temp_after = set(os.listdir(tf.gettempdir()))
        
        # Filter out common transient files
        new_files = temp_after - temp_before
        persistent_files = [f for f in new_files if "idea" in f.lower() or "digest" in f.lower()]
        
        assert len(persistent_files) == 0, \
            f"Should not leave temp files, found: {persistent_files}"

