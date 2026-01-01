"""
Tests for ProductHuntSource and GitHubTrendingSource.

Tests normalization, source_name assignment, limit handling,
graceful failure, and source independence.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.sources.producthunt import ProductHuntSource, PH_RSS_FEED_URL
from src.sources.github_trending import GitHubTrendingSource, GH_TRENDING_URL


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def ph_source():
    """ProductHuntSource instance for testing."""
    return ProductHuntSource()


@pytest.fixture
def gh_source():
    """GitHubTrendingSource instance for testing."""
    return GitHubTrendingSource()


@pytest.fixture
def sample_rss_entry():
    """Sample Product Hunt RSS entry."""
    return {
        "title": "Amazing Product — The best product ever",
        "link": "https://www.producthunt.com/posts/amazing-product",
        "published": "Tue, 24 Dec 2025 08:00:00 +0000",
        "published_parsed": (2025, 12, 24, 8, 0, 0, 1, 358, 0),
        "id": "https://www.producthunt.com/posts/amazing-product",
        "summary": "<p>This is an amazing product that does amazing things.</p>",
    }


@pytest.fixture
def sample_github_html():
    """Sample GitHub trending page HTML."""
    return """
    <html>
    <body>
    <article class="Box-row">
        <h2 class="h3 lh-condensed">
            <a href="/openai/gpt-5">openai / gpt-5</a>
        </h2>
        <p class="col-9 color-fg-muted my-1 pr-4">The next generation AI model</p>
        <span itemprop="programmingLanguage">Python</span>
        <a href="/openai/gpt-5/stargazers">12,345</a>
        <span class="d-inline-block float-sm-right">1,234 stars today</span>
    </article>
    <article class="Box-row">
        <h2 class="h3 lh-condensed">
            <a href="/rust-lang/rust">rust-lang / rust</a>
        </h2>
        <p class="col-9 color-fg-muted my-1 pr-4">Empowering everyone to build reliable software</p>
        <span itemprop="programmingLanguage">Rust</span>
        <a href="/rust-lang/rust/stargazers">85,000</a>
        <span class="d-inline-block float-sm-right">500 stars today</span>
    </article>
    <article class="Box-row">
        <h2 class="h3 lh-condensed">
            <a href="/facebook/react">facebook / react</a>
        </h2>
        <p class="col-9 color-fg-muted my-1 pr-4">A declarative UI library</p>
        <span itemprop="programmingLanguage">JavaScript</span>
        <a href="/facebook/react/stargazers">200,000</a>
    </article>
    </body>
    </html>
    """


# =============================================================================
# Test ProductHuntSource Interface
# =============================================================================

class TestProductHuntSourceInterface:
    """Tests for ProductHuntSource interface compliance."""
    
    def test_is_source_subclass(self, ph_source):
        """ProductHuntSource is a proper Source subclass."""
        assert isinstance(ph_source, Source)
    
    def test_name_property(self, ph_source):
        """ProductHuntSource has correct name."""
        assert ph_source.name == "producthunt"
    
    def test_default_feed_url(self, ph_source):
        """ProductHuntSource uses default feed URL."""
        assert ph_source.feed_url == PH_RSS_FEED_URL
    
    def test_custom_feed_url(self):
        """ProductHuntSource accepts custom feed URL."""
        custom_url = "https://custom.feed/rss"
        source = ProductHuntSource(feed_url=custom_url)
        assert source.feed_url == custom_url


# =============================================================================
# Test ProductHuntSource Normalization
# =============================================================================

class TestProductHuntNormalization:
    """Tests for Product Hunt RSS entry and API post normalization."""
    
    def test_normalize_rss_entry(self, ph_source, sample_rss_entry):
        """Complete RSS entry normalizes correctly via RSS method."""
        item = ph_source._normalize_rss_entry(sample_rss_entry)
        
        assert item is not None
        assert item.title == "Amazing Product — The best product ever"
        assert item.url == "https://www.producthunt.com/posts/amazing-product"
        assert item.source_name == "producthunt"
        assert item.id == "ph_amazing-product"
        assert "amazing product" in item.description.lower()
        assert item.source_date is not None
    
    def test_normalize_api_post(self, ph_source):
        """Complete API post normalizes correctly."""
        api_post = {
            "id": "123456",
            "name": "Amazing Product",
            "tagline": "The best product ever",
            "description": "Full description here",
            "url": "https://www.producthunt.com/posts/amazing-product",
            "votesCount": 500,
            "commentsCount": 50,
            "createdAt": "2025-12-24T10:00:00Z",
            "makers": [
                {
                    "name": "John Doe",
                    "username": "johndoe",
                }
            ],
        }
        item = ph_source._normalize_api_post(api_post)
        
        assert item is not None
        assert item.title == "Amazing Product"
        assert item.source_name == "producthunt"
        assert item.id == "ph_123456"
        assert item.votes == 500
        assert item.comments_count == 50
    
    def test_normalize_rss_missing_title_returns_none(self, ph_source):
        """RSS entry without title returns None."""
        entry = {"link": "https://example.com"}
        item = ph_source._normalize_rss_entry(entry)
        assert item is None
    
    def test_normalize_rss_missing_url_returns_none(self, ph_source):
        """RSS entry without link returns None."""
        entry = {"title": "Product Name"}
        item = ph_source._normalize_rss_entry(entry)
        assert item is None
    
    def test_normalize_api_empty_returns_none(self, ph_source):
        """Empty API post returns None."""
        item = ph_source._normalize_api_post({})
        assert item is None
    
    def test_normalize_api_none_returns_none(self, ph_source):
        """None API post returns None."""
        item = ph_source._normalize_api_post(None)
        assert item is None
    
    def test_normalize_rss_strips_html_from_description(self, ph_source):
        """HTML tags are stripped from RSS description."""
        entry = {
            "title": "Product",
            "link": "https://producthunt.com/posts/product",
            "summary": "<p>Hello <strong>World</strong></p>",
        }
        item = ph_source._normalize_rss_entry(entry)
        assert "<" not in item.description
        assert ">" not in item.description
        assert "Hello" in item.description
        assert "World" in item.description
    
    def test_id_extraction_from_rss_url(self, ph_source):
        """ID is correctly extracted from Product Hunt RSS URL."""
        entry = {
            "title": "Product",
            "link": "https://www.producthunt.com/posts/my-cool-product",
        }
        item = ph_source._normalize_rss_entry(entry)
        assert item.id == "ph_my-cool-product"


# =============================================================================
# Test ProductHuntSource Fetching (Mocked)
# =============================================================================

class TestProductHuntFetching:
    """Tests for Product Hunt fetching with mocked responses."""
    
    @pytest.fixture
    def ph_source_no_token(self):
        """ProductHuntSource without API token (uses RSS fallback)."""
        return ProductHuntSource(api_token="")
    
    def test_fetch_rss_success(self, ph_source_no_token, sample_rss_entry):
        """Successful RSS fetch returns IdeaItems."""
        mock_feed = Mock()
        mock_feed.entries = [sample_rss_entry, sample_rss_entry]
        mock_feed.bozo = False
        
        with patch.object(ph_source_no_token, '_fetch_feed', return_value=mock_feed):
            items = ph_source_no_token.fetch_items(limit=5)
            
            assert len(items) == 2
            assert all(isinstance(item, IdeaItem) for item in items)
    
    def test_fetch_rss_respects_limit(self, ph_source_no_token, sample_rss_entry):
        """RSS fetch respects the limit parameter."""
        mock_feed = Mock()
        mock_feed.entries = [sample_rss_entry] * 10
        mock_feed.bozo = False
        
        with patch.object(ph_source_no_token, '_fetch_feed', return_value=mock_feed):
            items = ph_source_no_token.fetch_items(limit=3)
            
            assert len(items) == 3
    
    def test_fetch_rss_returns_empty_on_error(self, ph_source_no_token):
        """RSS feed error returns empty list."""
        with patch.object(ph_source_no_token, '_fetch_feed', return_value=None):
            items = ph_source_no_token.fetch_items(limit=5)
            
            assert items == []
    
    def test_fetch_api_success(self, ph_source):
        """Successful API fetch returns IdeaItems when token is available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "posts": {
                    "edges": [
                        {"node": {"id": "1", "name": "Product 1", "url": "http://example.com/1"}},
                        {"node": {"id": "2", "name": "Product 2", "url": "http://example.com/2"}},
                    ]
                }
            }
        }
        
        with patch("requests.post", return_value=mock_response):
            # Use a source with a test token
            source = ProductHuntSource(api_token="test_token")
            items = source.fetch_items(limit=5)
            
            assert len(items) == 2
            assert all(isinstance(item, IdeaItem) for item in items)
    
    def test_fetch_api_error_returns_empty(self):
        """API error returns empty list."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Unauthorized")
        
        with patch("requests.post", return_value=mock_response):
            source = ProductHuntSource(api_token="bad_token")
            mock_response.raise_for_status.side_effect = Exception("Unauthorized")
            
            with patch("requests.post") as mock_post:
                mock_post.side_effect = Exception("API Error")
                items = source.fetch_items(limit=5)
                
                assert items == []


# =============================================================================
# Test GitHubTrendingSource Interface
# =============================================================================

class TestGitHubTrendingSourceInterface:
    """Tests for GitHubTrendingSource interface compliance."""
    
    def test_is_source_subclass(self, gh_source):
        """GitHubTrendingSource is a proper Source subclass."""
        assert isinstance(gh_source, Source)
    
    def test_name_property(self, gh_source):
        """GitHubTrendingSource has correct name."""
        assert gh_source.name == "github"
    
    def test_default_url(self, gh_source):
        """Default URL is correct."""
        assert GH_TRENDING_URL in gh_source._url
    
    def test_language_filter(self):
        """Language filter modifies URL."""
        source = GitHubTrendingSource(language="python")
        assert "python" in source._url
    
    def test_since_parameter(self):
        """Since parameter is included in URL."""
        source = GitHubTrendingSource(since="weekly")
        assert "since=weekly" in source._url


# =============================================================================
# Test GitHubTrendingSource Normalization
# =============================================================================

class TestGitHubTrendingNormalization:
    """Tests for GitHub repository normalization."""
    
    def test_normalize_complete_repo(self, gh_source):
        """Complete repo dict normalizes correctly."""
        repo = {
            "full_name": "openai/gpt-5",
            "owner": "openai",
            "repo": "gpt-5",
            "description": "The next generation AI model",
            "language": "Python",
            "stars": 12345,
            "stars_today": 1234,
            "url": "https://github.com/openai/gpt-5",
        }
        
        item = gh_source._normalize_repo(repo)
        
        assert item is not None
        assert "openai/gpt-5" in item.title
        assert item.url == "https://github.com/openai/gpt-5"
        assert item.source_name == "github"
        assert item.id == "gh_openai_gpt-5"
        # Check that stars and language are captured (may be in title or fields)
        assert item.stars == 12345 or "12" in str(item.description) or "12" in item.title
        assert item.language == "Python" or "Python" in item.title
    
    def test_normalize_missing_full_name_returns_none(self, gh_source):
        """Repo without full_name returns None."""
        repo = {"url": "https://github.com/test/test"}
        item = gh_source._normalize_repo(repo)
        assert item is None
    
    def test_normalize_missing_url_returns_none(self, gh_source):
        """Repo without URL returns None."""
        repo = {"full_name": "test/test"}
        item = gh_source._normalize_repo(repo)
        assert item is None
    
    def test_normalize_empty_repo_returns_none(self, gh_source):
        """Empty repo dict returns None."""
        item = gh_source._normalize_repo({})
        assert item is None
    
    def test_normalize_none_returns_none(self, gh_source):
        """None input returns None."""
        item = gh_source._normalize_repo(None)
        assert item is None
    
    def test_normalize_without_language(self, gh_source):
        """Repo without language still normalizes."""
        repo = {
            "full_name": "user/repo",
            "url": "https://github.com/user/repo",
        }
        item = gh_source._normalize_repo(repo)
        assert item is not None
        assert item.title == "user/repo"


# =============================================================================
# Test GitHubTrendingSource HTML Parsing
# =============================================================================

class TestGitHubTrendingParsing:
    """Tests for GitHub trending page HTML parsing."""
    
    def test_parse_repos_from_html(self, gh_source, sample_github_html):
        """HTML is correctly parsed into repo dicts."""
        repos = gh_source._parse_repos(sample_github_html)
        
        assert len(repos) == 3
        assert repos[0]["full_name"] == "openai/gpt-5"
        assert repos[1]["full_name"] == "rust-lang/rust"
        assert repos[2]["full_name"] == "facebook/react"
    
    def test_parse_extracts_description(self, gh_source, sample_github_html):
        """Description is extracted from HTML."""
        repos = gh_source._parse_repos(sample_github_html)
        
        assert "next generation AI" in repos[0]["description"]
    
    def test_parse_extracts_language(self, gh_source, sample_github_html):
        """Language is extracted from HTML."""
        repos = gh_source._parse_repos(sample_github_html)
        
        assert repos[0]["language"] == "Python"
        assert repos[1]["language"] == "Rust"
    
    def test_parse_handles_empty_html(self, gh_source):
        """Empty HTML returns empty list."""
        repos = gh_source._parse_repos("")
        assert repos == []
    
    def test_parse_handles_invalid_html(self, gh_source):
        """Invalid HTML doesn't crash."""
        repos = gh_source._parse_repos("<html><body>No repos here</body></html>")
        assert repos == []


