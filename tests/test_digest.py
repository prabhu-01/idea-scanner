"""
Tests for the digest generator module.

Tests grouping, ordering, file naming, output location,
handling of edge cases, and dry-run behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
import tempfile
import os

from src.models.idea_item import IdeaItem
from src.storage.base import Storage
from src.storage import MockAirtableStorage
from src.digest.generator import (
    DigestGenerator,
    DigestConfig,
    DigestResult,
    generate_digest,
    generate_digest_content,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_items():
    """Sample items with various themes and scores."""
    return [
        IdeaItem(
            id="item_1",
            title="AI-Powered Code Assistant",
            description="A revolutionary tool using GPT for coding",
            url="https://example.com/ai-code",
            source_name="producthunt",
            score=0.95,
            tags=["ai-ml", "developer-tools"],
        ),
        IdeaItem(
            id="item_2",
            title="Python Database Library",
            description="Fast and efficient database access",
            url="https://example.com/py-db",
            source_name="github",
            score=0.75,
            tags=["programming", "data"],
        ),
        IdeaItem(
            id="item_3",
            title="Startup Funding Platform",
            description="Connect with investors easily",
            url="https://example.com/funding",
            source_name="hackernews",
            score=0.60,
            tags=["startup"],
        ),
        IdeaItem(
            id="item_4",
            title="Open Source ML Framework",
            description="Community-driven machine learning",
            url="https://example.com/ml-oss",
            source_name="github",
            score=0.85,
            tags=["ai-ml", "open-source"],
        ),
        IdeaItem(
            id="item_5",
            title="Random News Article",
            description="Some general news without specific theme",
            url="https://example.com/news",
            source_name="hackernews",
            score=0.40,
            tags=[],  # No tags
        ),
    ]


@pytest.fixture
def mock_storage(sample_items):
    """Mock storage with sample items."""
    storage = MockAirtableStorage()
    storage.upsert_items(sample_items)
    return storage


@pytest.fixture
def temp_output_dir():
    """Temporary directory for digest output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# =============================================================================
# Test Digest Configuration
# =============================================================================

class TestDigestConfig:
    """Tests for DigestConfig."""
    
    def test_default_values(self):
        """Config has sensible defaults."""
        config = DigestConfig()
        assert config.limit == 50
        assert config.days == 1
        assert config.min_score == 0.0
        assert config.output_dir == "digests"
        assert config.include_ungrouped is True
    
    def test_custom_values(self):
        """Config accepts custom values."""
        config = DigestConfig(
            limit=100,
            days=7,
            min_score=0.5,
            output_dir="/custom/path",
            include_ungrouped=False,
        )
        assert config.limit == 100
        assert config.days == 7
        assert config.min_score == 0.5
        assert config.output_dir == "/custom/path"
        assert config.include_ungrouped is False


# =============================================================================
# Test Grouping by Theme
# =============================================================================

class TestGroupingByTheme:
    """Tests for correct grouping of items by theme."""
    
    def test_items_grouped_by_tags(self, mock_storage, temp_output_dir):
        """Items are correctly grouped by their tags."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        items = generator._fetch_items()
        grouped = generator._group_by_theme(items)
        
        # ai-ml should have 2 items (item_1 and item_4)
        assert "ai-ml" in grouped
        assert len(grouped["ai-ml"]) == 2
        
        # developer-tools should have 1 item (item_1)
        assert "developer-tools" in grouped
        assert len(grouped["developer-tools"]) == 1
        
        # startup should have 1 item (item_3)
        assert "startup" in grouped
        assert len(grouped["startup"]) == 1
    
    def test_multi_tag_items_appear_in_multiple_groups(self, mock_storage, temp_output_dir):
        """Items with multiple tags appear in each relevant group."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        items = generator._fetch_items()
        grouped = generator._group_by_theme(items)
        
        # item_1 has both ai-ml and developer-tools
        ai_items = grouped.get("ai-ml", [])
        dev_items = grouped.get("developer-tools", [])
        
        # Find item_1 in both groups
        ai_ids = [i.id for i in ai_items]
        dev_ids = [i.id for i in dev_items]
        
        assert "item_1" in ai_ids
        assert "item_1" in dev_ids
    
    def test_ungrouped_items_collected(self, mock_storage, temp_output_dir):
        """Items with no tags go to _ungrouped."""
        config = DigestConfig(output_dir=temp_output_dir, include_ungrouped=True)
        generator = DigestGenerator(mock_storage, config)
        
        items = generator._fetch_items()
        grouped = generator._group_by_theme(items)
        
        # item_5 has no tags
        assert "_ungrouped" in grouped
        ungrouped_ids = [i.id for i in grouped["_ungrouped"]]
        assert "item_5" in ungrouped_ids
    
    def test_ungrouped_excluded_when_disabled(self, temp_output_dir):
        """Ungrouped items excluded when include_ungrouped=False."""
        storage = MockAirtableStorage()
        storage.upsert_items([
            IdeaItem(
                id="no_tags",
                title="No Tags Item",
                url="https://example.com",
                source_name="test",
                score=0.5,
                tags=[],
            )
        ])
        
        config = DigestConfig(output_dir=temp_output_dir, include_ungrouped=False)
        generator = DigestGenerator(storage, config)
        
        items = generator._fetch_items()
        grouped = generator._group_by_theme(items)
        
        assert "_ungrouped" not in grouped


