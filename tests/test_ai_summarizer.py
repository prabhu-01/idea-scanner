"""
Tests for AI Summarization Service.

Tests the AISummarizer class, SummaryResult dataclass,
API interactions, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from src.services.ai_summarizer import (
    AISummarizer,
    SummaryResult,
    get_summarizer,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def summarizer_with_key():
    """AISummarizer with a test API key."""
    return AISummarizer(api_key="test_api_key", model="test-model")


@pytest.fixture
def summarizer_without_key():
    """AISummarizer without an API key."""
    # Use a sentinel value that evaluates to False but doesn't fallback to env
    summarizer = AISummarizer(api_key="", model="test-model")
    # Force the api_key to empty string (bypassing fallback logic)
    summarizer.api_key = ""
    return summarizer


@pytest.fixture
def mock_successful_response():
    """Mock successful API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "This is a test summary."
                }
            }
        ],
        "usage": {
            "total_tokens": 150
        }
    }
    return mock_response


@pytest.fixture
def mock_error_response():
    """Mock API error response."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "error": {
            "message": "Invalid API key"
        }
    }
    return mock_response


@pytest.fixture
def sample_idea():
    """Sample idea data for testing."""
    return {
        "title": "AI-Powered Code Assistant",
        "description": "A revolutionary tool that helps developers write better code using machine learning algorithms.",
        "source": "producthunt",
    }


@pytest.fixture
def sample_ideas_list():
    """Multiple ideas for insights testing."""
    return [
        {
            "title": "AI Code Helper",
            "description": "Helps with coding",
            "source": "hackernews",
        },
        {
            "title": "New Python Framework",
            "description": "Fast async framework",
            "source": "github",
        },
        {
            "title": "Productivity App",
            "description": "Task management tool",
            "source": "producthunt",
        },
    ]


# =============================================================================
# Test SummaryResult Dataclass
# =============================================================================

class TestSummaryResult:
    """Tests for the SummaryResult dataclass."""
    
    def test_summary_result_success_creation(self):
        """Test creating a successful SummaryResult."""
        result = SummaryResult(
            success=True,
            summary="Test summary",
            model="test-model",
            tokens_used=100
        )
        
        assert result.success is True
        assert result.summary == "Test summary"
        assert result.model == "test-model"
        assert result.tokens_used == 100
        assert result.error is None
    
    def test_summary_result_error_creation(self):
        """Test creating an error SummaryResult."""
        result = SummaryResult(
            success=False,
            summary="",
            error="API error"
        )
        
        assert result.success is False
        assert result.summary == ""
        assert result.error == "API error"
    
    def test_summary_result_defaults(self):
        """Test default values in SummaryResult."""
        result = SummaryResult(success=True, summary="Test")
        
        assert result.error is None
        assert result.model is None
        assert result.tokens_used == 0
    
    def test_summary_result_to_dict(self):
        """Test converting SummaryResult to dictionary."""
        result = SummaryResult(
            success=True,
            summary="Test",
            model="test-model",
            tokens_used=50
        )
        
        result_dict = asdict(result)
        
        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["summary"] == "Test"


# =============================================================================
# Test AISummarizer Initialization
# =============================================================================

class TestAISummarizerInit:
    """Tests for AISummarizer initialization."""
    
    def test_init_with_explicit_values(self):
        """Test initialization with explicit API key and model."""
        summarizer = AISummarizer(api_key="test_key", model="custom-model")
        
        assert summarizer.api_key == "test_key"
        assert summarizer.model == "custom-model"
    
    def test_init_with_empty_key(self):
        """Test initialization with empty API key (forced)."""
        summarizer = AISummarizer(api_key="", model="test-model")
        # Force empty key to test behavior (init may fallback to env)
        summarizer.api_key = ""
        
        assert summarizer.api_key == ""
        assert summarizer.is_available() is False
    
    @patch("src.services.ai_summarizer.GROQ_API_KEY", "env_api_key")
    @patch("src.services.ai_summarizer.GROQ_MODEL", "env_model")
    def test_init_from_environment(self):
        """Test initialization uses environment variables as defaults."""
        summarizer = AISummarizer()
        
        assert summarizer.api_key == "env_api_key"
        assert summarizer.model == "env_model"
    
    def test_api_url_constant(self):
        """Test API URL is correctly set."""
        assert AISummarizer.API_URL == "https://api.groq.com/openai/v1/chat/completions"


# =============================================================================
# Test is_available Method
# =============================================================================

class TestIsAvailable:
    """Tests for the is_available method."""
    
    def test_is_available_with_key(self, summarizer_with_key):
        """Test is_available returns True when API key is set."""
        assert summarizer_with_key.is_available() is True
    
    def test_is_available_without_key(self, summarizer_without_key):
        """Test is_available returns False when API key is empty."""
        assert summarizer_without_key.is_available() is False
    
    def test_is_available_with_none_key(self):
        """Test is_available with None API key."""
        summarizer = AISummarizer(api_key=None, model="test")
        # Will use default from config, which may be empty
        # This tests the bool conversion
        assert isinstance(summarizer.is_available(), bool)


# =============================================================================
# Test summarize_idea Method
# =============================================================================

class TestSummarizeIdea:
    """Tests for the summarize_idea method."""
    
    def test_summarize_returns_error_when_not_available(self, summarizer_without_key, sample_idea):
        """Test summarize_idea returns error when AI is not configured."""
        result = summarizer_without_key.summarize_idea(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is False
        assert "not configured" in result.error.lower()
    
    @patch("requests.post")
    def test_summarize_success(self, mock_post, summarizer_with_key, mock_successful_response, sample_idea):
        """Test successful summarization."""
        mock_post.return_value = mock_successful_response
        
        result = summarizer_with_key.summarize_idea(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is True
        assert result.summary == "This is a test summary."
        assert result.tokens_used == 150
    
    @patch("requests.post")
    def test_summarize_api_error(self, mock_post, summarizer_with_key, mock_error_response, sample_idea):
        """Test handling of API error response."""
        mock_post.return_value = mock_error_response
        
        result = summarizer_with_key.summarize_idea(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is False
        assert "401" in result.error or "Invalid" in result.error
    
    @patch("requests.post")
    def test_summarize_network_error(self, mock_post, summarizer_with_key, sample_idea):
        """Test handling of network errors."""
        mock_post.side_effect = Exception("Network error")
        
        result = summarizer_with_key.summarize_idea(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is False
        assert "error" in result.error.lower()
    
    @patch("requests.post")
    def test_summarize_request_format(self, mock_post, summarizer_with_key, mock_successful_response, sample_idea):
        """Test the format of the API request."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key.summarize_idea(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        # Verify the call was made
        mock_post.assert_called_once()
        
        # Check request format
        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer test_api_key"
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"
        
        payload = call_args.kwargs["json"]
        assert payload["model"] == "test-model"
        assert "messages" in payload
        assert len(payload["messages"]) == 2  # system + user


