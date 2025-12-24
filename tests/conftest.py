"""
Pytest Configuration and Fixtures

This module provides:
- Custom test output formatting
- Timestamped result file generation
- Shared fixtures for all tests
- Test category organization
"""

import pytest
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from io import StringIO

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test configuration
from tests.test_config import (
    CONFIG, EXPECTED, TEST_DATA, MESSAGES, WORKFLOW, TEST_CATEGORIES,
    get_sample_item, get_all_sample_items
)


# =============================================================================
# TEST RESULT FILE CONFIGURATION
# =============================================================================

RESULTS_DIR = PROJECT_ROOT / "test_results"


def get_result_filename() -> str:
    """Generate timestamped result filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"test_results_{timestamp}.txt"


def ensure_results_dir():
    """Create results directory if it doesn't exist."""
    RESULTS_DIR.mkdir(exist_ok=True)


# =============================================================================
# PYTEST HOOKS FOR CUSTOM OUTPUT
# =============================================================================

class TestResultCollector:
    """Collects test results for formatted output."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time: datetime = None
        self.end_time: datetime = None
        self.categories: Dict[str, List[Dict]] = {}
    
    def add_result(self, nodeid: str, outcome: str, duration: float, message: str = ""):
        """Add a test result."""
        # Extract category from nodeid
        category = self._extract_category(nodeid)
        
        result = {
            "nodeid": nodeid,
            "name": self._extract_test_name(nodeid),
            "category": category,
            "outcome": outcome,
            "duration": duration,
            "message": message,
        }
        
        self.results.append(result)
        
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(result)
    
    def _extract_category(self, nodeid: str) -> str:
        """Extract test category from nodeid."""
        # nodeid format: tests/system/test_config_validation.py::TestClass::test_method
        parts = nodeid.split("::")
        if parts:
            filename = parts[0].split("/")[-1]
            # Remove test_ prefix and .py suffix
            category = filename.replace("test_", "").replace(".py", "")
            return category
        return "unknown"
    
    def _extract_test_name(self, nodeid: str) -> str:
        """Extract readable test name from nodeid."""
        parts = nodeid.split("::")
        if len(parts) >= 2:
            # Get class and method
            class_name = parts[-2] if len(parts) >= 3 else ""
            method_name = parts[-1]
            
            # Convert method name to readable format
            readable = method_name.replace("test_", "").replace("_", " ").title()
            return readable
        return nodeid
    
    def get_summary(self) -> Dict[str, int]:
        """Get test result summary."""
        passed = sum(1 for r in self.results if r["outcome"] == "passed")
        failed = sum(1 for r in self.results if r["outcome"] == "failed")
        skipped = sum(1 for r in self.results if r["outcome"] == "skipped")
        
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }


# Global collector instance
_collector = TestResultCollector()


def pytest_configure(config):
    """Called when pytest starts."""
    _collector.start_time = datetime.now()
    ensure_results_dir()


def pytest_runtest_logreport(report):
    """Called after each test phase."""
    if report.when == "call":  # Only record the actual test call
        _collector.add_result(
            nodeid=report.nodeid,
            outcome=report.outcome,
            duration=report.duration,
            message=str(report.longrepr) if report.longrepr else "",
        )


def pytest_sessionfinish(session, exitstatus):
    """Called after all tests complete."""
    _collector.end_time = datetime.now()
    
    # Generate and save formatted report
    report = generate_formatted_report(_collector)
    save_report(report)
    
    # Also print summary to console
    print_summary(_collector)


def generate_formatted_report(collector: TestResultCollector) -> str:
    """Generate a formatted test report."""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("IDEA DIGEST - TEST RESULTS REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Timestamp and duration
    lines.append(f"Run Date:     {collector.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if collector.end_time:
        duration = (collector.end_time - collector.start_time).total_seconds()
        lines.append(f"Duration:     {duration:.2f} seconds")
    lines.append("")
    
    # Summary
    summary = collector.get_summary()
    lines.append("-" * 40)
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total Tests:  {summary['total']}")
    lines.append(f"Passed:       {summary['passed']} ✓")
    lines.append(f"Failed:       {summary['failed']} ✗")
    lines.append(f"Skipped:      {summary['skipped']} ○")
    lines.append(f"Pass Rate:    {(summary['passed'] / max(summary['total'], 1) * 100):.1f}%")
    lines.append("")
    
    # Results by category
    lines.append("=" * 80)
    lines.append("RESULTS BY CATEGORY")
    lines.append("=" * 80)
    
    for category, results in sorted(collector.categories.items()):
        # Get category metadata
        cat_info = TEST_CATEGORIES.get(category, {
            "name": category.replace("_", " ").title(),
            "description": "Test category",
            "protects_against": [],
        })
        
        passed = sum(1 for r in results if r["outcome"] == "passed")
        failed = sum(1 for r in results if r["outcome"] == "failed")
        
        lines.append("")
        lines.append(f"┌{'─' * 78}┐")
        lines.append(f"│ {cat_info['name']:<76} │")
        lines.append(f"├{'─' * 78}┤")
        lines.append(f"│ {cat_info['description']:<76} │")
        lines.append(f"│ Tests: {passed} passed, {failed} failed{' ' * (58 - len(str(passed)) - len(str(failed)))} │")
        lines.append(f"└{'─' * 78}┘")
        
        # What this category protects against
        if cat_info.get("protects_against"):
            lines.append("  Protects Against:")
            for protection in cat_info["protects_against"]:
                lines.append(f"    • {protection}")
        
        lines.append("")
        lines.append("  Test Results:")
        
        for result in results:
            status = "✓" if result["outcome"] == "passed" else "✗" if result["outcome"] == "failed" else "○"
            duration_str = f"({result['duration']*1000:.0f}ms)"
            lines.append(f"    {status} {result['name']:<55} {duration_str:>10}")
            
            if result["outcome"] == "failed" and result["message"]:
                # Add failure message (truncated)
                msg_lines = result["message"].split("\n")[:3]
                for msg_line in msg_lines:
                    if msg_line.strip():
                        lines.append(f"      └─ {msg_line[:70]}")
        
        lines.append("")
    
    # Failed tests detail
    failed_tests = [r for r in collector.results if r["outcome"] == "failed"]
    if failed_tests:
        lines.append("=" * 80)
        lines.append("FAILED TESTS DETAIL")
        lines.append("=" * 80)
        
        for result in failed_tests:
            lines.append("")
            lines.append(f"FAILED: {result['nodeid']}")
            lines.append("-" * 40)
            if result["message"]:
                for line in result["message"].split("\n")[:10]:
                    lines.append(f"  {line}")
            lines.append("")
    
    # Footer
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def save_report(report: str):
    """Save report to timestamped file."""
    filename = get_result_filename()
    filepath = RESULTS_DIR / filename
    
    with open(filepath, "w") as f:
        f.write(report)
    
    print(f"\n📄 Test results saved to: {filepath}")


def print_summary(collector: TestResultCollector):
    """Print summary to console."""
    summary = collector.get_summary()
    
    print("\n" + "=" * 60)
    print("TEST RUN COMPLETE")
    print("=" * 60)
    print(f"Total: {summary['total']} | Passed: {summary['passed']} | Failed: {summary['failed']} | Skipped: {summary['skipped']}")
    print(f"Pass Rate: {(summary['passed'] / max(summary['total'], 1) * 100):.1f}%")
    print("=" * 60)


# =============================================================================
# SHARED FIXTURES
# =============================================================================

@pytest.fixture
def sample_item():
    """Provide a single sample IdeaItem data dict."""
    return get_sample_item(0)


@pytest.fixture
def sample_items():
    """Provide list of sample IdeaItem data dicts."""
    return get_all_sample_items()


@pytest.fixture
def test_config():
    """Provide access to test configuration."""
    return CONFIG


@pytest.fixture
def expected_values():
    """Provide access to expected values."""
    return EXPECTED


@pytest.fixture
def test_data():
    """Provide access to test data."""
    return TEST_DATA


@pytest.fixture
def workflow_config():
    """Provide access to workflow configuration."""
    return WORKFLOW


@pytest.fixture
def temp_output_dir(tmp_path):
    """Provide a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_storage():
    """Provide a mock storage instance."""
    from unittest.mock import Mock
    from src.storage.base import Storage, UpsertResult
    
    storage = Mock(spec=Storage)
    storage.name = "mock_storage"
    storage.upsert_items.return_value = UpsertResult(inserted=0, updated=0)
    storage.get_recent_items.return_value = []
    storage.get_top_items.return_value = []
    
    return storage


@pytest.fixture
def mock_source():
    """Provide a mock source instance."""
    from unittest.mock import Mock
    from src.sources.base import Source
    
    source = Mock(spec=Source)
    source.name = "mock_source"
    source.fetch_items.return_value = []
    
    return source


# =============================================================================
# MARKERS FOR TEST CATEGORIES
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "config_validation: Configuration validation tests"
    )
    config.addinivalue_line(
        "markers", "source_resilience: Source error isolation tests"
    )
    config.addinivalue_line(
        "markers", "pipeline_orchestration: Pipeline execution order tests"
    )
    config.addinivalue_line(
        "markers", "idempotency: Duplicate prevention tests"
    )
    config.addinivalue_line(
        "markers", "digest_correctness: Digest output validation tests"
    )
    config.addinivalue_line(
        "markers", "cli_behavior: CLI interface tests"
    )
    config.addinivalue_line(
        "markers", "automation_safety: GitHub Actions workflow tests"
    )
    config.addinivalue_line(
        "markers", "operational_sanity: End-to-end behavior tests"
    )
    
    # Initialize collector
    _collector.start_time = datetime.now()
    ensure_results_dir()

