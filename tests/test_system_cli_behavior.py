"""
CLI Behavior Tests

Verifies that command-line interface behaves correctly,
parses arguments properly, and produces expected outputs.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
import sys
from io import StringIO
from unittest.mock import patch, Mock
import argparse

from main import create_parser, main
from src.pipeline import PipelineConfig

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, MESSAGES


class TestArgumentParsing:
    """Tests for correct argument parsing."""
    
    def test_dry_run_flag_parsed_correctly(self):
        """
        GIVEN: CLI invoked with --dry-run
        WHEN: Arguments are parsed
        THEN: dry_run is True
        """
        parser = create_parser()
        args = parser.parse_args(["--dry-run"])
        
        assert args.dry_run is True, "dry_run should be True"
    
    def test_dry_run_short_flag_parsed_correctly(self):
        """
        GIVEN: CLI invoked with -n (short for --dry-run)
        WHEN: Arguments are parsed
        THEN: dry_run is True
        """
        parser = create_parser()
        args = parser.parse_args(["-n"])
        
        assert args.dry_run is True, "-n should set dry_run to True"
    
    def test_limit_per_source_parsed_as_integer(self):
        """
        GIVEN: CLI invoked with --limit-per-source 5
        WHEN: Arguments are parsed
        THEN: limit_per_source is integer 5
        """
        parser = create_parser()
        args = parser.parse_args(["--limit-per-source", "5"])
        
        assert args.limit_per_source == 5, "limit should be 5"
        assert isinstance(args.limit_per_source, int), "limit should be int"
    
    def test_limit_short_flag_works(self):
        """
        GIVEN: CLI invoked with -l 10
        WHEN: Arguments are parsed
        THEN: limit_per_source is 10
        """
        parser = create_parser()
        args = parser.parse_args(["-l", "10"])
        
        assert args.limit_per_source == 10, "-l should set limit"
    
    def test_sources_filter_accepts_multiple_values(self):
        """
        GIVEN: CLI invoked with --sources hackernews github
        WHEN: Arguments are parsed
        THEN: sources contains both values
        """
        parser = create_parser()
        args = parser.parse_args(["--sources", "hackernews", "github"])
        
        assert args.sources == ["hackernews", "github"], \
            f"sources should be list, got {args.sources}"
    
    def test_since_days_accepts_valid_choices(self):
        """
        GIVEN: CLI invoked with --since-days weekly
        WHEN: Arguments are parsed
        THEN: since_days is 'weekly'
        """
        parser = create_parser()
        args = parser.parse_args(["--since-days", "weekly"])
        
        assert args.since_days == "weekly"
    
    def test_digest_limit_parsed_correctly(self):
        """
        GIVEN: CLI invoked with --digest-limit 25
        WHEN: Arguments are parsed
        THEN: digest_limit is 25
        """
        parser = create_parser()
        args = parser.parse_args(["--digest-limit", "25"])
        
        assert args.digest_limit == 25


class TestInvalidArguments:
    """Tests for handling of invalid arguments."""
    
    def test_invalid_source_name_rejected(self):
        """
        GIVEN: CLI invoked with --sources invalid_source
        WHEN: Arguments are parsed
        THEN: argparse error is raised (clean exit, not crash)
        """
        parser = create_parser()
        
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--sources", "invalid_source"])
        
        # argparse exits with code 2 for invalid arguments
        assert exc_info.value.code == 2, \
            "Invalid source should cause clean argparse exit"
    
    def test_invalid_since_days_rejected(self):
        """
        GIVEN: CLI invoked with --since-days invalid
        WHEN: Arguments are parsed
        THEN: argparse error is raised
        """
        parser = create_parser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(["--since-days", "invalid"])
    
    def test_non_integer_limit_rejected(self):
        """
        GIVEN: CLI invoked with --limit-per-source abc
        WHEN: Arguments are parsed
        THEN: argparse error is raised
        """
        parser = create_parser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(["--limit-per-source", "abc"])


class TestHelpText:
    """Tests for help text availability and accuracy."""
    
    def test_help_flag_shows_usage(self):
        """
        GIVEN: CLI invoked with --help
        WHEN: Help is displayed
        THEN: Contains usage information
        """
        parser = create_parser()
        
        # Capture help output
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        
        # Help exits with code 0
        assert exc_info.value.code == 0
    
    def test_help_mentions_dry_run(self):
        """
        GIVEN: Parser help text
        WHEN: Examined
        THEN: Documents --dry-run flag
        """
        parser = create_parser()
        help_text = parser.format_help()
        
        assert "--dry-run" in help_text, "Help should document --dry-run"
        assert "storage" in help_text.lower(), "Help should explain what dry-run skips"
    
    def test_help_mentions_all_sources(self):
        """
        GIVEN: Parser help text
        WHEN: Examined
        THEN: Documents available source names
        """
        parser = create_parser()
        help_text = parser.format_help()
        
        assert "hackernews" in help_text.lower(), "Help should mention hackernews"
        assert "github" in help_text.lower(), "Help should mention github"


class TestConfigOverrides:
    """Tests that CLI flags properly override config defaults."""
    
    def test_cli_limit_overrides_config_default(self):
        """
        GIVEN: Config has a default limit and CLI specifies different limit
        WHEN: PipelineConfig is created from args
        THEN: CLI value is used
        """
        parser = create_parser()
        args = parser.parse_args(["--limit-per-source", "7"])
        
        config = PipelineConfig(
            limit_per_source=args.limit_per_source or 20,
            dry_run=args.dry_run,
        )
        
        assert config.limit_per_source == 7, \
            "CLI should override default"
    
    def test_cli_dry_run_true_overrides_default_false(self):
        """
        GIVEN: dry_run defaults to False
        WHEN: CLI specifies --dry-run
        THEN: config.dry_run is True
        """
        parser = create_parser()
        args = parser.parse_args(["--dry-run"])
        
        config = PipelineConfig(dry_run=args.dry_run)
        
        assert config.dry_run is True


class TestShowConfigBehavior:
    """Tests for --show-config flag."""
    
    def test_show_config_exits_zero(self):
        """
        GIVEN: CLI invoked with --show-config
        WHEN: main() runs
        THEN: Exits with code 0 (success)
        """
        # Mock print to capture output
        with patch('builtins.print'):
            exit_code = main(["--show-config"])
        
        assert exit_code == 0, "--show-config should exit successfully"
    
    def test_show_config_does_not_run_pipeline(self):
        """
        GIVEN: CLI invoked with --show-config
        WHEN: main() runs
        THEN: Pipeline is NOT executed
        """
        with patch('main.IdeaDigestPipeline') as mock_pipeline:
            with patch('builtins.print'):
                main(["--show-config"])
        
        mock_pipeline.assert_not_called(), \
            "--show-config should not create pipeline"


class TestExitCodes:
    """Tests for correct exit codes."""
    
    def test_successful_run_returns_zero(self):
        """
        GIVEN: Pipeline runs successfully
        WHEN: main() completes
        THEN: Returns exit code 0
        """
        # Mock the pipeline to return success
        mock_result = Mock()
        mock_result.sources_failed = 0
        mock_result.sources_succeeded = 1
        mock_result.storage_result = None
        mock_result.to_summary.return_value = "Success"
        
        mock_pipeline = Mock()
        mock_pipeline.run.return_value = mock_result
        
        with patch('main.IdeaDigestPipeline', return_value=mock_pipeline):
            with patch('builtins.print'):
                exit_code = main(["--dry-run"])
        
        assert exit_code == 0, "Successful run should return 0"
    
    def test_all_sources_failed_returns_nonzero(self):
        """
        GIVEN: All sources fail
        WHEN: main() completes
        THEN: Returns non-zero exit code
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
        
        assert exit_code != 0, "All sources failing should return non-zero"

