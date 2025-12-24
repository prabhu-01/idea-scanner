#!/usr/bin/env python3
"""
Idea Digest - Daily idea discovery and digest pipeline.

Command-line entry point for running the full pipeline:
  - Fetch ideas from multiple sources (HackerNews, ProductHunt, GitHub)
  - Score and tag items based on configured interests
  - Store results to Airtable (or mock storage in dev)
  - Print execution summary

Usage:
    python main.py                      # Run full pipeline
    python main.py --dry-run            # Fetch and score only, no storage
    python main.py --limit-per-source 5 # Limit items per source
    python main.py --verbose            # Show detailed progress

Examples:
    # Development run (dry-run with small limit)
    python main.py --dry-run --limit-per-source 3 --verbose

    # Production run
    python main.py --limit-per-source 20
"""

import argparse
import sys

from src.pipeline import (
    IdeaDigestPipeline,
    PipelineConfig,
    PipelineResult,
    run_pipeline,
)
from src.config import (
    DEFAULT_LIMIT_PER_SOURCE,
    print_config_summary,
    validate_config,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="idea-digest",
        description="Fetch, score, and store ideas from multiple sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Run full pipeline with defaults
  %(prog)s --dry-run                 Fetch and score only, skip storage
  %(prog)s --limit-per-source 5      Limit to 5 items per source
  %(prog)s --sources hackernews      Only fetch from Hacker News
  %(prog)s --since-days weekly       GitHub trending: weekly instead of daily
  %(prog)s --digest-limit 20         Include max 20 items in digest
  %(prog)s --skip-digest             Run pipeline without generating digest
  %(prog)s -v --dry-run -l 3         Verbose dry-run with 3 items per source
        """,
    )
    
    # Core options
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Fetch and score items but skip storage (no writes)",
    )
    
    parser.add_argument(
        "--limit-per-source", "-l",
        type=int,
        default=None,
        metavar="N",
        help=f"Maximum items to fetch per source (default: {DEFAULT_LIMIT_PER_SOURCE})",
    )
    
    parser.add_argument(
        "--since-days", "-s",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Time range for GitHub trending (default: daily)",
    )
    
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["hackernews", "producthunt", "github"],
        metavar="SOURCE",
        help="Only fetch from specific sources (default: all)",
    )
    
    # Digest options
    parser.add_argument(
        "--digest-limit",
        type=int,
        default=None,
        metavar="N",
        help="Maximum items to include in digest (default: 50)",
    )
    
    parser.add_argument(
        "--digest-days",
        type=int,
        default=None,
        metavar="N",
        help="Number of days to include in digest (default: 1)",
    )
    
    parser.add_argument(
        "--skip-digest",
        action="store_true",
        help="Skip digest generation (storage only)",
    )
    
    # Output options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress and debug info",
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only show errors and final summary",
    )
    
    # Info options
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and exit",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    
    return parser


def show_config() -> None:
    """Display current configuration."""
    print("=" * 60)
    print("Idea Digest Configuration")
    print("=" * 60)
    print_config_summary()
    
    errors = validate_config()
    if errors:
        print("\nConfiguration warnings:")
        for error in errors:
            print(f"  ⚠️  {error}")
    else:
        print("\n✓ Configuration valid")
    print("=" * 60)


def print_result_summary(result: PipelineResult, verbose: bool = False) -> None:
    """Print the pipeline result summary."""
    print(result.to_summary())
    
    if verbose and result.total_items_scored > 0:
        print("\nTop scoring items would be shown here in verbose mode.")


def main(argv: list = None) -> int:
    """
    Main entry point.
    
    Args:
        argv: Command-line arguments (default: sys.argv[1:]).
        
    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Handle --show-config
    if args.show_config:
        show_config()
        return 0
    
    # Print header (unless quiet)
    if not args.quiet:
        print("=" * 60)
        print("Idea Digest Pipeline")
        print("=" * 60)
        
        if args.dry_run:
            print("Mode: DRY RUN (no storage writes)")
        
        if args.verbose:
            print("\nConfiguration:")
            print_config_summary()
            print()
    
    # Create pipeline config from CLI args
    config = PipelineConfig(
        limit_per_source=args.limit_per_source or DEFAULT_LIMIT_PER_SOURCE,
        dry_run=args.dry_run,
        since_days=args.since_days,
        verbose=args.verbose,
        sources=args.sources,
        digest_limit=args.digest_limit or 50,
        digest_days=args.digest_days or 1,
        skip_digest=args.skip_digest,
    )
    
    # Show effective settings
    if not args.quiet:
        print(f"Settings:")
        print(f"  Limit per source: {config.limit_per_source}")
        print(f"  Since: {config.since_days}")
        print(f"  Sources: {config.sources or 'all'}")
        print(f"  Dry run: {config.dry_run}")
        print(f"  Digest limit: {config.digest_limit}")
        print(f"  Digest days: {config.digest_days}")
        print(f"  Skip digest: {config.skip_digest}")
        print()
    
    # Run the pipeline
    try:
        pipeline = IdeaDigestPipeline(config)
        result = pipeline.run()
        
        # Print summary
        if not args.quiet:
            print_result_summary(result, args.verbose)
        
        # Determine exit code
        if result.sources_failed > 0 and result.sources_succeeded == 0:
            # All sources failed
            return 1
        
        if result.storage_result and result.storage_result.failed > 0:
            # Some storage failures
            print(f"\n⚠️  {result.storage_result.failed} items failed to store")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
