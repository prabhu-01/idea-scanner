"""
Core data model for Idea Digest.

Defines the IdeaItem dataclass representing a single idea/product/project
discovered from any source (Product Hunt, Hacker News, GitHub, etc.).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class IdeaItem:
    """
    Represents a single idea or product discovered from a source.
    
    This is the core data structure that flows through the entire pipeline:
    sources -> scoring -> storage -> digest.
    
    Attributes:
        id: Unique identifier for this item (UUID string).
        title: The name/title of the idea or product.
        description: Brief description or tagline.
        url: Link to the original source.
        source_name: Which platform this came from (e.g., "producthunt", "hackernews", "github").
        source_date: When this was posted/created on the source platform.
        score: Relevance/interest score assigned by scoring module (0.0 to 1.0).
        tags: List of category/topic tags.
        created_at: When this record was created in our system.
        updated_at: When this record was last updated.
    """
    
    # Required fields
    title: str
    url: str
    source_name: str
    
    # Optional fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    source_date: Optional[datetime] = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Platform-specific metrics (native engagement signals)
    # These store raw values from each platform for display purposes
    points: Optional[int] = None          # HN: points/upvotes
    comments_count: Optional[int] = None  # HN/PH: comment count
    votes: Optional[int] = None           # PH: upvote count
    stars: Optional[int] = None           # GitHub: total stars
    stars_today: Optional[int] = None     # GitHub: stars gained today/this week
    language: Optional[str] = None        # GitHub: programming language
    
    # Maker/Creator information
    maker_name: Optional[str] = None      # Name of creator/maker
    maker_username: Optional[str] = None  # Username on the platform
    maker_url: Optional[str] = None       # Profile URL
    maker_avatar: Optional[str] = None    # Avatar/profile image URL
    maker_bio: Optional[str] = None       # Short bio/headline
    maker_twitter: Optional[str] = None   # Twitter handle (if available)
    forks: Optional[int] = None           # GitHub: fork count
    watchers: Optional[int] = None        # GitHub: watcher count
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate that required fields are present and valid.
        
        Raises:
            ValueError: If validation fails.
        """
        errors = []
        
        # Required fields cannot be empty
        if not self.title or not self.title.strip():
            errors.append("title is required and cannot be empty")
        
        if not self.url or not self.url.strip():
            errors.append("url is required and cannot be empty")
        
        if not self.source_name or not self.source_name.strip():
            errors.append("source_name is required and cannot be empty")
        
        # Score must be in valid range
        if not (0.0 <= self.score <= 1.0):
            errors.append(f"score must be between 0.0 and 1.0, got {self.score}")
        
        # URL should look like a URL (basic check)
        if self.url and not (self.url.startswith("http://") or self.url.startswith("https://")):
            errors.append(f"url must start with http:// or https://, got {self.url}")
        
        if errors:
            raise ValueError(f"IdeaItem validation failed: {'; '.join(errors)}")
    
    def to_dict(self) -> dict:
        """
        Convert IdeaItem to a plain dictionary for storage/serialization.
        
        Datetime fields are converted to ISO format strings.
        
        Returns:
            Dictionary representation of this IdeaItem.
        """
        data = asdict(self)
        
        # Convert datetime fields to ISO strings for JSON compatibility
        if self.source_date:
            data["source_date"] = self.source_date.isoformat()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "IdeaItem":
        """
        Create an IdeaItem from a dictionary (e.g., from storage).
        
        Handles conversion of ISO format strings back to datetime objects.
        
        Args:
            data: Dictionary with IdeaItem fields.
            
        Returns:
            New IdeaItem instance.
        """
        # Make a copy to avoid modifying the input
        data = data.copy()
        
        # Convert ISO strings back to datetime objects
        if data.get("source_date") and isinstance(data["source_date"], str):
            data["source_date"] = datetime.fromisoformat(data["source_date"])
        
        if data.get("created_at") and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        
        if data.get("updated_at") and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return cls(**data)
    
    def update_score(self, new_score: float) -> None:
        """
        Update the score and refresh updated_at timestamp.
        
        Args:
            new_score: New score value (must be between 0.0 and 1.0).
        """
        if not (0.0 <= new_score <= 1.0):
            raise ValueError(f"score must be between 0.0 and 1.0, got {new_score}")
        self.score = new_score
        self.updated_at = datetime.now()
    
    def add_tags(self, new_tags: list[str]) -> None:
        """
        Add tags to this item (avoids duplicates).
        
        Args:
            new_tags: List of tags to add.
        """
        for tag in new_tags:
            tag = tag.strip().lower()
            if tag and tag not in self.tags:
                self.tags.append(tag)
        self.updated_at = datetime.now()
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"[{self.source_name}] {self.title} (score: {self.score:.2f})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"IdeaItem(id={self.id!r}, title={self.title!r}, "
            f"source_name={self.source_name!r}, score={self.score})"
        )

