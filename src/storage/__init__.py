"""
Storage module.

Handles persistence and retrieval of ideas via Airtable or other backends.
"""

from src.storage.base import Storage, UpsertResult
from src.storage.airtable import AirtableStorage, MockAirtableStorage

__all__ = [
    "Storage",
    "UpsertResult",
    "AirtableStorage",
    "MockAirtableStorage",
]


