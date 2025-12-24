"""
Test Configuration - Externalized Test Data

This file contains all configurable test data, expected values, and test parameters.
Update values here when requirements change - no need to modify test scripts.

Structure:
- CONFIG: General test configuration
- EXPECTED: Expected values for validation tests
- TEST_DATA: Test input data (mock items, sources, etc.)
- MESSAGES: Expected error messages and outputs
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


# =============================================================================
# GENERAL TEST CONFIGURATION
# =============================================================================

CONFIG = {
    # Environment settings for tests
    "environments": {
        "production": "production",
        "development": "development",
        "staging": "staging",
    },
    
    # Default test limits
    "default_limit_per_source": 3,
    "default_test_timeout": 30,
    
    # Directories
    "test_output_dir": "test_results",
    "digest_output_dir": "digests",
    
    # Sources available in the system
    "available_sources": ["hackernews", "producthunt", "github"],
    
    # Valid CLI since-days options
    "valid_since_days": ["daily", "weekly", "monthly"],
}


# =============================================================================
# EXPECTED VALUES FOR VALIDATION
# =============================================================================

EXPECTED = {
    # Configuration validation
    "config": {
        "default_limit_range": (1, 100),  # min, max for reasonable default
        "default_timeout_range": (5, 120),  # min, max seconds
        "default_scrape_delay_min": 0.0,
        
        # Required env vars in production
        "required_production_vars": [
            "AIRTABLE_API_KEY",
            "AIRTABLE_BASE_ID",
        ],
    },
    
    # Scoring expectations
    "scoring": {
        "score_range": (0.0, 1.0),
        "theme_weight_default": 1.0,
        "weight_themes": 0.4,
        "weight_recency": 0.3,
        "weight_popularity": 0.3,
    },
    
    # Digest expectations
    "digest": {
        "filename_pattern": r"\d{4}-\d{2}-\d{2}\.md$",  # YYYY-MM-DD.md
        "required_sections": ["Summary", "#"],  # Must have summary and headers
    },
    
    # CLI expectations
    "cli": {
        "exit_code_success": 0,
        "exit_code_failure": 1,
        "exit_code_argparse_error": 2,
    },
    
    # Pipeline expectations
    "pipeline": {
        "execution_order": ["fetch", "score", "store", "digest"],
    },
}


# =============================================================================
# TEST DATA - MOCK ITEMS AND SOURCES
# =============================================================================

TEST_DATA = {
    # Sample IdeaItem data for tests
    "sample_items": [
        {
            "id": "test_item_1",
            "title": "AI-Powered Code Assistant",
            "url": "https://example.com/ai-assistant",
            "source_name": "hackernews",
            "description": "A revolutionary AI tool for developers using GPT",
            "score": 0.85,
            "tags": ["ai-ml", "developer-tools"],
        },
        {
            "id": "test_item_2",
            "title": "New Python Framework",
            "url": "https://example.com/python-framework",
            "source_name": "github",
            "description": "A modern Python web framework with async support",
            "score": 0.72,
            "tags": ["programming", "developer-tools"],
        },
        {
            "id": "test_item_3",
            "title": "Productivity App Launch",
            "url": "https://example.com/productivity",
            "source_name": "producthunt",
            "description": "Simple task management for busy professionals",
            "score": 0.45,
            "tags": ["productivity"],
        },
    ],
    
    # Items for score ordering tests
    "score_ordered_items": [
        {"id": "high", "title": "High Score Item", "score": 0.95, "tags": ["ai-ml"]},
        {"id": "mid", "title": "Mid Score Item", "score": 0.60, "tags": ["ai-ml"]},
        {"id": "low", "title": "Low Score Item", "score": 0.25, "tags": ["ai-ml"]},
    ],
    
    # Items for theme grouping tests
    "theme_grouped_items": [
        {"id": "ai1", "title": "AI Tool 1", "score": 0.8, "tags": ["ai-ml"]},
        {"id": "ai2", "title": "AI Tool 2", "score": 0.7, "tags": ["ai-ml"]},
        {"id": "dev1", "title": "Dev Tool 1", "score": 0.75, "tags": ["developer-tools"]},
        {"id": "multi", "title": "AI Dev Tool", "score": 0.9, "tags": ["ai-ml", "developer-tools"]},
    ],
    
    # Items for idempotency tests
    "idempotency_items": [
        {"id": "idem_1", "title": "Item 1", "source_name": "test"},
        {"id": "idem_2", "title": "Item 2", "source_name": "test"},
        {"id": "idem_3", "title": "Item 3", "source_name": "test"},
    ],
    
    # Source configurations for mock sources
    "mock_sources": {
        "success_source": {
            "name": "mock_success",
            "items_count": 3,
            "should_fail": False,
        },
        "failing_source": {
            "name": "mock_failing",
            "error_type": "ConnectionError",
            "error_message": "Simulated network failure",
            "should_fail": True,
        },
    },
}


# =============================================================================
# ERROR MESSAGES - Expected messages for validation
# =============================================================================

MESSAGES = {
    # Configuration error messages (substrings to check)
    "config_errors": {
        "missing_api_key": "AIRTABLE_API_KEY",
        "missing_base_id": "AIRTABLE_BASE_ID",
        "invalid_limit": "LIMIT",
        "invalid_delay": "DELAY",
    },
    
    # CLI help text (substrings that should appear)
    "cli_help": {
        "dry_run": "--dry-run",
        "limit": "--limit-per-source",
        "sources": "--sources",
        "verbose": "--verbose",
    },
    
    # Pipeline summary (substrings)
    "pipeline_summary": {
        "header": "SUMMARY",
        "sources_label": "Sources",
        "duration_label": "Duration",
    },
}


# =============================================================================
# WORKFLOW CONFIGURATION - GitHub Actions validation
# =============================================================================

WORKFLOW = {
    "file_path": ".github/workflows/daily-digest.yml",
    
    # Required elements in workflow
    "required_elements": {
        "name": "name:",
        "trigger": "on:",
        "schedule": "schedule:",
        "cron": "cron:",
        "workflow_dispatch": "workflow_dispatch:",
        "jobs": "jobs:",
    },
    
    # Required secrets
    "required_secrets": [
        "AIRTABLE_API_KEY",
        "AIRTABLE_BASE_ID",
    ],
    
    # Required file references
    "required_files": [
        "main.py",
        "requirements.txt",
    ],
    
    # Cron expression validation
    "cron_fields_count": 5,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_sample_item(index: int = 0) -> dict:
    """Get a sample item by index."""
    items = TEST_DATA["sample_items"]
    return items[index % len(items)]


def get_all_sample_items() -> List[dict]:
    """Get all sample items."""
    return TEST_DATA["sample_items"].copy()


def get_expected_value(category: str, key: str) -> Any:
    """Get an expected value from the EXPECTED config."""
    return EXPECTED.get(category, {}).get(key)


def get_config_value(key: str) -> Any:
    """Get a general config value."""
    return CONFIG.get(key)


# =============================================================================
# TEST CATEGORIES METADATA
# =============================================================================

TEST_CATEGORIES = {
    "config_validation": {
        "name": "Configuration Validation",
        "description": "Validates environment configuration and error handling",
        "protects_against": [
            "Silent failures from missing configuration",
            "Cryptic stack traces instead of helpful errors",
            "Invalid configuration values being accepted",
        ],
    },
    "source_resilience": {
        "name": "Source Resilience",
        "description": "Validates error isolation between data sources",
        "protects_against": [
            "One failing source crashing the entire pipeline",
            "Silent swallowing of errors without reporting",
            "Incorrect success/failure counts",
        ],
    },
    "pipeline_orchestration": {
        "name": "Pipeline Orchestration",
        "description": "Validates execution order and dry-run behavior",
        "protects_against": [
            "Steps executing out of order",
            "Storage being called during dry-run",
            "Missing steps in the pipeline",
        ],
    },
    "idempotency": {
        "name": "Idempotency",
        "description": "Validates duplicate prevention and consistent results",
        "protects_against": [
            "Duplicate records in storage",
            "Incorrect insert vs update counts",
            "Data corruption from repeated runs",
        ],
    },
    "digest_correctness": {
        "name": "Digest Correctness",
        "description": "Validates digest output format and ordering",
        "protects_against": [
            "Incorrect theme grouping",
            "Wrong sort order within groups",
            "Non-deterministic output",
        ],
    },
    "cli_behavior": {
        "name": "CLI Behavior",
        "description": "Validates command-line interface correctness",
        "protects_against": [
            "CLI flags not being honored",
            "Invalid arguments causing crashes",
            "Missing help documentation",
        ],
    },
    "automation_safety": {
        "name": "Automation Safety",
        "description": "Validates GitHub Actions workflow configuration",
        "protects_against": [
            "Workflow referencing non-existent files",
            "Missing secret documentation",
            "Invalid cron expressions",
        ],
    },
    "operational_sanity": {
        "name": "Operational Sanity",
        "description": "Validates end-to-end system behavior",
        "protects_against": [
            "Unexpected filesystem writes",
            "Missing or incorrect output",
            "Silent failures without proper exit codes",
        ],
    },
}

