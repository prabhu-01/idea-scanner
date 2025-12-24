"""
Configuration module for Idea Digest.

Loads environment variables from .env file and exposes them as typed configuration values.
Uses python-dotenv for loading and provides safe defaults where appropriate.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
# The .env file should be in the root directory (parent of src/)
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path)


# =============================================================================
# Application Environment
# =============================================================================

# Application environment: "development", "staging", or "production"
# Default: "development" for safe local testing
APP_ENV: str = os.getenv("APP_ENV", "development")

# Enable debug mode for verbose logging (only in development)
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


# =============================================================================
# Airtable Configuration
# =============================================================================

# Airtable API key for authentication
# Required for production; empty string as default for development
AIRTABLE_API_KEY: str = os.getenv("AIRTABLE_API_KEY", "")

# Airtable base ID where ideas are stored
# Required for production; empty string as default for development
AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")

# Airtable table name for storing ideas
AIRTABLE_TABLE_NAME: str = os.getenv("AIRTABLE_TABLE_NAME", "Ideas")


# =============================================================================
# Data Fetching Configuration
# =============================================================================

# Maximum number of items to fetch per source in a single run
# Default: 20 items - reasonable for daily digest without overwhelming
DEFAULT_LIMIT_PER_SOURCE: int = int(os.getenv("DEFAULT_LIMIT_PER_SOURCE", "20"))

# HTTP request timeout in seconds
# Default: 30 seconds - generous timeout for slow APIs
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Delay between scraping requests in seconds (to be respectful to servers)
# Default: 2 seconds - polite delay to avoid rate limiting
SCRAPE_DELAY: float = float(os.getenv("SCRAPE_DELAY", "2.0"))


# =============================================================================
# Source-Specific API Keys (Optional)
# =============================================================================

# Product Hunt API token (if using authenticated API)
PRODUCT_HUNT_TOKEN: str = os.getenv("PRODUCT_HUNT_TOKEN", "")

# GitHub personal access token (for higher rate limits)
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")


# =============================================================================
# Helper Functions
# =============================================================================

def is_production() -> bool:
    """Check if running in production environment."""
    return APP_ENV == "production"


def is_development() -> bool:
    """Check if running in development environment."""
    return APP_ENV == "development"


def validate_config() -> list[str]:
    """
    Validate that required configuration is present for production.
    
    Returns:
        List of missing or invalid configuration keys (empty if all valid).
    """
    errors = []
    
    if is_production():
        if not AIRTABLE_API_KEY:
            errors.append("AIRTABLE_API_KEY is required in production")
        if not AIRTABLE_BASE_ID:
            errors.append("AIRTABLE_BASE_ID is required in production")
    
    if DEFAULT_LIMIT_PER_SOURCE < 1:
        errors.append("DEFAULT_LIMIT_PER_SOURCE must be at least 1")
    
    if REQUEST_TIMEOUT < 1:
        errors.append("REQUEST_TIMEOUT must be at least 1 second")
    
    if SCRAPE_DELAY < 0:
        errors.append("SCRAPE_DELAY cannot be negative")
    
    return errors


def print_config_summary() -> None:
    """Print a summary of current configuration (safe for logs, no secrets)."""
    print(f"  APP_ENV: {APP_ENV}")
    print(f"  DEBUG: {DEBUG}")
    print(f"  AIRTABLE_API_KEY: {'***' if AIRTABLE_API_KEY else '(not set)'}")
    print(f"  AIRTABLE_BASE_ID: {'***' if AIRTABLE_BASE_ID else '(not set)'}")
    print(f"  AIRTABLE_TABLE_NAME: {AIRTABLE_TABLE_NAME}")
    print(f"  DEFAULT_LIMIT_PER_SOURCE: {DEFAULT_LIMIT_PER_SOURCE}")
    print(f"  REQUEST_TIMEOUT: {REQUEST_TIMEOUT}s")
    print(f"  SCRAPE_DELAY: {SCRAPE_DELAY}s")

