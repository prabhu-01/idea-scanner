"""
Product Hunt source implementation.

Fetches recent product launches from Product Hunt using their RSS feed.
RSS is preferred over the official API because:
1. No authentication required
2. Simple and reliable
3. Contains all necessary fields (title, description, URL, date)

RSS Feed: https://www.producthunt.com/feed
"""

import time
from datetime import datetime
from typing import List, Optional
import feedparser

from src.config import DEFAULT_LIMIT_PER_SOURCE, REQUEST_TIMEOUT, SCRAPE_DELAY
from src.models.idea_item import IdeaItem
from src.sources.base import Source


# Product Hunt RSS feed URL
PH_RSS_FEED_URL = "https://www.producthunt.com/feed"


class ProductHuntSource(Source):
    """
    Fetches recent product launches from Product Hunt via RSS.
    
    Uses the public RSS feed which provides:
    - Product title
    - Tagline/description
    - Product Hunt URL
    - Publication date
    
    Rate limiting is enforced via SCRAPE_DELAY between requests
    (though RSS parsing is typically a single request).
    """
    
    def __init__(self, feed_url: str = None):
        """
        Initialize ProductHuntSource.
        
        Args:
            feed_url: Optional custom feed URL (for testing).
        """
        self.feed_url = feed_url or PH_RSS_FEED_URL
        self._last_request_time = 0.0
    
    @property
    def name(self) -> str:
        return "producthunt"
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < SCRAPE_DELAY:
            time.sleep(SCRAPE_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def fetch_items(self, limit: int | None = None) -> List[IdeaItem]:
        """
        Fetch recent product launches from Product Hunt RSS feed.
        
        Args:
            limit: Maximum number of items to fetch. Defaults to DEFAULT_LIMIT_PER_SOURCE.
            
        Returns:
            List of IdeaItem instances from Product Hunt.
        """
        if limit is None:
            limit = DEFAULT_LIMIT_PER_SOURCE
        
        self._rate_limit()
        
        # Parse RSS feed
        feed = self._fetch_feed()
        if not feed or not feed.entries:
            print(f"[{self.name}] Failed to fetch or parse RSS feed")
            return []
        
        # Normalize entries to IdeaItems
        items: List[IdeaItem] = []
        for entry in feed.entries[:limit]:
            item = self._normalize_entry(entry)
            if item is not None:
                items.append(item)
        
        print(f"[{self.name}] Fetched {len(items)} items (requested {limit})")
        return items
    
    def _fetch_feed(self) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse the RSS feed.
        
        Returns:
            Parsed feed or None on failure.
        """
        try:
            # feedparser handles timeout internally via request_headers
            # We set a user agent to be polite
            feed = feedparser.parse(
                self.feed_url,
                request_headers={
                    "User-Agent": "IdeaDigest/1.0 (RSS Reader)",
                },
            )
            
            # Check for feed errors
            if feed.bozo and not feed.entries:
                print(f"[{self.name}] Feed parse error: {feed.bozo_exception}")
                return None
            
            return feed
            
        except Exception as e:
            print(f"[{self.name}] Error fetching feed: {e}")
            return None
    
    def _normalize_entry(self, entry: dict) -> Optional[IdeaItem]:
        """
        Convert an RSS entry to an IdeaItem.
        
        RSS entry structure (from Product Hunt):
        {
            "title": "Product Name — Tagline",
            "link": "https://www.producthunt.com/posts/product-name",
            "published": "Tue, 24 Dec 2025 08:00:00 +0000",
            "published_parsed": time.struct_time,
            "id": "https://www.producthunt.com/posts/product-name",
            "summary": "Description text...",
        }
        
        Args:
            entry: RSS feed entry dict.
            
        Returns:
            IdeaItem if valid, None if missing required fields.
        """
        if not entry:
            return None
        
        # Extract title (required)
        title = entry.get("title", "").strip()
        if not title:
            return None
        
        # Extract URL (required)
        url = entry.get("link", "").strip()
        if not url:
            return None
        
        # Generate unique ID from URL
        # Product Hunt URLs are like: producthunt.com/posts/product-name
        item_id = self._extract_id_from_url(url)
        
        # Parse description/summary
        description = self._clean_description(entry.get("summary", ""))
        
        # Parse publication date
        source_date = self._parse_date(entry)
        
        try:
            return IdeaItem(
                id=f"ph_{item_id}",
                title=title,
                description=description,
                url=url,
                source_name=self.name,
                source_date=source_date,
                score=0.0,
                tags=[],
            )
        except ValueError as e:
            print(f"[{self.name}] Invalid entry: {e}")
            return None
    
    def _extract_id_from_url(self, url: str) -> str:
        """
        Extract a unique ID from the Product Hunt URL.
        
        Args:
            url: Product Hunt post URL.
            
        Returns:
            Extracted ID or hash of URL.
        """
        # URL format: https://www.producthunt.com/posts/product-name
        if "/posts/" in url:
            return url.split("/posts/")[-1].split("?")[0]
        
        # Fallback: use hash of URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def _clean_description(self, summary: str) -> str:
        """
        Clean HTML and extract text from RSS summary.
        
        Args:
            summary: Raw summary text (may contain HTML).
            
        Returns:
            Cleaned text description.
        """
        if not summary:
            return ""
        
        # Remove HTML tags (simple approach)
        import re
        clean = re.sub(r"<[^>]+>", " ", summary)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()[:500]  # Limit length
    
    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """
        Parse publication date from RSS entry.
        
        Args:
            entry: RSS feed entry.
            
        Returns:
            datetime if parseable, None otherwise.
        """
        # Try parsed time tuple first
        if entry.get("published_parsed"):
            try:
                import time as time_module
                return datetime(*entry["published_parsed"][:6])
            except (ValueError, TypeError):
                pass
        
        # Try published string
        if entry.get("published"):
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(entry["published"])
            except (ValueError, TypeError):
                pass
        
        return None

