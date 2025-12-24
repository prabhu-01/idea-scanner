"""
Base source abstraction for Idea Digest.

Defines the abstract interface that all data sources must implement.
"""

from abc import ABC, abstractmethod
from typing import List

from src.models.idea_item import IdeaItem


class Source(ABC):
    """
    Abstract base class for all idea sources.
    
    Each source (Product Hunt, Hacker News, GitHub, etc.) must implement
    this interface to be used in the pipeline.
    
    Attributes:
        name: Unique identifier for this source (e.g., "hackernews", "producthunt").
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the unique name identifier for this source.
        
        This name is used in IdeaItem.source_name and for logging.
        Should be lowercase, no spaces (e.g., "hackernews", "producthunt", "github").
        """
        pass
    
    @abstractmethod
    def fetch_items(self, limit: int | None = None) -> List[IdeaItem]:
        """
        Fetch items from this source and return as IdeaItem instances.
        
        Implementations should:
        - Respect the limit parameter (or use DEFAULT_LIMIT_PER_SOURCE if None)
        - Respect REQUEST_TIMEOUT from config
        - Gracefully skip items that cannot be normalized (missing required fields)
        - Return an empty list on complete failure (don't raise exceptions)
        
        Args:
            limit: Maximum number of items to fetch. If None, use config default.
            
        Returns:
            List of IdeaItem instances (may be empty if fetch fails).
        """
        pass
    
    def __str__(self) -> str:
        return f"Source({self.name})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

