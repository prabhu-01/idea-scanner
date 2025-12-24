"""
Hacker News source implementation.

Fetches top stories from Hacker News using the official Firebase API.
API Documentation: https://github.com/HackerNews/API
"""

from datetime import datetime
from typing import List, Optional, Any
import requests

from src.config import DEFAULT_LIMIT_PER_SOURCE, REQUEST_TIMEOUT
from src.models.idea_item import IdeaItem
from src.sources.base import Source


# Hacker News Firebase API endpoints
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_TOP_STORIES_URL = f"{HN_API_BASE}/topstories.json"
HN_ITEM_URL = f"{HN_API_BASE}/item/{{item_id}}.json"

# Hacker News web URL for items
HN_ITEM_WEB_URL = "https://news.ycombinator.com/item?id={item_id}"


class HackerNewsSource(Source):
    """
    Fetches top stories from Hacker News.
    
    Uses the official Hacker News Firebase API:
    - First fetches the list of top story IDs
    - Then fetches individual item details for each ID
    - Normalizes items into IdeaItem instances
    
    Items missing required fields (title, url, id) are gracefully skipped.
    "Ask HN" and "Show HN" posts without external URLs use the HN discussion URL.
    """
    
    @property
    def name(self) -> str:
        return "hackernews"
    
    def fetch_items(self, limit: int | None = None) -> List[IdeaItem]:
        """
        Fetch top stories from Hacker News.
        
        Args:
            limit: Maximum number of items to fetch. Defaults to DEFAULT_LIMIT_PER_SOURCE.
            
        Returns:
            List of IdeaItem instances from top HN stories.
        """
        if limit is None:
            limit = DEFAULT_LIMIT_PER_SOURCE
        
        # Step 1: Fetch top story IDs
        story_ids = self._fetch_top_story_ids(limit)
        if not story_ids:
            print(f"[{self.name}] Failed to fetch story IDs")
            return []
        
        # Step 2: Fetch individual items and normalize
        items: List[IdeaItem] = []
        for story_id in story_ids:
            item = self._fetch_and_normalize_item(story_id)
            if item is not None:
                items.append(item)
        
        print(f"[{self.name}] Fetched {len(items)} items (requested {limit})")
        return items
    
    def _fetch_top_story_ids(self, limit: int) -> List[int]:
        """
        Fetch the list of top story IDs from HN API.
        
        Args:
            limit: Maximum number of IDs to return.
            
        Returns:
            List of story IDs (may be fewer than limit if API returns fewer).
        """
        try:
            response = requests.get(
                HN_TOP_STORIES_URL,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            all_ids = response.json()
            
            # Return only up to limit
            return all_ids[:limit] if all_ids else []
            
        except requests.RequestException as e:
            print(f"[{self.name}] Error fetching top stories: {e}")
            return []
        except Exception as e:
            print(f"[{self.name}] Unexpected error fetching top stories: {e}")
            return []
    
    def _fetch_and_normalize_item(self, item_id: int) -> Optional[IdeaItem]:
        """
        Fetch a single item from HN API and normalize to IdeaItem.
        
        Args:
            item_id: The HN item ID to fetch.
            
        Returns:
            IdeaItem if successful, None if fetch fails or item is invalid.
        """
        raw_item = self._fetch_item(item_id)
        if raw_item is None:
            return None
        
        return self._normalize_item(raw_item)
    
    def _fetch_item(self, item_id: int) -> Optional[dict]:
        """
        Fetch a single item's data from the HN API.
        
        Args:
            item_id: The HN item ID.
            
        Returns:
            Raw item dict from API, or None on failure.
        """
        try:
            url = HN_ITEM_URL.format(item_id=item_id)
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"[{self.name}] Error fetching item {item_id}: {e}")
            return None
        except (ValueError, TypeError) as e:
            print(f"[{self.name}] Error parsing item {item_id}: {e}")
            return None
    
    def _normalize_item(self, raw: dict) -> Optional[IdeaItem]:
        """
        Convert raw HN API response to an IdeaItem.
        
        HN API item structure:
        {
            "id": 12345,
            "type": "story",
            "title": "Example Title",
            "url": "https://example.com",  # Optional for Ask HN, etc.
            "text": "...",                  # Optional, for self-posts
            "by": "username",
            "time": 1234567890,             # Unix timestamp
            "score": 100,
            "descendants": 50               # Comment count
        }
        
        Args:
            raw: Raw item dict from HN API.
            
        Returns:
            IdeaItem if valid, None if missing required fields.
        """
        if not raw or not isinstance(raw, dict):
            return None
        
        # Extract and validate required fields
        item_id = raw.get("id")
        title = raw.get("title")
        
        # ID and title are required
        if not item_id or not title:
            return None
        
        # URL is optional in HN API (Ask HN, Show HN without link, etc.)
        # Fall back to HN discussion page URL
        url = raw.get("url")
        if not url:
            url = HN_ITEM_WEB_URL.format(item_id=item_id)
        
        # Parse timestamp to datetime
        source_date = None
        if raw.get("time"):
            try:
                source_date = datetime.fromtimestamp(raw["time"])
            except (ValueError, TypeError, OSError):
                pass
        
        # Build description from available info
        description = self._build_description(raw)
        
        try:
            return IdeaItem(
                id=f"hn_{item_id}",
                title=title.strip(),
                description=description,
                url=url,
                source_name=self.name,
                source_date=source_date,
                score=0.0,  # Score will be set by scoring module later
                tags=[],    # Tags will be set by scoring module later
            )
        except ValueError as e:
            # Validation failed in IdeaItem
            print(f"[{self.name}] Invalid item {item_id}: {e}")
            return None
    
    def _build_description(self, raw: dict) -> str:
        """
        Build a description string from available HN item fields.
        
        Args:
            raw: Raw item dict from HN API.
            
        Returns:
            Description string.
        """
        parts = []
        
        # Add author if present
        if raw.get("by"):
            parts.append(f"by {raw['by']}")
        
        # Add score if present
        if raw.get("score"):
            parts.append(f"{raw['score']} points")
        
        # Add comment count if present
        if raw.get("descendants"):
            parts.append(f"{raw['descendants']} comments")
        
        return " | ".join(parts) if parts else ""