# =============================================================================
# Test generate_insights Method
# =============================================================================

class TestGenerateInsights:
    """Tests for the generate_insights method."""
    
    def test_insights_returns_error_when_not_available(self, summarizer_without_key, sample_ideas_list):
        """Test generate_insights returns error when AI is not configured."""
        result = summarizer_without_key.generate_insights(sample_ideas_list)
        
        assert result.success is False
        assert "not configured" in result.error.lower()
    
    @patch("requests.post")
    def test_insights_success(self, mock_post, summarizer_with_key, mock_successful_response, sample_ideas_list):
        """Test successful insights generation."""
        mock_post.return_value = mock_successful_response
        
        result = summarizer_with_key.generate_insights(sample_ideas_list)
        
        assert result.success is True
        assert result.summary == "This is a test summary."
    
    @patch("requests.post")
    def test_insights_limits_ideas(self, mock_post, summarizer_with_key, mock_successful_response):
        """Test that insights limit the number of ideas to 15."""
        mock_post.return_value = mock_successful_response
        
        # Create 20 ideas
        many_ideas = [{"title": f"Idea {i}", "description": f"Desc {i}", "source": "test"} for i in range(20)]
        
        summarizer_with_key.generate_insights(many_ideas)
        
        # Verify the prompt only includes up to 15 ideas
        call_args = mock_post.call_args
        prompt = call_args.kwargs["json"]["messages"][1]["content"]
        
        # Count the number of ideas in the prompt
        idea_count = prompt.count("- [")
        assert idea_count <= 15


