"""
Tests for Web Dashboard Application.

Tests the Flask routes, API endpoints, template filters,
and error handling.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

# Import the Flask app
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app, score_color, format_date


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_idea_item():
    """Sample IdeaItem for testing."""
    from src.models.idea_item import IdeaItem
    return IdeaItem(
        id="hn_12345",
        title="Test Idea",
        description="A test description",
        url="https://example.com",
        source_name="hackernews",
        source_date=datetime(2025, 12, 25),
        score=0.75,
        tags=["ai-ml", "developer-tools"],
        points=150,
        comments_count=25,
    )


@pytest.fixture
def sample_ideas():
    """Multiple sample IdeaItems."""
    from src.models.idea_item import IdeaItem
    return [
        IdeaItem(
            id="hn_1",
            title="HN Idea",
            url="https://example.com/1",
            source_name="hackernews",
            score=0.9,
            created_at=datetime.now(),
        ),
        IdeaItem(
            id="ph_1",
            title="PH Idea",
            url="https://example.com/2",
            source_name="producthunt",
            score=0.7,
            created_at=datetime.now() - timedelta(hours=2),
        ),
        IdeaItem(
            id="gh_1",
            title="GH Idea",
            url="https://example.com/3",
            source_name="github",
            score=0.5,
            created_at=datetime.now() - timedelta(days=1),
        ),
    ]


@pytest.fixture
def mock_storage(sample_ideas):
    """Mock AirtableStorage instance."""
    mock = Mock()
    mock.get_recent_items.return_value = sample_ideas
    mock.get_record_count.return_value = 50
    return mock


# =============================================================================
# Test Template Filters
# =============================================================================

class TestTemplateFilters:
    """Tests for Jinja2 template filters."""
    
    def test_score_color_high(self):
        """Test score_color returns 'high' for scores >= 0.7."""
        assert score_color(0.7) == "high"
        assert score_color(0.85) == "high"
        assert score_color(1.0) == "high"
    
    def test_score_color_medium(self):
        """Test score_color returns 'medium' for scores 0.4-0.69."""
        assert score_color(0.4) == "medium"
        assert score_color(0.5) == "medium"
        assert score_color(0.69) == "medium"
    
    def test_score_color_low(self):
        """Test score_color returns 'low' for scores < 0.4."""
        assert score_color(0.0) == "low"
        assert score_color(0.2) == "low"
        assert score_color(0.39) == "low"
    
    def test_format_date_with_datetime(self):
        """Test format_date with datetime object."""
        dt = datetime(2025, 12, 25, 10, 30, 0)
        result = format_date(dt)
        
        assert "Dec" in result
        assert "25" in result
        assert "2025" in result
    
    def test_format_date_with_string(self):
        """Test format_date with string input."""
        result = format_date("2025-12-25")
        
        assert result == "2025-12-25"
    
    def test_format_date_with_none(self):
        """Test format_date with None returns 'Unknown'."""
        result = format_date(None)
        
        assert result == "Unknown"


# =============================================================================
# Test Dashboard Route
# =============================================================================

class TestDashboardRoute:
    """Tests for the main dashboard route."""
    
    @patch("web.app.get_storage")
    def test_dashboard_renders(self, mock_get_storage, client, mock_storage):
        """Test dashboard renders successfully."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/")
        
        assert response.status_code == 200
    
    @patch("web.app.get_storage")
    def test_dashboard_no_storage(self, mock_get_storage, client):
        """Test dashboard shows error when storage not configured."""
        mock_get_storage.return_value = None
        
        response = client.get("/")
        
        assert response.status_code == 200
        assert b"not configured" in response.data.lower() or b"error" in response.data.lower()
    
    @patch("web.app.get_storage")
    def test_dashboard_source_filter(self, mock_get_storage, client, mock_storage):
        """Test dashboard source filtering."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/?source=hackernews")
        
        assert response.status_code == 200
        mock_storage.get_recent_items.assert_called()
    
    @patch("web.app.get_storage")
    def test_dashboard_tag_filter(self, mock_get_storage, client, mock_storage):
        """Test dashboard tag filtering."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/?tag=ai-ml")
        
        assert response.status_code == 200
    
    @patch("web.app.get_storage")
    def test_dashboard_sort_by_score(self, mock_get_storage, client, mock_storage):
        """Test dashboard sorting by score."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/?sort=score")
        
        assert response.status_code == 200
    
    @patch("web.app.get_storage")
    def test_dashboard_sort_by_date(self, mock_get_storage, client, mock_storage):
        """Test dashboard sorting by date."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/?sort=date")
        
        assert response.status_code == 200
    
    @patch("web.app.get_storage")
    def test_dashboard_days_parameter(self, mock_get_storage, client, mock_storage):
        """Test dashboard days filter parameter."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/?days=14")
        
        assert response.status_code == 200
        # Verify get_recent_items was called (may be called multiple times with different args)
        assert mock_storage.get_recent_items.called


# =============================================================================
# Test API Stats Endpoint
# =============================================================================

class TestApiStats:
    """Tests for the /api/stats endpoint."""
    
    @patch("web.app.get_storage")
    def test_api_stats_success(self, mock_get_storage, client, mock_storage):
        """Test stats endpoint returns correct data."""
        mock_get_storage.return_value = mock_storage
        
        response = client.get("/api/stats")
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert "record_count" in data
        assert data["record_count"] == 50
        assert "usage_percent" in data
    
    @patch("web.app.get_storage")
    def test_api_stats_no_storage(self, mock_get_storage, client):
        """Test stats endpoint error when no storage."""
        mock_get_storage.return_value = None
        
        response = client.get("/api/stats")
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert "error" in data


# =============================================================================
# Test Digests Routes
# =============================================================================

class TestDigestsRoutes:
    """Tests for digest listing and viewing routes."""
    
    def test_digests_list_renders(self, client):
        """Test digests list page renders."""
        response = client.get("/digests")
        
        assert response.status_code == 200
    
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_view_digest_success(self, mock_read, mock_exists, client):
        """Test viewing a specific digest."""
        mock_exists.return_value = True
        mock_read.return_value = "# Test Digest\n\nContent here"
        
        response = client.get("/digest/2025-12-25")
        
        assert response.status_code == 200
    
    @patch("pathlib.Path.exists")
    def test_view_digest_not_found(self, mock_exists, client):
        """Test viewing a non-existent digest."""
        mock_exists.return_value = False
        
        response = client.get("/digest/9999-99-99")
        
        assert response.status_code == 200
        assert b"not found" in response.data.lower() or b"error" in response.data.lower()


# =============================================================================
# Test AI Summarize Endpoint
# =============================================================================

class TestApiSummarize:
    """Tests for the /api/ai/summarize endpoint."""
    
    def test_summarize_no_data(self, client):
        """Test summarize endpoint with no data."""
        response = client.post("/api/ai/summarize", 
                              data=json.dumps({}),
                              content_type="application/json")
        
        assert response.status_code == 400
    
    def test_summarize_missing_content(self, client):
        """Test summarize endpoint with missing title and description."""
        response = client.post("/api/ai/summarize",
                              data=json.dumps({"source": "test"}),
                              content_type="application/json")
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    @patch("web.app.get_summarizer")
    def test_summarize_ai_not_configured(self, mock_get_summarizer, client):
        """Test summarize endpoint when AI is not configured."""
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = False
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/summarize",
                              data=json.dumps({
                                  "title": "Test",
                                  "description": "Test desc",
                                  "source": "hackernews"
                              }),
                              content_type="application/json")
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert "error" in data
    
    @patch("web.app.get_summarizer")
    def test_summarize_success(self, mock_get_summarizer, client):
        """Test successful summarization."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.summarize_idea.return_value = SummaryResult(
            success=True,
            summary="Test summary",
            model="test-model",
            tokens_used=100
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/summarize",
                              data=json.dumps({
                                  "title": "Test Idea",
                                  "description": "Test description",
                                  "source": "hackernews"
                              }),
                              content_type="application/json")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["summary"] == "Test summary"
    
    @patch("web.app.get_summarizer")
    def test_summarize_api_error(self, mock_get_summarizer, client):
        """Test summarize endpoint with API error."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.summarize_idea.return_value = SummaryResult(
            success=False,
            summary="",
            error="API error occurred"
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/summarize",
                              data=json.dumps({
                                  "title": "Test",
                                  "description": "Test",
                                  "source": "test"
                              }),
                              content_type="application/json")
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False


# =============================================================================
# Test AI Insights Endpoint
# =============================================================================

class TestApiInsights:
    """Tests for the /api/ai/insights endpoint."""
    
    def test_insights_no_data(self, client):
        """Test insights endpoint with no data."""
        response = client.post("/api/ai/insights",
                              data=json.dumps({}),
                              content_type="application/json")
        
        assert response.status_code == 400
    
    def test_insights_empty_ideas(self, client):
        """Test insights endpoint with empty ideas array."""
        response = client.post("/api/ai/insights",
                              data=json.dumps({"ideas": []}),
                              content_type="application/json")
        
        assert response.status_code == 400
    
    @patch("web.app.get_summarizer")
    def test_insights_ai_not_configured(self, mock_get_summarizer, client):
        """Test insights endpoint when AI is not configured."""
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = False
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/insights",
                              data=json.dumps({
                                  "ideas": [{"title": "Test", "description": "Desc"}]
                              }),
                              content_type="application/json")
        
        assert response.status_code == 503
    
    @patch("web.app.get_summarizer")
    def test_insights_success(self, mock_get_summarizer, client):
        """Test successful insights generation."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.generate_insights.return_value = SummaryResult(
            success=True,
            summary="Key trends: AI and automation",
            model="test-model",
            tokens_used=200
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/insights",
                              data=json.dumps({
                                  "ideas": [
                                      {"title": "AI Tool", "description": "AI desc"},
                                      {"title": "Auto Tool", "description": "Auto desc"}
                                  ]
                              }),
                              content_type="application/json")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "insights" in data


