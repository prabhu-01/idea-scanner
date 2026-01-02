"""
Idea Digest - Web Dashboard

A simple Flask-based dashboard to browse ideas from Airtable.

Run with: python -m web.app
Or: cd web && python app.py
"""

import sys
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from src.storage.airtable import AirtableStorage
from src.services.ai_summarizer import get_summarizer
from src.pipeline import run_pipeline, PipelineResult
from src.config import (
    AIRTABLE_API_KEY,
    AIRTABLE_MAX_RECORDS,
    AIRTABLE_RETENTION_DAYS,
    GROQ_API_KEY,
    DEFAULT_LIMIT_PER_SOURCE,
)

app = Flask(__name__)


# =============================================================================
# Pipeline Status Tracking
# =============================================================================

@dataclass
class PipelineStatus:
    """Tracks the status of a pipeline run."""
    running: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str = "idle"  # idle, running, completed, failed
    message: str = ""
    result: Optional[dict] = None
    logs: list = None  # Terminal-style log messages
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []
    
    def log(self, message: str, level: str = "info"):
        """Add a log entry with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append({
            "time": timestamp,
            "level": level,  # info, success, warning, error
            "message": message
        })

# Global pipeline status (simple in-memory tracking)
_pipeline_status = PipelineStatus()

def get_storage():
    """Get configured Airtable storage."""
    if not AIRTABLE_API_KEY:
        return None
    return AirtableStorage()


@app.route("/")
def index():
    """Main dashboard page."""
    storage = get_storage()
    
    if not storage:
        return render_template("error.html", message="Airtable not configured")
    
    # Get filter parameters
    source_filter = request.args.get("source", "all")
    tag_filter = request.args.get("tag", "all")
    sort_by = request.args.get("sort", "score")
    days = int(request.args.get("days", 7))
    
    # Fetch items
    items = storage.get_recent_items(days=days)
    
    # Apply filters
    if source_filter != "all":
        items = [i for i in items if i.source_name == source_filter]
    
    if tag_filter != "all":
        items = [i for i in items if tag_filter in (i.tags or [])]
    
    # Sort
    if sort_by == "score":
        items.sort(key=lambda x: x.score, reverse=True)
    elif sort_by == "date":
        items.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
    elif sort_by == "source":
        items.sort(key=lambda x: x.source_name)
    
    # Get unique sources and tags for filters
    all_items = storage.get_recent_items(days=30)
    sources = sorted(set(i.source_name for i in all_items))
    tags = sorted(set(tag for i in all_items for tag in (i.tags or [])))
    
    # Get stats
    record_count = storage.get_record_count()
    
    # Get last sync time from pipeline (regardless of success/failure)
    last_updated = None
    
    if _pipeline_status.finished_at:
        # Pipeline has run in this session - use that time
        try:
            diff = datetime.now() - _pipeline_status.finished_at
            total_seconds = int(diff.total_seconds())
            
            if total_seconds < 60:
                last_updated = "just now"
            elif total_seconds < 3600:
                last_updated = f"{total_seconds // 60}m ago"
            elif total_seconds < 86400:
                last_updated = f"{total_seconds // 3600}h ago"
            else:
                last_updated = f"{diff.days}d ago"
        except Exception:
            last_updated = "recently"
    else:
        # Pipeline hasn't run yet in this session - show "ready" or count
        if all_items:
            last_updated = f"{len(all_items)} ideas loaded"
        else:
            last_updated = "ready"
    
    return render_template(
        "index.html",
        items=items,
        sources=sources,
        tags=tags,
        current_source=source_filter,
        current_tag=tag_filter,
        current_sort=sort_by,
        current_days=days,
        record_count=record_count,
        max_records=AIRTABLE_MAX_RECORDS,
        retention_days=AIRTABLE_RETENTION_DAYS,
        last_updated=last_updated,
    )


@app.route("/api/stats")
def api_stats():
    """API endpoint for storage stats."""
    storage = get_storage()
    
    if not storage:
        return jsonify({"error": "Airtable not configured"}), 500
    
    count = storage.get_record_count()
    
    return jsonify({
        "record_count": count,
        "max_records": AIRTABLE_MAX_RECORDS,
        "free_tier_limit": 1200,
        "usage_percent": round(count / 1200 * 100, 1),
    })


@app.route("/digests")
def digests():
    """List available digest files."""
    digests_dir = Path(__file__).parent.parent / "digests"
    
    digest_files = []
    if digests_dir.exists():
        for f in sorted(digests_dir.glob("*.md"), reverse=True):
            digest_files.append({
                "name": f.stem,
                "path": f.name,
                "date": f.stem,
            })
    
    return render_template("digests.html", digests=digest_files)


@app.route("/digest/<date>")
def view_digest(date):
    """View a specific digest."""
    digests_dir = Path(__file__).parent.parent / "digests"
    digest_path = digests_dir / f"{date}.md"
    
    if not digest_path.exists():
        return render_template("error.html", message=f"Digest not found: {date}")
    
    content = digest_path.read_text()
    
    # Convert markdown to HTML (simple conversion)
    import re
    html_content = content
    
    # Headers
    html_content = re.sub(r'^### \*\*\[(.+?)\]\*\* \[(.+?)\]\((.+?)\)', r'<h4><span class="score">[\1]</span> <a href="\3" target="_blank">\2</a></h4>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    
    # Bold and italic
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_content)
    
    # Links
    html_content = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank">\1</a>', html_content)
    
    # Code/tags
    html_content = re.sub(r'`(.+?)`', r'<code>\1</code>', html_content)
    
    # Blockquotes
    html_content = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html_content, flags=re.MULTILINE)
    
    # Line breaks
    html_content = re.sub(r'\n\n', r'</p><p>', html_content)
    html_content = f'<p>{html_content}</p>'
    
    return render_template("digest.html", date=date, content=html_content)


@app.route("/api/ai/summarize", methods=["POST"])
def api_summarize():
    """AI summarization endpoint for a single idea."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    title = data.get("title", "")
    description = data.get("description", "")
    source = data.get("source", "unknown")
    
    if not title and not description:
        return jsonify({"error": "Title or description required"}), 400
    
    summarizer = get_summarizer()
    
    if not summarizer.is_available():
        return jsonify({
            "error": "AI not configured",
            "message": "Add GROQ_API_KEY to .env file"
        }), 503
    
    result = summarizer.summarize_idea(title, description, source)
    
    if result.success:
        return jsonify({
            "success": True,
            "summary": result.summary,
            "model": result.model,
            "tokens": result.tokens_used
        })
    else:
        return jsonify({
            "success": False,
            "error": result.error
        }), 500