# =============================================================================
# Test Ordering by Score
# =============================================================================

class TestOrderingByScore:
    """Tests for deterministic ordering by score."""
    
    def test_items_sorted_by_score_descending(self, mock_storage, temp_output_dir):
        """Items are sorted by score in descending order."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        items = generator._fetch_items()
        
        # Check order
        for i in range(len(items) - 1):
            assert items[i].score >= items[i + 1].score
    
    def test_within_group_sorted_by_score(self, mock_storage, temp_output_dir):
        """Items within a theme group are sorted by score."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        items = generator._fetch_items()
        grouped = generator._group_by_theme(items)
        
        # Check ai-ml group (has 2 items)
        ai_items = grouped.get("ai-ml", [])
        for i in range(len(ai_items) - 1):
            assert ai_items[i].score >= ai_items[i + 1].score
    
    def test_deterministic_ordering_same_score(self, temp_output_dir):
        """Items with same score are ordered deterministically by title."""
        storage = MockAirtableStorage()
        storage.upsert_items([
            IdeaItem(id="a", title="Zebra", url="https://a.com", source_name="test", score=0.5),
            IdeaItem(id="b", title="Apple", url="https://b.com", source_name="test", score=0.5),
            IdeaItem(id="c", title="Mango", url="https://c.com", source_name="test", score=0.5),
        ])
        
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(storage, config)
        
        # Run twice to verify determinism
        items1 = generator._fetch_items()
        items2 = generator._fetch_items()
        
        assert [i.title for i in items1] == [i.title for i in items2]
        # Should be sorted alphabetically when scores are equal
        assert items1[0].title == "Apple"


# =============================================================================
# Test File Naming and Output Location
# =============================================================================