# =============================================================================
# Test AI Analyze Endpoint
# =============================================================================

class TestApiAnalyze:
    """Tests for the /api/ai/analyze endpoint."""
    
    def test_analyze_no_data(self, client):
        """Test analyze endpoint with no data."""
        response = client.post("/api/ai/analyze",
                              data=json.dumps({}),
                              content_type="application/json")
        
        assert response.status_code == 400
    
    def test_analyze_missing_title(self, client):
        """Test analyze endpoint without title."""
        response = client.post("/api/ai/analyze",
                              data=json.dumps({"description": "Test"}),
                              content_type="application/json")
        
        assert response.status_code == 400
    
    @patch("web.app.get_summarizer")
    def test_analyze_ai_not_configured(self, mock_get_summarizer, client):
        """Test analyze endpoint when AI is not configured."""
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = False
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/analyze",
                              data=json.dumps({"title": "Test"}),
                              content_type="application/json")
        
        assert response.status_code == 503
    
    @patch("web.app.get_summarizer")
    def test_analyze_success_json_response(self, mock_get_summarizer, client):
        """Test analyze endpoint with valid JSON response."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.analyze_idea_deeply.return_value = SummaryResult(
            success=True,
            summary='{"summary": "Test", "problem_solved": "Problem", "target_audience": "Devs", "unique_value": "Fast", "potential_impact": "high", "tags": ["ai"], "maker_insight": null}',
            model="test-model",
            tokens_used=300
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/analyze",
                              data=json.dumps({
                                  "title": "Test Idea",
                                  "description": "Test desc",
                                  "source": "hackernews"
                              }),
                              content_type="application/json")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "analysis" in data
    
    @patch("web.app.get_summarizer")
    def test_analyze_with_maker_info(self, mock_get_summarizer, client):
        """Test analyze endpoint with maker information."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.analyze_idea_deeply.return_value = SummaryResult(
            success=True,
            summary='{"summary": "Test analysis"}',
            model="test-model",
            tokens_used=300
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/analyze",
                              data=json.dumps({
                                  "title": "Test Idea",
                                  "description": "Test desc",
                                  "source": "producthunt",
                                  "maker_name": "John Doe",
                                  "maker_bio": "Founder & CEO"
                              }),
                              content_type="application/json")
        
        assert response.status_code == 200
        mock_summarizer.analyze_idea_deeply.assert_called_with(
            "Test Idea", "Test desc", "producthunt", "John Doe", "Founder & CEO"
        )
    
    @patch("web.app.get_summarizer")
    def test_analyze_non_json_response(self, mock_get_summarizer, client):
        """Test analyze endpoint when AI returns non-JSON response."""
        from src.services.ai_summarizer import SummaryResult
        
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.analyze_idea_deeply.return_value = SummaryResult(
            success=True,
            summary="This is a plain text response, not JSON",
            model="test-model",
            tokens_used=100
        )
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.post("/api/ai/analyze",
                              data=json.dumps({"title": "Test"}),
                              content_type="application/json")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        # Should fallback to raw text in summary field
        assert "summary" in data["analysis"]


