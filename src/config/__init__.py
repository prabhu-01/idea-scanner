"""
Configuration module.

Handles environment variables, API keys, and application settings.
"""

from src.config.config import (
    APP_ENV,
    DEBUG,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    DEFAULT_LIMIT_PER_SOURCE,
    REQUEST_TIMEOUT,
    SCRAPE_DELAY,
    PRODUCT_HUNT_TOKEN,
    GITHUB_TOKEN,
    GROQ_API_KEY,
    GROQ_MODEL,
    AIRTABLE_MAX_RECORDS,
    AIRTABLE_RETENTION_DAYS,
    AIRTABLE_AUTO_CLEANUP,
    is_production,
    is_development,
    validate_config,
    print_config_summary,
)

__all__ = [
    "APP_ENV",
    "DEBUG",
    "AIRTABLE_API_KEY",
    "AIRTABLE_BASE_ID",
    "AIRTABLE_TABLE_NAME",
    "DEFAULT_LIMIT_PER_SOURCE",
    "REQUEST_TIMEOUT",
    "SCRAPE_DELAY",
    "PRODUCT_HUNT_TOKEN",
    "GITHUB_TOKEN",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "AIRTABLE_MAX_RECORDS",
    "AIRTABLE_RETENTION_DAYS",
    "AIRTABLE_AUTO_CLEANUP",
    "is_production",
    "is_development",
    "validate_config",
    "print_config_summary",
]