# =============================================================================
# Test analyze_idea_deeply Method
# =============================================================================

class TestAnalyzeIdeaDeeply:
    """Tests for the analyze_idea_deeply method."""
    
    def test_analyze_returns_error_when_not_available(self, summarizer_without_key, sample_idea):
        """Test analyze_idea_deeply returns error when AI is not configured."""
        result = summarizer_without_key.analyze_idea_deeply(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is False
        assert "not configured" in result.error.lower()
    
    @patch("requests.post")
    def test_analyze_success(self, mock_post, summarizer_with_key, sample_idea):
        """Test successful deep analysis."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"summary": "Test analysis"}'}}],
            "usage": {"total_tokens": 200}
        }
        mock_post.return_value = mock_response
        
        result = summarizer_with_key.analyze_idea_deeply(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is True
    
    @patch("requests.post")
    def test_analyze_with_maker_info(self, mock_post, summarizer_with_key, mock_successful_response, sample_idea):
        """Test analysis includes maker information in prompt."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key.analyze_idea_deeply(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"],
            maker_name="John Doe",
            maker_bio="Serial entrepreneur"
        )
        
        call_args = mock_post.call_args
        prompt = call_args.kwargs["json"]["messages"][1]["content"]
        
        assert "John Doe" in prompt
        assert "Serial entrepreneur" in prompt
    
    @patch("requests.post")
    def test_analyze_without_maker_info(self, mock_post, summarizer_with_key, mock_successful_response, sample_idea):
        """Test analysis works without maker information."""
        mock_post.return_value = mock_successful_response
        
        result = summarizer_with_key.analyze_idea_deeply(
            sample_idea["title"],
            sample_idea["description"],
            sample_idea["source"]
        )
        
        assert result.success is True


# =============================================================================
# Test Prompt Building Methods
# =============================================================================

class TestPromptBuilding:
    """Tests for internal prompt building methods."""
    
    def test_summary_prompt_includes_title(self, summarizer_with_key):
        """Test summary prompt includes the title."""
        prompt = summarizer_with_key._build_summary_prompt(
            "Test Title",
            "Test Description",
            "hackernews"
        )
        
        assert "Test Title" in prompt
    
    def test_summary_prompt_includes_description(self, summarizer_with_key):
        """Test summary prompt includes the description."""
        prompt = summarizer_with_key._build_summary_prompt(
            "Test Title",
            "Test Description",
            "hackernews"
        )
        
        assert "Test Description" in prompt
    
    def test_summary_prompt_source_context_hackernews(self, summarizer_with_key):
        """Test source context for Hacker News."""
        prompt = summarizer_with_key._build_summary_prompt(
            "Test", "Test", "hackernews"
        )
        
        assert "Hacker News" in prompt or "tech/startup" in prompt
    
    def test_summary_prompt_source_context_producthunt(self, summarizer_with_key):
        """Test source context for Product Hunt."""
        prompt = summarizer_with_key._build_summary_prompt(
            "Test", "Test", "producthunt"
        )
        
        assert "Product Hunt" in prompt or "product/tool" in prompt
    
    def test_summary_prompt_source_context_github(self, summarizer_with_key):
        """Test source context for GitHub."""
        prompt = summarizer_with_key._build_summary_prompt(
            "Test", "Test", "github"
        )
        
        assert "GitHub" in prompt or "open source" in prompt
    
    def test_summary_prompt_truncates_long_description(self, summarizer_with_key):
        """Test that long descriptions are truncated."""
        long_description = "x" * 3000
        
        prompt = summarizer_with_key._build_summary_prompt(
            "Test",
            long_description,
            "hackernews"
        )
        
        # Description should be truncated to 1500 characters
        assert len(prompt) < len(long_description)
    
    def test_insights_prompt_includes_ideas(self, summarizer_with_key, sample_ideas_list):
        """Test insights prompt includes all ideas."""
        prompt = summarizer_with_key._build_insights_prompt(sample_ideas_list)
        
        for idea in sample_ideas_list:
            assert idea["title"] in prompt


