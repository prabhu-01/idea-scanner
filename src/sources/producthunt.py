"""
Product Hunt source implementation.

Fetches recent product launches from Product Hunt using the GraphQL API.
Falls back to RSS feed if API token is not configured.

API Documentation: https://api.producthunt.com/v2/docs
"""

import time
from datetime import datetime
from typing import List, Optional
import requests
import feedparser

from src.config import DEFAULT_LIMIT_PER_SOURCE, REQUEST_TIMEOUT, SCRAPE_DELAY, PRODUCT_HUNT_TOKEN
from src.models.idea_item import IdeaItem
from src.sources.base import Source


# Product Hunt endpoints
PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
PH_RSS_FEED_URL = "https://www.producthunt.com/feed"


class ProductHuntSource(Source):
    """
    Fetches recent product launches from Product Hunt.
    
    Uses the GraphQL API if PRODUCT_HUNT_TOKEN is configured (recommended).
    Falls back to RSS feed otherwise (no vote counts available).
    """
    
    def __init__(self, feed_url: str = None, api_token: str = None):
        """
        Initialize ProductHuntSource.
        
        Args:
            feed_url: Optional custom RSS feed URL (for testing).
            api_token: Optional API token override (for testing).
        """
        self.feed_url = feed_url or PH_RSS_FEED_URL
        self.api_token = api_token if api_token is not None else PRODUCT_HUNT_TOKEN
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
        Fetch recent product launches from Product Hunt.
        
        Uses GraphQL API if token is available, otherwise falls back to RSS.
        
        Args:
            limit: Maximum number of items to fetch. Defaults to DEFAULT_LIMIT_PER_SOURCE.
            
        Returns:
            List of IdeaItem instances from Product Hunt.
        """
        if limit is None:
            limit = DEFAULT_LIMIT_PER_SOURCE
        
        self._rate_limit()
        
        # Use GraphQL API if token is available
        if self.api_token:
            return self._fetch_via_api(limit)
        else:
            return self._fetch_via_rss(limit)
    
    # =========================================================================
    # GraphQL API Implementation
    # =========================================================================
    
    def _fetch_via_api(self, limit: int) -> List[IdeaItem]:
        """Fetch products using GraphQL API (includes vote counts)."""
        query = """
        query GetPosts($first: Int!) {
            posts(first: $first) {
                edges {
                    node {
                        id
                        name
                        tagline
                        description
                        url
                        votesCount
                        commentsCount
                        createdAt
                        website
                        topics {
                            edges {
                                node {
                                    name
                                }
                            }
                        }
                        makers {
                            id
                            name
                            username
                            headline
                            profileImage
                            twitterUsername
                        }
                    }
                }
            }
        }
        """
        
        try:
            response = requests.post(
                PH_GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "variables": {"first": limit}
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                print(f"[{self.name}] GraphQL errors: {data['errors']}")
                return []
            
            items = []
            posts = data.get("data", {}).get("posts", {}).get("edges", [])
            
            for edge in posts:
                item = self._normalize_api_post(edge.get("node", {}))
                if item:
                    items.append(item)
            
            print(f"[{self.name}] Fetched {len(items)} items via API (requested {limit})")
            return items
            
        except requests.RequestException as e:
            print(f"[{self.name}] API error: {e}")
            return []
        except Exception as e:
            print(f"[{self.name}] Unexpected error: {e}")
            return []
    
    def _normalize_api_post(self, post: dict) -> Optional[IdeaItem]:
        """Convert GraphQL API response to IdeaItem."""
        if not post:
            return None
        
        name = post.get("name", "").strip()
        if not name:
            return None
        
        # Prefer website URL, fall back to PH post URL
        url = post.get("website") or post.get("url", "")
        if not url:
            return None
        
        # Extract post ID for unique key
        post_id = post.get("id", "")
        
        # Parse created date (remove timezone info for consistency)
        source_date = None
        if post.get("createdAt"):
            try:
                # Format: 2025-12-27T08:00:00Z
                date_str = post["createdAt"].replace("Z", "")
                if "+" in date_str:
                    date_str = date_str.split("+")[0]
                source_date = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass
        
        # Build description from tagline
        tagline = post.get("tagline", "")
        description = post.get("description", "")
        
        # Use tagline as primary description (it's usually more concise)
        final_description = tagline if tagline else (description[:200] if description else "")
        
        # Extract metrics
        votes = post.get("votesCount", 0)
        comments_count = post.get("commentsCount", 0)
        
        # Extract topics as tags
        topics = []
        for topic_edge in post.get("topics", {}).get("edges", []):
            topic_name = topic_edge.get("node", {}).get("name", "")
            if topic_name:
                topics.append(topic_name.lower())
        
        # Extract maker info (first maker)
        makers = post.get("makers", [])
        maker_name = None
        maker_username = None
        maker_url = None
        maker_avatar = None
        maker_bio = None
        maker_twitter = None
        
        if makers and len(makers) > 0:
            first_maker = makers[0]
            maker_name = first_maker.get("name")
            maker_username = first_maker.get("username")
            maker_url = f"https://www.producthunt.com/@{maker_username}" if maker_username else None
            maker_avatar = first_maker.get("profileImage")
            maker_bio = first_maker.get("headline")
            maker_twitter = first_maker.get("twitterUsername")
        
        try:
            return IdeaItem(
                id=f"ph_{post_id}",
                title=name,
                description=final_description,
                url=url,
                source_name=self.name,
                source_date=source_date,
                score=0.0,
                tags=topics[:5],  # Limit to 5 tags
                # Platform-specific metrics
                votes=votes,
                comments_count=comments_count,
                # Maker info
                maker_name=maker_name,
                maker_username=maker_username,
                maker_url=maker_url,
                maker_avatar=maker_avatar,
                maker_bio=maker_bio,
                maker_twitter=maker_twitter,
            )
        except ValueError as e:
            print(f"[{self.name}] Invalid post {name}: {e}")
            return None
    
    # =========================================================================
    # RSS Feed Implementation (Fallback)
    # =========================================================================
    
    def _fetch_via_rss(self, limit: int) -> List[IdeaItem]:
        """Fetch products via RSS feed (no vote counts)."""
        print(f"[{self.name}] No API token, using RSS feed (vote counts unavailable)")
        
        feed = self._fetch_feed()
        if not feed or not feed.entries:
            print(f"[{self.name}] Failed to fetch or parse RSS feed")
            return []
        
        items: List[IdeaItem] = []
        for entry in feed.entries[:limit]:
            item = self._normalize_rss_entry(entry)
            if item is not None:
                items.append(item)
        
        print(f"[{self.name}] Fetched {len(items)} items via RSS (requested {limit})")
        return items
    
    def _fetch_feed(self) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse the RSS feed."""
        try:
            feed = feedparser.parse(
                self.feed_url,
                request_headers={
                    "User-Agent": "IdeaDigest/1.0 (RSS Reader)",
                },
            )
            
            if feed.bozo and not feed.entries:
                print(f"[{self.name}] Feed parse error: {feed.bozo_exception}")
                return None
            
            return feed
            
        except Exception as e:
            print(f"[{self.name}] Error fetching feed: {e}")
            return None
    
    def _normalize_rss_entry(self, entry: dict) -> Optional[IdeaItem]:
        """Convert an RSS entry to an IdeaItem."""
        if not entry:
            return None
        
        title = entry.get("title", "").strip()
        if not title:
            return None
        
        url = entry.get("link", "").strip()
        if not url:
            return None
        
        item_id = self._extract_id_from_url(url)
        description = self._clean_description(entry.get("summary", ""))
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
                # No metrics available from RSS
                votes=None,
                comments_count=None,
            )
        except ValueError as e:
            print(f"[{self.name}] Invalid entry: {e}")
            return None
    
    def _extract_id_from_url(self, url: str) -> str:
        """Extract a unique ID from the Product Hunt URL."""
        if "/posts/" in url:
            return url.split("/posts/")[-1].split("?")[0]
        
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def _clean_description(self, summary: str) -> str:
        """Clean HTML and extract text from RSS summary."""
        if not summary:
            return ""
        
        import re
        clean = re.sub(r"<[^>]+>", " ", summary)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()[:500]
    
    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        if entry.get("published_parsed"):
            try:
                return datetime(*entry["published_parsed"][:6])
            except (ValueError, TypeError):
                pass
        
        if entry.get("published"):
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(entry["published"])
            except (ValueError, TypeError):
                pass
        
        return None