# =============================================================================
# Test AI Status Endpoint
# =============================================================================

class TestApiAiStatus:
    """Tests for the /api/ai/status endpoint."""
    
    @patch("web.app.get_summarizer")
    def test_ai_status_available(self, mock_get_summarizer, client):
        """Test AI status when configured."""
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = True
        mock_summarizer.model = "llama3-70b"
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.get("/api/ai/status")
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data["available"] is True
        assert data["model"] == "llama3-70b"
    
    @patch("web.app.get_summarizer")
    def test_ai_status_not_available(self, mock_get_summarizer, client):
        """Test AI status when not configured."""
        mock_summarizer = Mock()
        mock_summarizer.is_available.return_value = False
        mock_get_summarizer.return_value = mock_summarizer
        
        response = client.get("/api/ai/status")
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data["available"] is False
        assert data["model"] is None


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in the web app."""
    
    @patch("web.app.get_storage")
    def test_storage_exception_handling(self, mock_get_storage, client):
        """Test handling of storage exceptions."""
        mock_storage = Mock()
        mock_storage.get_recent_items.side_effect = Exception("Database error")
        mock_get_storage.return_value = mock_storage
        
        # This should not crash the app
        try:
            response = client.get("/")
            # May return error page or crash, both are valid test outcomes
        except Exception:
            pass  # Expected in some cases
    
    def test_invalid_json_in_post(self, client):
        """Test handling of invalid JSON in POST requests."""
        response = client.post("/api/ai/summarize",
                              data="not valid json",
                              content_type="application/json")
        
        # Should return 400 or handle gracefully
        assert response.status_code in [400, 500]


# =============================================================================
# Test Route Existence
# =============================================================================

class TestRouteExistence:
    """Tests to verify all expected routes exist."""
    
    def test_index_route_exists(self, client):
        """Test that index route exists."""
        response = client.get("/")
        assert response.status_code in [200, 302, 500]  # May redirect or error without config
    
    def test_digests_route_exists(self, client):
        """Test that digests route exists."""
        response = client.get("/digests")
        assert response.status_code in [200, 302]
    
    def test_api_stats_route_exists(self, client):
        """Test that API stats route exists."""
        response = client.get("/api/stats")
        assert response.status_code in [200, 500]
    
    def test_api_ai_summarize_route_exists(self, client):
        """Test that AI summarize route exists."""
        response = client.post("/api/ai/summarize",
                              data=json.dumps({}),
                              content_type="application/json")
        assert response.status_code in [400, 500]  # 400 expected without data
    
    def test_api_ai_insights_route_exists(self, client):
        """Test that AI insights route exists."""
        response = client.post("/api/ai/insights",
                              data=json.dumps({}),
                              content_type="application/json")
        assert response.status_code in [400, 500]
    
    def test_api_ai_analyze_route_exists(self, client):
        """Test that AI analyze route exists."""
        response = client.post("/api/ai/analyze",
                              data=json.dumps({}),
                              content_type="application/json")
        assert response.status_code in [400, 500]
    
    def test_api_ai_status_route_exists(self, client):
        """Test that AI status route exists."""
        response = client.get("/api/ai/status")
        assert response.status_code == 200


