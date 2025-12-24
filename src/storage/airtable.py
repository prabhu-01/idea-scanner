"""
Airtable storage backend for Idea Digest.

Implements the Storage interface using Airtable as the persistence layer.
Uses the Airtable REST API for all operations.

Airtable API Documentation: https://airtable.com/developers/web/api/introduction

=============================================================================
AIRTABLE SCHEMA
=============================================================================

Required table columns (create these in Airtable):

| Column Name    | Field Type      | Description                          |
|----------------|-----------------|--------------------------------------|
| unique_key     | Single line text| Primary dedup key (e.g., "hn_12345") |
| title          | Single line text| Item title                           |
| description    | Long text       | Item description                     |
| url            | URL             | Link to original source              |
| source_name    | Single line text| Source identifier (e.g., "hackernews")|
| source_date    | Date            | When posted on source (ISO format)   |
| score          | Number          | Interest score (0.0 to 1.0)          |
| tags           | Multiple select | Theme tags                           |
| created_at     | Date            | When we first saw this item          |
| updated_at     | Date            | When we last updated this item       |
| item_id        | Single line text| Original ID from IdeaItem            |

Note: "unique_key" is used for deduplication. It should be the IdeaItem.id
which is already formatted as "source_itemid" (e.g., "hn_12345").

=============================================================================
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import requests

from src.config import (
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
    REQUEST_TIMEOUT,
)
from src.models.idea_item import IdeaItem
from src.storage.base import Storage, UpsertResult


class AirtableStorage(Storage):
    """
    Airtable-backed storage implementation.
    
    Uses Airtable REST API for persistence. Implements idempotent upserts
    by checking for existing records with matching unique_key before inserting.
    
    Configuration is pulled from environment variables via src.config:
    - AIRTABLE_API_KEY: API key for authentication
    - AIRTABLE_BASE_ID: Base ID (starts with "app")
    - AIRTABLE_TABLE_NAME: Name of the table to use
    """
    
    # Airtable API base URL
    API_BASE = "https://api.airtable.com/v0"
    
    # Rate limiting: Airtable allows 5 requests per second
    REQUEST_DELAY = 0.25  # 250ms between requests to stay under limit
    
    def __init__(
        self,
        api_key: str = None,
        base_id: str = None,
        table_name: str = None,
    ):
        """
        Initialize AirtableStorage.
        
        Args:
            api_key: Airtable API key. Defaults to config.AIRTABLE_API_KEY.
            base_id: Airtable base ID. Defaults to config.AIRTABLE_BASE_ID.
            table_name: Table name. Defaults to config.AIRTABLE_TABLE_NAME.
        """
        # Use provided values, or fall back to config if None (not empty string)
        self.api_key = api_key if api_key is not None else AIRTABLE_API_KEY
        self.base_id = base_id if base_id is not None else AIRTABLE_BASE_ID
        self.table_name = table_name if table_name is not None else AIRTABLE_TABLE_NAME
        
        self._last_request_time = 0.0
    
    @property
    def name(self) -> str:
        return "airtable"
    
    @property
    def _base_url(self) -> str:
        """Construct the base URL for API requests."""
        return f"{self.API_BASE}/{self.base_id}/{self.table_name}"
    
    @property
    def _headers(self) -> Dict[str, str]:
        """Construct headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def _validate_config(self) -> None:
        """Validate that required configuration is present."""
        if not self.api_key:
            raise ValueError("AIRTABLE_API_KEY is not configured")
        if not self.base_id:
            raise ValueError("AIRTABLE_BASE_ID is not configured")
        if not self.table_name:
            raise ValueError("AIRTABLE_TABLE_NAME is not configured")
    
    # =========================================================================
    # Serialization: IdeaItem <-> Airtable
    # =========================================================================
    
    @staticmethod
    def item_to_airtable_fields(item: IdeaItem) -> Dict[str, Any]:
        """
        Convert an IdeaItem to Airtable field format.
        
        Args:
            item: The IdeaItem to convert.
            
        Returns:
            Dictionary of field names to values for Airtable.
        """
        fields = {
            "unique_key": item.id,  # Using IdeaItem.id as the unique key
            "item_id": item.id,
            "title": item.title,
            "url": item.url,
            "source_name": item.source_name,
            "score": item.score,
        }
        
        # Optional fields - only include if present
        if item.description:
            fields["description"] = item.description
        
        if item.source_date:
            fields["source_date"] = item.source_date.isoformat()
        
        if item.tags:
            # Airtable multiple select expects list of strings
            fields["tags"] = item.tags
        
        if item.created_at:
            fields["created_at"] = item.created_at.isoformat()
        
        if item.updated_at:
            fields["updated_at"] = item.updated_at.isoformat()
        
        return fields
    
    @staticmethod
    def airtable_record_to_item(record: Dict[str, Any]) -> Optional[IdeaItem]:
        """
        Convert an Airtable record to an IdeaItem.
        
        Args:
            record: Airtable record with "id" and "fields".
            
        Returns:
            IdeaItem if conversion successful, None otherwise.
        """
        try:
            fields = record.get("fields", {})
            
            # Required fields
            title = fields.get("title")
            url = fields.get("url")
            source_name = fields.get("source_name")
            
            if not all([title, url, source_name]):
                return None
            
            # Parse optional datetime fields
            source_date = None
            if fields.get("source_date"):
                try:
                    source_date = datetime.fromisoformat(
                        fields["source_date"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            
            created_at = datetime.now()
            if fields.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(
                        fields["created_at"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            
            updated_at = datetime.now()
            if fields.get("updated_at"):
                try:
                    updated_at = datetime.fromisoformat(
                        fields["updated_at"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            
            return IdeaItem(
                id=fields.get("item_id", fields.get("unique_key", "")),
                title=title,
                description=fields.get("description", ""),
                url=url,
                source_name=source_name,
                source_date=source_date,
                score=float(fields.get("score", 0.0)),
                tags=fields.get("tags", []),
                created_at=created_at,
                updated_at=updated_at,
            )
        except Exception:
            return None
    
    # =========================================================================
    # API Operations
    # =========================================================================
    
    def _find_by_unique_key(self, unique_key: str) -> Optional[Tuple[str, Dict]]:
        """
        Find an existing record by unique_key.
        
        Args:
            unique_key: The unique_key to search for.
            
        Returns:
            Tuple of (record_id, fields) if found, None otherwise.
        """
        self._rate_limit()
        
        try:
            # Use filterByFormula to find exact match
            params = {
                "filterByFormula": f"{{unique_key}}='{unique_key}'",
                "maxRecords": 1,
            }
            
            response = requests.get(
                self._base_url,
                headers=self._headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            data = response.json()
            records = data.get("records", [])
            
            if records:
                record = records[0]
                return (record["id"], record.get("fields", {}))
            
            return None
            
        except Exception:
            return None
    
    def _create_record(self, item: IdeaItem) -> Tuple[bool, str]:
        """
        Create a new record in Airtable.
        
        Args:
            item: The IdeaItem to create.
            
        Returns:
            Tuple of (success, error_message).
        """
        self._rate_limit()
        
        try:
            payload = {
                "fields": self.item_to_airtable_fields(item),
            }
            
            response = requests.post(
                self._base_url,
                headers=self._headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return (True, "")
            
        except Exception as e:
            return (False, str(e))
    
    def _update_record(self, record_id: str, item: IdeaItem) -> Tuple[bool, str]:
        """
        Update an existing record in Airtable.
        
        Args:
            record_id: The Airtable record ID to update.
            item: The IdeaItem with new values.
            
        Returns:
            Tuple of (success, error_message).
        """
        self._rate_limit()
        
        try:
            url = f"{self._base_url}/{record_id}"
            payload = {
                "fields": self.item_to_airtable_fields(item),
            }
            
            response = requests.patch(
                url,
                headers=self._headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return (True, "")
            
        except Exception as e:
            return (False, str(e))
    
    def _list_records(
        self,
        filter_formula: str = None,
        sort_field: str = None,
        sort_direction: str = "desc",
        max_records: int = 100,
    ) -> List[Dict]:
        """
        List records from Airtable with optional filtering and sorting.
        
        Args:
            filter_formula: Airtable formula for filtering.
            sort_field: Field name to sort by.
            sort_direction: "asc" or "desc".
            max_records: Maximum number of records to return.
            
        Returns:
            List of Airtable record dicts.
        """
        self._rate_limit()
        
        try:
            params = {"maxRecords": max_records}
            
            if filter_formula:
                params["filterByFormula"] = filter_formula
            
            if sort_field:
                params["sort[0][field]"] = sort_field
                params["sort[0][direction]"] = sort_direction
            
            response = requests.get(
                self._base_url,
                headers=self._headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("records", [])
            
        except Exception:
            return []
    
    # =========================================================================
    # Storage Interface Implementation
    # =========================================================================
    
    def upsert_items(self, items: List[IdeaItem]) -> UpsertResult:
        """
        Insert or update items in Airtable.
        
        For each item:
        1. Check if record with same unique_key exists
        2. If exists: update the record
        3. If not: create new record
        
        This ensures idempotent behavior - running multiple times
        with the same data won't create duplicates.
        
        Args:
            items: List of IdeaItem instances to store.
            
        Returns:
            UpsertResult with counts of inserted/updated/failed.
        """
        self._validate_config()
        
        result = UpsertResult()
        
        for item in items:
            try:
                # Look for existing record
                existing = self._find_by_unique_key(item.id)
                
                if existing:
                    # Update existing record
                    record_id, _ = existing
                    success, error = self._update_record(record_id, item)
                    
                    if success:
                        result.updated += 1
                    else:
                        result.failed += 1
                        result.errors.append(f"Update failed for {item.id}: {error}")
                else:
                    # Create new record
                    success, error = self._create_record(item)
                    
                    if success:
                        result.inserted += 1
                    else:
                        result.failed += 1
                        result.errors.append(f"Insert failed for {item.id}: {error}")
                        
            except Exception as e:
                result.failed += 1
                result.errors.append(f"Error processing {item.id}: {str(e)}")
        
        return result
    
    def get_recent_items(self, days: int = 7) -> List[IdeaItem]:
        """
        Retrieve items from the last N days.
        
        Args:
            days: Number of days to look back.
            
        Returns:
            List of IdeaItem instances.
        """
        self._validate_config()
        
        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        # Airtable filter formula for date comparison
        filter_formula = f"IS_AFTER({{created_at}}, '{cutoff_str}')"
        
        records = self._list_records(
            filter_formula=filter_formula,
            sort_field="created_at",
            sort_direction="desc",
        )
        
        items = []
        for record in records:
            item = self.airtable_record_to_item(record)
            if item:
                items.append(item)
        
        return items
    
    def get_top_items(
        self,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[IdeaItem]:
        """
        Retrieve top-scoring items.
        
        Args:
            limit: Maximum number of items to return.
            min_score: Minimum score threshold.
            
        Returns:
            List of IdeaItem instances sorted by score.
        """
        self._validate_config()
        
        # Airtable filter formula for minimum score
        filter_formula = f"{{score}} >= {min_score}" if min_score > 0 else None
        
        records = self._list_records(
            filter_formula=filter_formula,
            sort_field="score",
            sort_direction="desc",
            max_records=limit,
        )
        
        items = []
        for record in records:
            item = self.airtable_record_to_item(record)
            if item:
                items.append(item)
        
        return items
    
    def get_item_by_key(self, unique_key: str) -> Optional[IdeaItem]:
        """
        Retrieve a single item by its unique key.
        
        Args:
            unique_key: The unique identifier (e.g., "hn_12345").
            
        Returns:
            IdeaItem if found, None otherwise.
        """
        self._validate_config()
        
        existing = self._find_by_unique_key(unique_key)
        if existing:
            record_id, fields = existing
            record = {"id": record_id, "fields": fields}
            return self.airtable_record_to_item(record)
        
        return None


class MockAirtableStorage(Storage):
    """
    In-memory mock storage for testing and development.
    
    Use this when Airtable is not configured or for testing.
    Data is stored in memory and lost when the process ends.
    """
    
    def __init__(self):
        self._records: Dict[str, IdeaItem] = {}
    
    @property
    def name(self) -> str:
        return "mock"
    
    def upsert_items(self, items: List[IdeaItem]) -> UpsertResult:
        """Store items in memory with idempotent behavior."""
        result = UpsertResult()
        
        for item in items:
            if item.id in self._records:
                result.updated += 1
            else:
                result.inserted += 1
            
            self._records[item.id] = item
        
        return result
    
    def get_recent_items(self, days: int = 7) -> List[IdeaItem]:
        """Get items from the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        items = [
            item for item in self._records.values()
            if item.created_at >= cutoff
        ]
        return sorted(items, key=lambda x: x.created_at, reverse=True)
    
    def get_top_items(
        self,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[IdeaItem]:
        """Get top-scoring items."""
        items = [
            item for item in self._records.values()
            if item.score >= min_score
        ]
        items.sort(key=lambda x: x.score, reverse=True)
        return items[:limit]
    
    def get_item_by_key(self, unique_key: str) -> Optional[IdeaItem]:
        """Get a single item by key."""
        return self._records.get(unique_key)
    
    def clear(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()
    
    def count(self) -> int:
        """Return number of stored records (for testing)."""
        return len(self._records)