# =============================================================================
# Test GitHubTrendingSource Fetching (Mocked)
# =============================================================================

class TestGitHubTrendingFetching:
    """Tests for GitHub trending fetching with mocked responses."""
    
    def test_fetch_success(self, gh_source, sample_github_html):
        """Successful fetch returns IdeaItems."""
        with patch.object(gh_source, '_fetch_page', return_value=sample_github_html):
            items = gh_source.fetch_items(limit=5)
            
            assert len(items) == 3
            assert all(isinstance(item, IdeaItem) for item in items)
    
    def test_fetch_respects_limit(self, gh_source, sample_github_html):
        """Fetch respects the limit parameter."""
        with patch.object(gh_source, '_fetch_page', return_value=sample_github_html):
            items = gh_source.fetch_items(limit=2)
            
            assert len(items) == 2
    
    def test_fetch_returns_empty_on_page_error(self, gh_source):
        """Page error returns empty list."""
        with patch.object(gh_source, '_fetch_page', return_value=None):
            items = gh_source.fetch_items(limit=5)
            
            assert items == []
    
    def test_fetch_network_error_returns_empty(self, gh_source):
        """Network error returns empty list gracefully."""
        with patch("src.sources.github_trending.requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            items = gh_source.fetch_items(limit=5)
            
            assert items == []


# =============================================================================
# Test Source Independence
# =============================================================================

class TestSourceIndependence:
    """Tests that sources operate independently."""
    
    def test_sources_have_different_names(self, ph_source, gh_source):
        """Each source has a unique name."""
        from src.sources.hackernews import HackerNewsSource
        
        hn_source = HackerNewsSource()
        
        names = {ph_source.name, gh_source.name, hn_source.name}
        assert len(names) == 3  # All unique
    
    def test_source_failure_does_not_affect_others(self):
        """One source failing doesn't affect other sources."""
        from src.sources.hackernews import HackerNewsSource
        
        # Create sources (PH without token to use RSS)
        hn_source = HackerNewsSource()
        ph_source = ProductHuntSource(api_token="")  # Force RSS mode
        gh_source = GitHubTrendingSource()
        
        results = {}
        
        # Mock HN to return empty (simulating network failure handled gracefully)
        with patch.object(hn_source, '_fetch_top_story_ids', return_value=[]):
            results["hn"] = hn_source.fetch_items(limit=3)
        
        # Mock PH to succeed via RSS
        mock_feed = Mock()
        mock_feed.entries = [
            {"title": "Product", "link": "https://producthunt.com/posts/p"}
        ]
        mock_feed.bozo = False
        with patch.object(ph_source, '_fetch_feed', return_value=mock_feed):
            results["ph"] = ph_source.fetch_items(limit=3)
        
        # Mock GH to succeed
        gh_html = """
        <article class="Box-row">
            <h2><a href="/test/repo">test / repo</a></h2>
            <p>Description</p>
        </article>
        """
        with patch.object(gh_source, '_fetch_page', return_value=gh_html):
            results["gh"] = gh_source.fetch_items(limit=3)
        
        # HN returned empty but others succeeded
        assert results["hn"] == []
        assert len(results["ph"]) == 1
        assert len(results["gh"]) == 1
    
    def test_items_have_correct_source_name(self):
        """Each source correctly sets source_name on items."""
        ph_source = ProductHuntSource(api_token="")  # Force RSS mode
        gh_source = GitHubTrendingSource()
        
        # Mock responses
        mock_feed = Mock()
        mock_feed.entries = [
            {"title": "Product", "link": "https://producthunt.com/posts/p"}
        ]
        mock_feed.bozo = False
        
        gh_html = """
        <article class="Box-row">
            <h2><a href="/test/repo">test / repo</a></h2>
        </article>
        """
        
        with patch.object(ph_source, '_fetch_feed', return_value=mock_feed):
            ph_items = ph_source.fetch_items(limit=1)
        
        with patch.object(gh_source, '_fetch_page', return_value=gh_html):
            gh_items = gh_source.fetch_items(limit=1)
        
        assert ph_items[0].source_name == "producthunt"
        assert gh_items[0].source_name == "github"


# =============================================================================
# Test Number Parsing Utility
# =============================================================================

class TestGitHubNumberParsing:
    """Tests for star count number parsing."""
    
    def test_parse_plain_number(self, gh_source):
        """Plain number is parsed correctly."""
        assert gh_source._parse_number("1234") == 1234
    
    def test_parse_number_with_commas(self, gh_source):
        """Number with commas is parsed correctly."""
        assert gh_source._parse_number("1,234,567") == 1234567
    
    def test_parse_number_with_k(self, gh_source):
        """Number with 'k' suffix is parsed correctly."""
        assert gh_source._parse_number("1.5k") == 1500
    
    def test_parse_number_with_text(self, gh_source):
        """Number with surrounding text is parsed correctly."""
        assert gh_source._parse_number("1,234 stars today") == 1234
    
    def test_parse_empty_string(self, gh_source):
        """Empty string returns 0."""
        assert gh_source._parse_number("") == 0