@app.route("/api/ai/insights", methods=["POST"])
def api_insights():
    """Generate insights from multiple ideas."""
    data = request.get_json()
    
    if not data or "ideas" not in data:
        return jsonify({"error": "Ideas array required"}), 400
    
    ideas = data.get("ideas", [])
    
    if not ideas:
        return jsonify({"error": "At least one idea required"}), 400
    
    summarizer = get_summarizer()
    
    if not summarizer.is_available():
        return jsonify({
            "error": "AI not configured",
            "message": "Add GROQ_API_KEY to .env file"
        }), 503
    
    result = summarizer.generate_insights(ideas)
    
    if result.success:
        return jsonify({
            "success": True,
            "insights": result.summary,
            "model": result.model,
            "tokens": result.tokens_used
        })
    else:
        return jsonify({
            "success": False,
            "error": result.error
        }), 500


@app.route("/api/ai/analyze", methods=["POST"])
def api_analyze():
    """Deep AI analysis of an idea with maker context."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    title = data.get("title", "")
    description = data.get("description", "")
    source = data.get("source", "unknown")
    maker_name = data.get("maker_name")
    maker_bio = data.get("maker_bio")
    
    if not title:
        return jsonify({"error": "Title required"}), 400
    
    summarizer = get_summarizer()
    
    if not summarizer.is_available():
        return jsonify({
            "error": "AI not configured",
            "message": "Add GROQ_API_KEY to .env file"
        }), 503
    
    result = summarizer.analyze_idea_deeply(
        title, description, source, maker_name, maker_bio
    )
    
    if result.success:
        # Try to parse JSON from the response
        import json
        try:
            analysis = json.loads(result.summary)
            return jsonify({
                "success": True,
                "analysis": analysis,
                "model": result.model,
                "tokens": result.tokens_used
            })
        except json.JSONDecodeError:
            # Fallback to raw text if JSON parsing fails
            return jsonify({
                "success": True,
                "analysis": {"summary": result.summary},
                "model": result.model,
                "tokens": result.tokens_used
            })
    else:
        return jsonify({
            "success": False,
            "error": result.error
        }), 500


@app.route("/api/ai/status")
def api_ai_status():
    """Check if AI summarization is available."""
    summarizer = get_summarizer()
    return jsonify({
        "available": summarizer.is_available(),
        "model": summarizer.model if summarizer.is_available() else None
    })


@app.route("/api/search")
def api_search():
    """Search for ideas matching a query."""
    storage = get_storage()
    
    if not storage:
        return jsonify({"error": "Airtable not configured"}), 500
    
    query = request.args.get("q", "").strip()
    source = request.args.get("source", None)
    limit = min(int(request.args.get("limit", 50)), 100)  # Cap at 100
    
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    if source == "all":
        source = None
    
    items = storage.search_items(query=query, limit=limit, source_filter=source)
    
    # Convert items to JSON-serializable format
    results = []
    for item in items:
        results.append({
            "id": item.id,
            "title": item.title,
            "description": item.description or "",
            "url": item.url,
            "source_name": item.source_name,
            "score": item.score,
            "tags": item.tags or [],
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "points": item.points,
            "votes": item.votes,
            "stars": item.stars,
            "comments_count": item.comments_count,
            "maker_name": item.maker_name,
            "maker_avatar": item.maker_avatar,
        })
    
    return jsonify({
        "success": True,
        "query": query,
        "count": len(results),
        "results": results,
    })


# =============================================================================
# Pipeline API Endpoints
# =============================================================================

def _run_pipeline_async(limit: int):
    """Run pipeline in background thread with terminal-style logging."""
    global _pipeline_status
    import time
    
    try:
        _pipeline_status.status = "running"
        _pipeline_status.log("$ idea-digest --run", "cmd")
        _pipeline_status.log("Initializing Idea Digest Pipeline v1.0", "info")
        time.sleep(0.3)
        
        _pipeline_status.log(f"Config: limit_per_source={limit}, dry_run=false", "info")
        _pipeline_status.message = "Connecting to sources..."
        time.sleep(0.2)
        
        _pipeline_status.log("→ Connecting to Hacker News API...", "info")
        time.sleep(0.1)
        _pipeline_status.log("→ Connecting to Product Hunt API...", "info")
        time.sleep(0.1)
        _pipeline_status.log("→ Connecting to GitHub Trending...", "info")
        time.sleep(0.2)
        
        _pipeline_status.log("Sources initialized ✓", "success")
        _pipeline_status.message = "Fetching ideas from sources..."
        
        # Run the pipeline
        result = run_pipeline(
            limit_per_source=limit,
            dry_run=False,
            verbose=False,
            skip_digest=False,
        )
        
        # Log source results
        for sr in result.source_results:
            if sr.success:
                _pipeline_status.log(
                    f"[{sr.source_name}] Fetched {sr.items_fetched} items ({sr.duration_ms:.0f}ms)", 
                    "success"
                )
            else:
                _pipeline_status.log(
                    f"[{sr.source_name}] Failed: {sr.error}", 
                    "error"
                )
        
        _pipeline_status.message = "Scoring and tagging items..."
        _pipeline_status.log(f"Scoring {result.total_items_fetched} items...", "info")
        time.sleep(0.2)
        _pipeline_status.log(f"Applied interest scoring ✓", "success")
        
        # Storage results
        if result.storage_result:
            _pipeline_status.message = "Saving to Airtable..."
            _pipeline_status.log("Connecting to Airtable...", "info")
            time.sleep(0.1)
            
            inserted = result.storage_result.inserted
            updated = result.storage_result.updated
            failed = result.storage_result.failed
            
            if inserted > 0:
                _pipeline_status.log(f"Inserted {inserted} new records", "success")
            if updated > 0:
                _pipeline_status.log(f"Updated {updated} existing records", "info")
            if failed > 0:
                _pipeline_status.log(f"Failed to save {failed} records", "warning")
        
        # Digest
        if result.digest_result:
            _pipeline_status.log(f"Generated digest: {result.digest_result.filename}", "success")
        
        # Convert result to dict
        _pipeline_status.result = {
            "sources_succeeded": result.sources_succeeded,
            "sources_failed": result.sources_failed,
            "total_items_fetched": result.total_items_fetched,
            "total_items_scored": result.total_items_scored,
            "storage": {
                "inserted": result.storage_result.inserted if result.storage_result else 0,
                "updated": result.storage_result.updated if result.storage_result else 0,
                "failed": result.storage_result.failed if result.storage_result else 0,
            } if result.storage_result else None,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors[:5] if result.errors else [],
        }
        
        _pipeline_status.log("", "info")
        _pipeline_status.log(f"Pipeline completed in {result.duration_seconds:.1f}s", "success")
        _pipeline_status.log(f"Total: {result.total_items_fetched} ideas from {result.sources_succeeded} sources", "info")
        
        _pipeline_status.status = "completed"
        _pipeline_status.message = f"Fetched {result.total_items_fetched} ideas from {result.sources_succeeded} sources"
        
    except Exception as e:
        _pipeline_status.log(f"Error: {str(e)}", "error")
        _pipeline_status.log("Pipeline execution failed", "error")
        _pipeline_status.status = "failed"
        _pipeline_status.message = f"Pipeline failed: {str(e)}"
        _pipeline_status.result = {"error": str(e)}
    
    finally:
        _pipeline_status.running = False
        _pipeline_status.finished_at = datetime.now()
        _pipeline_status.log("$ _", "cmd")  # Blinking cursor effect


@app.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    """Trigger a pipeline run."""
    global _pipeline_status
    
    # Check if already running
    if _pipeline_status.running:
        return jsonify({
            "success": False,
            "error": "Pipeline is already running",
            "status": _pipeline_status.status,
        }), 409
    
    # Get parameters
    data = request.get_json() or {}
    limit = min(int(data.get("limit", DEFAULT_LIMIT_PER_SOURCE)), 50)  # Cap at 50
    
    # Reset status
    _pipeline_status = PipelineStatus(
        running=True,
        started_at=datetime.now(),
        status="starting",
        message="Initializing pipeline...",
    )
    
    # Start pipeline in background thread
    thread = threading.Thread(target=_run_pipeline_async, args=(limit,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Pipeline started",
        "status": "starting",
    })


@app.route("/api/pipeline/status")
def api_pipeline_status():
    """Get current pipeline status."""
    global _pipeline_status
    
    response = {
        "running": _pipeline_status.running,
        "status": _pipeline_status.status,
        "message": _pipeline_status.message,
        "logs": _pipeline_status.logs or [],
    }
    
    if _pipeline_status.started_at:
        response["started_at"] = _pipeline_status.started_at.isoformat()
    
    if _pipeline_status.finished_at:
        response["finished_at"] = _pipeline_status.finished_at.isoformat()
        response["duration_seconds"] = (
            _pipeline_status.finished_at - _pipeline_status.started_at
        ).total_seconds()
    
    if _pipeline_status.result:
        response["result"] = _pipeline_status.result
    
    return jsonify(response)


@app.template_filter("score_color")
def score_color(score):
    """Return a color class based on score."""
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    else:
        return "low"


@app.template_filter("format_date")
def format_date(dt):
    """Format datetime for display."""
    if not dt:
        return "Unknown"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%b %d, %Y")


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Idea Digest Dashboard")
    print("=" * 50)
    print("Open http://localhost:5001 in your browser")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    app.run(debug=True, port=5001)

