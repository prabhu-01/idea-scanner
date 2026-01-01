"""
Idea Digest - Web Dashboard

A simple Flask-based dashboard to browse ideas from Airtable.

Run with: python -m web.app
Or: cd web && python app.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from src.storage.airtable import AirtableStorage
from src.services.ai_summarizer import get_summarizer
from src.config import (
    AIRTABLE_API_KEY,
    AIRTABLE_MAX_RECORDS,
    AIRTABLE_RETENTION_DAYS,
    GROQ_API_KEY,
)

app = Flask(__name__)

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
    
    # Get last updated time (most recent item's created_at)
    last_updated = None
    if all_items:
        most_recent = max(all_items, key=lambda x: x.created_at or datetime.min)
        if most_recent.created_at:
            # Format as relative time
            diff = datetime.now() - most_recent.created_at
            if diff.days > 0:
                last_updated = f"{diff.days}d ago"
            elif diff.seconds >= 3600:
                last_updated = f"{diff.seconds // 3600}h ago"
            elif diff.seconds >= 60:
                last_updated = f"{diff.seconds // 60}m ago"
            else:
                last_updated = "just now"
    
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

