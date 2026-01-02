"""
Base storage abstraction for Idea Digest.

Defines the abstract interface that all storage backends must implement.
This allows swapping between Airtable, SQLite, PostgreSQL, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from src.models.idea_item import IdeaItem


@dataclass
class UpsertResult:
    """
    Result of an upsert operation.
    
    Attributes:
        inserted: Number of new records created.
        updated: Number of existing records updated.
        failed: Number of records that failed to save.
        errors: List of error messages for failed records.
    """
    inserted: int = 0
    updated: int = 0
    failed: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def total_processed(self) -> int:
        """Total number of successfully processed records."""
        return self.inserted + self.updated
    
    def __str__(self) -> str:
        return f"UpsertResult(inserted={self.inserted}, updated={self.updated}, failed={self.failed})"


class Storage(ABC):
    """
    Abstract base class for all storage backends.
    
    Implementations must provide methods for:
    - Upserting items (insert or update based on unique key)
    - Retrieving recent items
    - Retrieving top-scoring items
    
    All implementations should be idempotent: running the same
    operation multiple times should not create duplicates.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the name of this storage backend.
        
        Used for logging and debugging.
        """
        pass
    
    @abstractmethod
    def upsert_items(self, items: List[IdeaItem]) -> UpsertResult:
        """
        Insert or update items in storage.
        
        This operation must be idempotent: if an item with the same
        unique key already exists, it should be updated rather than
        creating a duplicate.
        
        The unique key is typically: source_name + id (e.g., "hn_12345")
        
        Args:
            items: List of IdeaItem instances to store.
            
        Returns:
            UpsertResult with counts of inserted/updated/failed records.
        """
        pass
    
    @abstractmethod
    def get_recent_items(self, days: int = 7) -> List[IdeaItem]:
        """
        Retrieve items from the last N days.
        
        Args:
            days: Number of days to look back (default 7).
            
        Returns:
            List of IdeaItem instances, sorted by created_at descending.
        """
        pass
    
    @abstractmethod
    def get_top_items(
        self,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[IdeaItem]:
        """
        Retrieve top-scoring items.
        
        Args:
            limit: Maximum number of items to return (default 10).
            min_score: Minimum score threshold (default 0.0).
            
        Returns:
            List of IdeaItem instances, sorted by score descending.
        """
        pass
    
    def get_item_by_key(self, unique_key: str) -> Optional[IdeaItem]:
        """
        Retrieve a single item by its unique key.
        
        Default implementation returns None. Override for backends
        that support efficient single-item lookup.
        
        Args:
            unique_key: The unique identifier (e.g., "hn_12345").
            
        Returns:
            IdeaItem if found, None otherwise.
        """
        return None
    
    def search_items(
        self,
        query: str,
        limit: int = 50,
        source_filter: Optional[str] = None,
    ) -> List[IdeaItem]:
        """
        Search for items matching a text query.
        
        Searches across title and description fields. Results are
        sorted by relevance (score) descending.
        
        Default implementation returns empty list. Override for backends
        that support text search.
        
        Args:
            query: Search query string.
            limit: Maximum number of results (default 50).
            source_filter: Optional source name to filter by.
            
        Returns:
            List of matching IdeaItem instances.
        """
        return []
    
    def __str__(self) -> str:
        return f"Storage({self.name})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

