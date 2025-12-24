#!/usr/bin/env python3
"""
Test Runner Script for Idea Digest

This script provides a convenient way to run tests with formatted output
and automatic result file generation.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --category config  # Run specific category
    python run_tests.py --quick           # Run quick sanity tests only
    python run_tests.py --verbose         # Verbose output
    python run_tests.py --list            # List available categories
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Test categories mapping
TEST_CATEGORIES = {
    "config": "tests/test_system_config_validation.py",
    "sources": "tests/test_system_source_resilience.py",
    "pipeline": "tests/test_system_pipeline_orchestration.py",
    "idempotency": "tests/test_system_idempotency.py",
    "digest": "tests/test_system_digest_correctness.py",
    "cli": "tests/test_system_cli_behavior.py",
    "automation": "tests/test_system_automation_safety.py",
    "sanity": "tests/test_system_operational_sanity.py",
    "unit_digest": "tests/test_digest.py",
    "unit_pipeline": "tests/test_pipeline.py",
    "unit_scoring": "tests/test_scoring.py",
    "unit_sources": "tests/test_sources.py",
    "unit_storage": "tests/test_storage.py",
}

CATEGORY_DESCRIPTIONS = {
    "config": "Configuration validation - env vars, defaults, error messages",
    "sources": "Source resilience - error isolation, partial failures",
    "pipeline": "Pipeline orchestration - execution order, dry-run behavior",
    "idempotency": "Idempotency - duplicate prevention, consistent results",
    "digest": "Digest correctness - grouping, ordering, format",
    "cli": "CLI behavior - argument parsing, help text, exit codes",
    "automation": "Automation safety - GitHub Actions workflow validation",
    "sanity": "Operational sanity - end-to-end with mocks",
    "unit_digest": "Unit tests - digest module",
    "unit_pipeline": "Unit tests - pipeline module",
    "unit_scoring": "Unit tests - scoring module",
    "unit_sources": "Unit tests - sources module",
    "unit_storage": "Unit tests - storage module",
}


def list_categories():
    """Print available test categories."""
    print("\n" + "=" * 60)
    print("AVAILABLE TEST CATEGORIES")
    print("=" * 60)
    
    print("\n📋 System Tests (Verification):")
    for key, desc in CATEGORY_DESCRIPTIONS.items():
        if not key.startswith("unit_"):
            print(f"  {key:15} - {desc}")
    
    print("\n📋 Unit Tests:")
    for key, desc in CATEGORY_DESCRIPTIONS.items():
        if key.startswith("unit_"):
            name = key.replace("unit_", "")
            print(f"  {key:15} - {desc}")
    
    print("\n" + "=" * 60)
    print("Usage examples:")
    print("  python run_tests.py --category config")
    print("  python run_tests.py --category pipeline,cli")
    print("  python run_tests.py  # Run all")
    print("=" * 60)


def run_tests(categories=None, verbose=False, quick=False):
    """Run tests with specified options."""
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add paths based on categories
    if categories:
        paths = []
        for cat in categories:
            if cat in TEST_CATEGORIES:
                path = TEST_CATEGORIES[cat]
                if Path(path).exists():
                    paths.append(path)
                else:
                    # Try alternate path (system folder)
                    alt_path = path.replace("system_", "system/test_")
                    if Path(alt_path).exists():
                        paths.append(alt_path)
        
        if paths:
            cmd.extend(paths)
        else:
            cmd.append("tests/")
    else:
        cmd.append("tests/")
    
    # Add options
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("--tb=short")
    
    if quick:
        cmd.extend(["-x", "--ff"])  # Stop on first failure, failed first
    
    # Print header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 60)
    print("IDEA DIGEST TEST RUNNER")
    print("=" * 60)
    print(f"Started:    {timestamp}")
    print(f"Categories: {', '.join(categories) if categories else 'ALL'}")
    print(f"Options:    {'verbose' if verbose else 'standard'}{', quick' if quick else ''}")
    print("=" * 60 + "\n")
    
    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Run Idea Digest tests with formatted output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                     # Run all tests
  python run_tests.py --category config   # Run config tests only
  python run_tests.py --category cli,digest  # Run multiple categories
  python run_tests.py --quick             # Stop on first failure
  python run_tests.py --verbose           # Detailed output
  python run_tests.py --list              # Show available categories
        """
    )
    
    parser.add_argument(
        "--category", "-c",
        type=str,
        help="Test category to run (comma-separated for multiple)",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output",
    )
    
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode - stop on first failure",
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available test categories",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_categories()
        return 0
    
    categories = None
    if args.category:
        categories = [c.strip() for c in args.category.split(",")]
    
    return run_tests(
        categories=categories,
        verbose=args.verbose,
        quick=args.quick,
    )


if __name__ == "__main__":
    sys.exit(main())

