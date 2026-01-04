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
        
        # Airtable date fields expect YYYY-MM-DD format (not full ISO timestamp)
        if item.source_date:
            fields["source_date"] = item.source_date.strftime("%Y-%m-%d")
        
        if item.tags:
            # Airtable multiple select expects list of strings
            fields["tags"] = item.tags
        
        if item.created_at:
            fields["created_at"] = item.created_at.strftime("%Y-%m-%d")
        
        if item.updated_at:
            fields["updated_at"] = item.updated_at.strftime("%Y-%m-%d")
        
        # Platform-specific metrics (store as numbers in Airtable)
        if item.points is not None:
            fields["points"] = item.points
        if item.comments_count is not None:
            fields["comments_count"] = item.comments_count
        if item.votes is not None:
            fields["votes"] = item.votes
        if item.stars is not None:
            fields["stars"] = item.stars
        if item.stars_today is not None:
            fields["stars_today"] = item.stars_today
        if item.language:
            fields["language"] = item.language
        
        # Maker/creator information
        if item.maker_name:
            fields["maker_name"] = item.maker_name
        if item.maker_username:
            fields["maker_username"] = item.maker_username
        if item.maker_url:
            fields["maker_url"] = item.maker_url
        if item.maker_avatar:
            fields["maker_avatar"] = item.maker_avatar
        if item.maker_bio:
            fields["maker_bio"] = item.maker_bio
        if item.maker_twitter:
            fields["maker_twitter"] = item.maker_twitter
        
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
                # Platform-specific metrics
                points=fields.get("points"),
                comments_count=fields.get("comments_count"),
                votes=fields.get("votes"),
                stars=fields.get("stars"),
                stars_today=fields.get("stars_today"),
                language=fields.get("language"),
                # Maker/creator information
                maker_name=fields.get("maker_name"),
                maker_username=fields.get("maker_username"),
                maker_url=fields.get("maker_url"),
                maker_avatar=fields.get("maker_avatar"),
                maker_bio=fields.get("maker_bio"),
                maker_twitter=fields.get("maker_twitter"),
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
        max_records: int = 500,
    ) -> List[Dict]:
        """
        List records from Airtable with optional filtering and sorting.
        
        Handles pagination automatically to fetch all matching records
        up to max_records limit.
        
        Args:
            filter_formula: Airtable formula for filtering.
            sort_field: Field name to sort by.
            sort_direction: "asc" or "desc".
            max_records: Maximum number of records to return.
            
        Returns:
            List of Airtable record dicts.
        """
        all_records = []
        offset = None
        
        try:
            while len(all_records) < max_records:
                self._rate_limit()
                
                # Airtable returns max 100 per page
                page_size = min(100, max_records - len(all_records))
                params = {"pageSize": page_size}
                
                if filter_formula:
                    params["filterByFormula"] = filter_formula
                
                if sort_field:
                    params["sort[0][field]"] = sort_field
                    params["sort[0][direction]"] = sort_direction
                
                if offset:
                    params["offset"] = offset
                
                response = requests.get(
                    self._base_url,
                    headers=self._headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                
                data = response.json()
                records = data.get("records", [])
                all_records.extend(records)
                
                # Check if there are more pages
                offset = data.get("offset")
                if not offset or not records:
                    break
            
            return all_records
            
        except Exception:
            return all_records  # Return what we have so far
    
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
    
    def search_items(
        self,
        query: str,
        limit: int = 50,
        source_filter: Optional[str] = None,
    ) -> List[IdeaItem]:
        """
        Search for items matching a text query.
        
        Searches across title and description fields using Airtable's
        SEARCH function. Results are sorted by score descending.
        
        Args:
            query: Search query string.
            limit: Maximum number of results (default 50).
            source_filter: Optional source name to filter by.
            
        Returns:
            List of matching IdeaItem instances.
        """
        self._validate_config()
        
        if not query or not query.strip():
            return []
        
        # Sanitize query for Airtable formula (escape quotes)
        sanitized_query = query.strip().replace('"', '\\"').replace("'", "\\'")
        
        # Build Airtable filter formula using SEARCH
        # SEARCH returns position (1-indexed) or 0 if not found
        # We search in both title and description (case-insensitive via LOWER)
        search_conditions = [
            f'SEARCH(LOWER("{sanitized_query}"), LOWER({{title}})) > 0',
            f'SEARCH(LOWER("{sanitized_query}"), LOWER({{description}})) > 0',
        ]
        
        filter_formula = f"OR({', '.join(search_conditions)})"
        
        # Add source filter if specified
        if source_filter:
            filter_formula = f"AND({filter_formula}, {{source_name}} = '{source_filter}')"
        
        try:
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
            
        except Exception as e:
            print(f"[{self.name}] Search error: {e}")
            return []
    
    # =========================================================================
    # Free Tier Management - Stay Under 1,200 Records
    # =========================================================================
    
    def get_record_count(self) -> int:
        """
        Get the total number of records in the table.
        
        Returns:
            Total record count.
        """
        self._validate_config()
        
        try:
            # Airtable doesn't have a direct count endpoint, 
            # so we fetch minimal data and count
            count = 0
            offset = None
            
            while True:
                self._rate_limit()
                
                params = {
                    "pageSize": 100,
                    "fields[]": "unique_key",  # Minimal field to reduce payload
                }
                if offset:
                    params["offset"] = offset
                
                response = requests.get(
                    self._base_url,
                    headers=self._headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                
                count += len(data.get("records", []))
                offset = data.get("offset")
                
                if not offset:
                    break
            
            return count
            
        except Exception as e:
            print(f"[airtable] Error getting record count: {e}")
            return -1
    
    def delete_records_older_than(self, days: int) -> Dict[str, int]:
        """
        Delete records older than specified days (rolling window cleanup).
        
        This helps stay under Airtable's free tier limit of 1,200 records.
        
        Args:
            days: Delete records older than this many days.
            
        Returns:
            Dict with 'deleted' and 'failed' counts.
        """
        self._validate_config()
        
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        # Find old records
        filter_formula = f"IS_BEFORE({{created_at}}, '{cutoff_str}')"
        
        deleted = 0
        failed = 0
        
        try:
            # Airtable allows batch delete of up to 10 records at a time
            while True:
                self._rate_limit()
                
                # Get batch of old records
                params = {
                    "filterByFormula": filter_formula,
                    "pageSize": 10,
                    "fields[]": "unique_key",
                }
                
                response = requests.get(
                    self._base_url,
                    headers=self._headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                
                records = response.json().get("records", [])
                if not records:
                    break
                
                # Delete this batch
                record_ids = [r["id"] for r in records]
                delete_result = self._delete_records_batch(record_ids)
                
                deleted += delete_result["deleted"]
                failed += delete_result["failed"]
                
                if delete_result["failed"] > 0:
                    break  # Stop on errors
                    
        except Exception as e:
            print(f"[airtable] Error during cleanup: {e}")
        
        return {"deleted": deleted, "failed": failed}
    
    def _delete_records_batch(self, record_ids: List[str]) -> Dict[str, int]:
        """
        Delete a batch of records by their Airtable record IDs.
        
        Args:
            record_ids: List of Airtable record IDs (max 10).
            
        Returns:
            Dict with 'deleted' and 'failed' counts.
        """
        if not record_ids:
            return {"deleted": 0, "failed": 0}
        
        self._rate_limit()
        
        try:
            # Airtable batch delete uses query params: records[]=id1&records[]=id2
            params = {"records[]": record_ids}
            
            response = requests.delete(
                self._base_url,
                headers=self._headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            result = response.json()
            deleted_count = len(result.get("records", []))
            
            return {"deleted": deleted_count, "failed": len(record_ids) - deleted_count}
            
        except Exception as e:
            print(f"[airtable] Error deleting batch: {e}")
            return {"deleted": 0, "failed": len(record_ids)}
    
    def cleanup_for_free_tier(
        self,
        max_records: int = 1000,
        retention_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Smart cleanup to stay under Airtable free tier limits.
        
        Strategy:
        1. Check current record count
        2. If under max_records, do nothing
        3. If over, delete oldest records beyond retention_days
        4. If still over, delete lowest-scoring old records
        
        Args:
            max_records: Target maximum records (default: 1000, leaves 200 buffer)
            retention_days: Minimum days to keep records (default: 30)
            
        Returns:
            Dict with cleanup statistics.
        """
        self._validate_config()
        
        result = {
            "initial_count": 0,
            "final_count": 0,
            "deleted": 0,
            "failed": 0,
            "action": "none",
        }
        
        # Step 1: Check current count
        current_count = self.get_record_count()
        if current_count < 0:
            result["action"] = "error_counting"
            return result
        
        result["initial_count"] = current_count
        
        # Step 2: If under limit, no action needed
        if current_count <= max_records:
            result["final_count"] = current_count
            result["action"] = "none_needed"
            print(f"[airtable] Record count ({current_count}) is under limit ({max_records}). No cleanup needed.")
            return result
        
        # Step 3: Delete old records
        print(f"[airtable] Record count ({current_count}) exceeds limit ({max_records}). Starting cleanup...")
        
        cleanup_result = self.delete_records_older_than(retention_days)
        result["deleted"] = cleanup_result["deleted"]
        result["failed"] = cleanup_result["failed"]
        result["action"] = "deleted_old_records"
        
        # Step 4: Verify final count
        final_count = self.get_record_count()
        result["final_count"] = final_count if final_count >= 0 else current_count - result["deleted"]
        
        print(f"[airtable] Cleanup complete. Deleted {result['deleted']} records. New count: {result['final_count']}")
        
        return result


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
    
    def get_record_count(self) -> int:
        """Get total record count."""
        return len(self._records)
    
    def delete_records_older_than(self, days: int) -> Dict[str, int]:
        """Delete records older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        to_delete = [
            key for key, item in self._records.items()
            if item.created_at < cutoff
        ]
        for key in to_delete:
            del self._records[key]
        return {"deleted": len(to_delete), "failed": 0}
    
    def cleanup_for_free_tier(
        self,
        max_records: int = 1000,
        retention_days: int = 30,
    ) -> Dict[str, Any]:
        """Mock cleanup for testing."""
        initial = len(self._records)
        if initial <= max_records:
            return {
                "initial_count": initial,
                "final_count": initial,
                "deleted": 0,
                "failed": 0,
                "action": "none_needed",
            }
        
        result = self.delete_records_older_than(retention_days)
        return {
            "initial_count": initial,
            "final_count": len(self._records),
            "deleted": result["deleted"],
            "failed": 0,
            "action": "deleted_old_records",
        }