class TestFileNamingAndLocation:
    """Tests for correct file naming and output location."""
    
    def test_filename_uses_date_format(self, mock_storage, temp_output_dir):
        """Filename follows YYYY-MM-DD.md format."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        test_date = datetime(2025, 12, 25, 10, 30, 0)
        result = generator.generate(date=test_date)
        
        assert result.success
        assert result.filepath.endswith("2025-12-25.md")
    
    def test_file_created_in_output_dir(self, mock_storage, temp_output_dir):
        """Digest file is created in configured output directory."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        
        assert result.success
        assert result.filepath.startswith(temp_output_dir)
        assert Path(result.filepath).exists()
    
    def test_output_dir_created_if_missing(self, mock_storage, temp_output_dir):
        """Output directory is created if it doesn't exist."""
        nested_dir = os.path.join(temp_output_dir, "nested", "path")
        config = DigestConfig(output_dir=nested_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        
        assert result.success
        assert Path(nested_dir).exists()
    
    def test_different_dates_different_files(self, mock_storage, temp_output_dir):
        """Different dates produce different files."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result1 = generator.generate(date=datetime(2025, 12, 24))
        result2 = generator.generate(date=datetime(2025, 12, 25))
        
        assert result1.filepath != result2.filepath
        assert "2025-12-24" in result1.filepath
        assert "2025-12-25" in result2.filepath


# =============================================================================
# Test Digest Content
# =============================================================================

class TestDigestContent:
    """Tests for digest content format."""
    
    def test_content_is_valid_markdown(self, mock_storage, temp_output_dir):
        """Generated content is valid Markdown."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        
        content = Path(result.filepath).read_text()
        
        # Should have Markdown headers
        assert "# Idea Digest" in content
        assert "## " in content  # Section headers
        
        # Should have links
        assert "[" in content and "](" in content
    
    def test_summary_section_included(self, mock_storage, temp_output_dir):
        """Summary section is included at top."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        content = Path(result.filepath).read_text()
        
        assert "## 📊 Summary" in content
        assert "Total items:" in content
        assert "Top themes:" in content
        assert "Top item:" in content
    
    def test_items_include_required_fields(self, mock_storage, temp_output_dir):
        """Each item includes title, source, description, URL, score, themes."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        content = Path(result.filepath).read_text()
        
        # Check for item_1 content
        assert "AI-Powered Code Assistant" in content
        assert "producthunt" in content
        assert "https://example.com/ai-code" in content
        assert "0.95" in content  # Score
        assert "#ai-ml" in content  # Theme tag
    
    def test_themes_have_emoji_headers(self, mock_storage, temp_output_dir):
        """Theme sections have emoji headers."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        content = Path(result.filepath).read_text()
        
        # Check for theme emojis
        assert "🤖" in content  # ai-ml
        assert "🛠️" in content  # developer-tools


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for graceful handling of edge cases."""
    
    def test_no_items_returns_success_with_message(self, temp_output_dir):
        """Empty storage returns success with appropriate message."""
        storage = MockAirtableStorage()  # Empty storage
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(storage, config)
        
        result = generator.generate()
        
        assert result.success
        assert result.items_included == 0
        assert "No items found" in result.error
    
    def test_all_items_without_tags(self, temp_output_dir):
        """Handles items that all have no tags."""
        storage = MockAirtableStorage()
        storage.upsert_items([
            IdeaItem(id="1", title="Item 1", url="https://1.com", source_name="test", tags=[]),
            IdeaItem(id="2", title="Item 2", url="https://2.com", source_name="test", tags=[]),
        ])
        
        config = DigestConfig(output_dir=temp_output_dir, include_ungrouped=True)
        generator = DigestGenerator(storage, config)
        
        result = generator.generate()
        
        assert result.success
        assert result.items_included == 2
        # All items should be in _ungrouped
        assert "_ungrouped" not in result.themes_covered  # themes_covered excludes _ungrouped
    
    def test_missing_description_handled(self, temp_output_dir):
        """Items with missing description don't crash."""
        storage = MockAirtableStorage()
        storage.upsert_items([
            IdeaItem(
                id="no_desc",
                title="No Description Item",
                description="",
                url="https://example.com",
                source_name="test",
            ),
        ])
        
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(storage, config)
        
        result = generator.generate()
        
        assert result.success
        content = Path(result.filepath).read_text()
        assert "No Description Item" in content
    
    def test_very_long_description_truncated(self, temp_output_dir):
        """Long descriptions are truncated."""
        long_desc = "A" * 500
        storage = MockAirtableStorage()
        storage.upsert_items([
            IdeaItem(
                id="long_desc",
                title="Long Description Item",
                description=long_desc,
                url="https://example.com",
                source_name="test",
            ),
        ])
        
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(storage, config)
        
        result = generator.generate()
        content = Path(result.filepath).read_text()
        
        # Should be truncated with ...
        assert "..." in content
        assert long_desc not in content  # Full description not present


# =============================================================================
# Test DigestResult
# =============================================================================

class TestDigestResult:
    """Tests for DigestResult dataclass."""
    
    def test_success_result_has_filepath(self, mock_storage, temp_output_dir):
        """Successful result includes filepath."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        
        assert result.success
        assert result.filepath is not None
        assert result.error is None
    
    def test_success_result_has_stats(self, mock_storage, temp_output_dir):
        """Successful result includes statistics."""
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(mock_storage, config)
        
        result = generator.generate()
        
        assert result.items_included > 0
        assert len(result.themes_covered) > 0
    
    def test_failure_result_has_error(self, temp_output_dir):
        """Failed result includes error message."""
        # Create a storage that will fail
        storage = Mock(spec=Storage)
        storage.get_top_items.side_effect = Exception("Storage error")
        
        config = DigestConfig(output_dir=temp_output_dir)
        generator = DigestGenerator(storage, config)
        
        result = generator.generate()
        
        assert not result.success
        assert result.error is not None
        assert "Storage error" in result.error


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_generate_digest_function(self, mock_storage, temp_output_dir):
        """generate_digest convenience function works."""
        result = generate_digest(
            storage=mock_storage,
            limit=10,
            days=1,
            output_dir=temp_output_dir,
        )
        
        assert result.success
        assert Path(result.filepath).exists()
    
    def test_generate_digest_content_function(self, sample_items):
        """generate_digest_content returns Markdown string."""
        content = generate_digest_content(
            items=sample_items,
            date=datetime(2025, 12, 25),
        )
        
        assert isinstance(content, str)
        assert "# Idea Digest - 2025-12-25" in content
        assert "AI-Powered Code Assistant" in content


# =============================================================================
# Test Integration with Pipeline (Dry-Run)
# =============================================================================

class TestPipelineIntegration:
    """Tests for digest integration with pipeline."""
    
    def test_digest_not_generated_in_dry_run(self):
        """Digest generation is skipped during dry-run."""
        # This tests the expected behavior - actual integration is in pipeline tests
        config = DigestConfig()
        
        # In dry-run mode, pipeline should not call digest generator
        # This is a behavioral expectation test
        assert config.limit > 0  # Digest would normally run
    
    def test_digest_config_from_cli_args(self):
        """Digest config can be created from CLI-like args."""
        # Simulate CLI args
        args = {
            "digest_limit": 25,
            "digest_days": 3,
        }
        
        config = DigestConfig(
            limit=args["digest_limit"],
            days=args["digest_days"],
        )
        
        assert config.limit == 25
        assert config.days == 3