# =============================================================================
# Test API Call Method
# =============================================================================

class TestApiCall:
    """Tests for the _call_api method."""
    
    @patch("requests.post")
    def test_api_call_uses_correct_headers(self, mock_post, summarizer_with_key, mock_successful_response):
        """Test API call uses correct authorization header."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key._call_api("Test prompt")
        
        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]
        
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["Content-Type"] == "application/json"
    
    @patch("requests.post")
    def test_api_call_uses_correct_model(self, mock_post, summarizer_with_key, mock_successful_response):
        """Test API call uses the configured model."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key._call_api("Test prompt")
        
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        
        assert payload["model"] == "test-model"
    
    @patch("requests.post")
    def test_api_call_respects_max_tokens(self, mock_post, summarizer_with_key, mock_successful_response):
        """Test API call respects max_tokens parameter."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key._call_api("Test prompt", max_tokens=500)
        
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        
        assert payload["max_tokens"] == 500
    
    @patch("requests.post")
    def test_api_call_timeout(self, mock_post, summarizer_with_key, mock_successful_response):
        """Test API call has a timeout."""
        mock_post.return_value = mock_successful_response
        
        summarizer_with_key._call_api("Test prompt")
        
        call_args = mock_post.call_args
        assert call_args.kwargs["timeout"] == 30
    
    @patch("requests.post")
    def test_api_call_strips_whitespace(self, mock_post, summarizer_with_key):
        """Test API response has whitespace stripped."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  Test summary with spaces  "}}],
            "usage": {"total_tokens": 50}
        }
        mock_post.return_value = mock_response
        
        result = summarizer_with_key._call_api("Test prompt")
        
        assert result.summary == "Test summary with spaces"


# =============================================================================
# Test Singleton Pattern
# =============================================================================

class TestSingleton:
    """Tests for the get_summarizer singleton function."""
    
    def test_get_summarizer_returns_instance(self):
        """Test get_summarizer returns an AISummarizer instance."""
        summarizer = get_summarizer()
        
        assert isinstance(summarizer, AISummarizer)
    
    def test_get_summarizer_returns_same_instance(self):
        """Test get_summarizer returns the same instance on multiple calls."""
        # Reset the singleton for clean test
        import src.services.ai_summarizer as module
        module._summarizer = None
        
        first = get_summarizer()
        second = get_summarizer()
        
        assert first is second
    
    def test_get_summarizer_is_usable(self):
        """Test the singleton instance has expected methods."""
        summarizer = get_summarizer()
        
        assert hasattr(summarizer, "is_available")
        assert hasattr(summarizer, "summarize_idea")
        assert hasattr(summarizer, "generate_insights")
        assert hasattr(summarizer, "analyze_idea_deeply")


# =============================================================================
# Integration-Style Tests (Still Mocked)
# =============================================================================

class TestIntegrationScenarios:
    """Tests for common usage scenarios."""
    
    @patch("requests.post")
    def test_full_summarization_workflow(self, mock_post, summarizer_with_key):
        """Test a complete summarization workflow."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Great AI tool for developers."}}],
            "usage": {"total_tokens": 100}
        }
        mock_post.return_value = mock_response
        
        # Check availability
        assert summarizer_with_key.is_available() is True
        
        # Summarize an idea
        result = summarizer_with_key.summarize_idea(
            "AI Code Assistant",
            "Helps developers write better code",
            "producthunt"
        )
        
        assert result.success is True
        assert len(result.summary) > 0
        assert result.tokens_used > 0
    
    @patch("requests.post")
    def test_error_recovery(self, mock_post, summarizer_with_key):
        """Test that errors don't break subsequent calls."""
        # First call fails
        mock_post.side_effect = Exception("Network error")
        
        result1 = summarizer_with_key.summarize_idea("Test", "Desc", "test")
        assert result1.success is False
        
        # Reset mock for success
        mock_post.side_effect = None
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Success"}}],
            "usage": {"total_tokens": 50}
        }
        
        # Second call should succeed
        result2 = summarizer_with_key.summarize_idea("Test", "Desc", "test")
        assert result2.success is True


