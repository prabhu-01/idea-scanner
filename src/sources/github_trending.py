"""
GitHub Trending source implementation.

Fetches trending repositories from GitHub's trending page via HTML parsing.
Uses BeautifulSoup for lightweight parsing without requiring Playwright.

Why HTML parsing instead of API:
1. GitHub doesn't have an official "trending" API endpoint
2. The trending page is publicly accessible
3. BeautifulSoup is lightweight and reliable
4. Avoids authentication complexity

Trending page: https://github.com/trending
"""

import time
from datetime import datetime
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

from src.config import DEFAULT_LIMIT_PER_SOURCE, REQUEST_TIMEOUT, SCRAPE_DELAY
from src.models.idea_item import IdeaItem
from src.sources.base import Source


# GitHub Trending page URLs
GH_TRENDING_URL = "https://github.com/trending"
GH_TRENDING_BY_LANGUAGE_URL = "https://github.com/trending/{language}"


class GitHubTrendingSource(Source):
    """
    Fetches trending repositories from GitHub via HTML parsing.
    
    Parses the GitHub trending page which provides:
    - Repository name (owner/repo)
    - Description
    - Stars count
    - Language
    - Stars gained today
    
    Rate limiting is enforced via SCRAPE_DELAY to be respectful.
    A polite User-Agent is used to identify the scraper.
    """
    
    # User agent for polite scraping
    USER_AGENT = "IdeaDigest/1.0 (GitHub Trending Reader; +https://github.com)"
    
    def __init__(self, language: str = None, since: str = "daily"):
        """
        Initialize GitHubTrendingSource.
        
        Args:
            language: Filter by programming language (e.g., "python", "rust").
                      None for all languages.
            since: Time range - "daily", "weekly", or "monthly".
        """
        self.language = language
        self.since = since
        self._last_request_time = 0.0
    
    @property
    def name(self) -> str:
        return "github"
    
    @property
    def _url(self) -> str:
        """Construct the trending page URL."""
        if self.language:
            base_url = GH_TRENDING_BY_LANGUAGE_URL.format(language=self.language)
        else:
            base_url = GH_TRENDING_URL
        
        return f"{base_url}?since={self.since}"
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < SCRAPE_DELAY:
            time.sleep(SCRAPE_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def fetch_items(self, limit: int | None = None) -> List[IdeaItem]:
        """
        Fetch trending repositories from GitHub.
        
        Args:
            limit: Maximum number of items to fetch. Defaults to DEFAULT_LIMIT_PER_SOURCE.
            
        Returns:
            List of IdeaItem instances from GitHub trending.
        """
        if limit is None:
            limit = DEFAULT_LIMIT_PER_SOURCE
        
        self._rate_limit()
        
        # Fetch and parse the trending page
        html = self._fetch_page()
        if not html:
            print(f"[{self.name}] Failed to fetch trending page")
            return []
        
        # Parse repository entries
        repos = self._parse_repos(html)
        
        # Normalize to IdeaItems
        items: List[IdeaItem] = []
        for repo in repos[:limit]:
            item = self._normalize_repo(repo)
            if item is not None:
                items.append(item)
        
        print(f"[{self.name}] Fetched {len(items)} items (requested {limit})")
        return items
    
    def _fetch_page(self) -> Optional[str]:
        """
        Fetch the GitHub trending page HTML.
        
        Returns:
            HTML string or None on failure.
        """
        try:
            response = requests.get(
                self._url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.text
            
        except requests.RequestException as e:
            print(f"[{self.name}] Error fetching page: {e}")
            return None
        except Exception as e:
            print(f"[{self.name}] Unexpected error: {e}")
            return None
    
    def _parse_repos(self, html: str) -> List[dict]:
        """
        Parse repository information from the trending page HTML.
        
        GitHub trending page structure (as of 2024):
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/owner/repo">owner / repo</a>
          </h2>
          <p class="col-9 color-fg-muted my-1 pr-4">Description...</p>
          <span class="d-inline-block ml-0 mr-3">
            <span class="repo-language-color" style="..."></span>
            <span>Python</span>
          </span>
          <a href="/owner/repo/stargazers">1,234 stars</a>
          <span>234 stars today</span>
        </article>
        
        Args:
            html: Raw HTML of the trending page.
            
        Returns:
            List of parsed repository dicts.
        """
        repos = []
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find all repository articles
            articles = soup.find_all("article", class_="Box-row")
            
            for article in articles:
                repo = self._parse_article(article)
                if repo:
                    repos.append(repo)
                    
        except Exception as e:
            print(f"[{self.name}] Error parsing HTML: {e}")
        
        return repos
    
    def _parse_article(self, article) -> Optional[dict]:
        """
        Parse a single repository article element.
        
        Args:
            article: BeautifulSoup article element.
            
        Returns:
            Dict with repo info or None if parsing fails.
        """
        try:
            # Find repo link (h2 > a)
            h2 = article.find("h2")
            if not h2:
                return None
            
            link = h2.find("a")
            if not link or not link.get("href"):
                return None
            
            href = link.get("href", "").strip()
            if not href or href.count("/") < 1:
                return None
            
            # Extract owner/repo from href
            parts = href.strip("/").split("/")
            if len(parts) < 2:
                return None
            
            owner = parts[0]
            repo_name = parts[1]
            full_name = f"{owner}/{repo_name}"
            
            # Get description
            desc_elem = article.find("p")
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Get language
            lang_elem = article.find("span", itemprop="programmingLanguage")
            language = lang_elem.get_text(strip=True) if lang_elem else ""
            
            # Get stars count (look for stargazers link)
            stars = self._extract_stars(article)
            
            # Get stars today
            stars_today = self._extract_stars_today(article)
            
            return {
                "full_name": full_name,
                "owner": owner,
                "repo": repo_name,
                "description": description,
                "language": language,
                "stars": stars,
                "stars_today": stars_today,
                "url": f"https://github.com/{full_name}",
            }
            
        except Exception:
            return None
    
    def _extract_stars(self, article) -> int:
        """Extract total stars count from article."""
        try:
            # Look for stargazers link
            star_link = article.find("a", href=lambda h: h and "/stargazers" in h)
            if star_link:
                text = star_link.get_text(strip=True)
                return self._parse_number(text)
            return 0
        except Exception:
            return 0
    
    def _extract_stars_today(self, article) -> int:
        """Extract stars gained today from article."""
        try:
            # Look for "stars today" or "stars this week" text
            for span in article.find_all("span", class_="d-inline-block"):
                text = span.get_text(strip=True)
                if "stars" in text.lower() and ("today" in text.lower() or "this" in text.lower()):
                    return self._parse_number(text)
            return 0
        except Exception:
            return 0
    
    def _parse_number(self, text: str) -> int:
        """
        Parse a number from text like "1,234 stars" or "1.2k".
        
        Args:
            text: Text containing a number.
            
        Returns:
            Parsed integer.
        """
        import re
        
        # Remove commas
        text = text.replace(",", "")
        
        # Find number with optional k/m suffix
        match = re.search(r"([\d.]+)\s*([km])?", text.lower())
        if match:
            num = float(match.group(1))
            suffix = match.group(2)
            
            if suffix == "k":
                num *= 1000
            elif suffix == "m":
                num *= 1000000
            
            return int(num)
        
        return 0
    
    def _normalize_repo(self, repo: dict) -> Optional[IdeaItem]:
        """
        Convert a parsed repository dict to an IdeaItem.
        
        Args:
            repo: Parsed repository dict.
            
        Returns:
            IdeaItem if valid, None otherwise.
        """
        if not repo:
            return None
        
        full_name = repo.get("full_name", "")
        url = repo.get("url", "")
        
        if not full_name or not url:
            return None
        
        # Build title
        title = full_name
        if repo.get("language"):
            title = f"{full_name} ({repo['language']})"
        
        # Build description with stats
        desc_parts = []
        if repo.get("description"):
            desc_parts.append(repo["description"])
        
        stats = []
        if repo.get("stars"):
            stats.append(f"⭐ {repo['stars']:,}")
        if repo.get("stars_today"):
            stats.append(f"+{repo['stars_today']} today")
        
        if stats:
            desc_parts.append(" | ".join(stats))
        
        description = " — ".join(desc_parts) if desc_parts else ""
        
        # Generate unique ID
        item_id = full_name.replace("/", "_")
        
        try:
            return IdeaItem(
                id=f"gh_{item_id}",
                title=title,
                description=description,
                url=url,
                source_name=self.name,
                source_date=datetime.now(),  # Trending is "now"
                score=0.0,
                tags=[],
            )
        except ValueError as e:
            print(f"[{self.name}] Invalid repo {full_name}: {e}")
            return None

