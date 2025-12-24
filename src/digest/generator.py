"""
Daily Digest Generator for Idea Digest.

Generates human-readable Markdown digests from scored IdeaItem objects.

Format: Markdown (.md)
Why Markdown:
1. Human-readable as plain text
2. Renders nicely in GitHub, email clients, Notion, etc.
3. Easy to convert to HTML, PDF, or other formats
4. Native support for links, headers, lists
5. Can be viewed in any text editor

Output: digests/YYYY-MM-DD.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from src.models.idea_item import IdeaItem
from src.storage.base import Storage


# =============================================================================
# Digest Configuration
# =============================================================================

@dataclass
class DigestConfig:
    """
    Configuration for digest generation.
    
    Attributes:
        limit: Maximum number of items to include (0 = no limit).
        days: Number of days to look back for items.
        min_score: Minimum score threshold for inclusion.
        output_dir: Directory to write digest files.
        include_ungrouped: Whether to include items with no themes.
    """
    limit: int = 50
    days: int = 1
    min_score: float = 0.0
    output_dir: str = "digests"
    include_ungrouped: bool = True


# =============================================================================
# Digest Result
# =============================================================================

@dataclass
class DigestResult:
    """
    Result of digest generation.
    
    Attributes:
        success: Whether digest was generated successfully.
        filepath: Path to the generated digest file.
        items_included: Number of items in the digest.
        themes_covered: List of themes included.
        error: Error message if generation failed.
    """
    success: bool
    filepath: Optional[str] = None
    items_included: int = 0
    themes_covered: List[str] = field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# Digest Generator
# =============================================================================

class DigestGenerator:
    """
    Generates daily digest files from scored items in storage.
    
    Usage:
        storage = MockAirtableStorage()
        generator = DigestGenerator(storage)
        result = generator.generate()
        print(f"Digest saved to: {result.filepath}")
    
    The generator:
    1. Queries storage for recent/top items
    2. Groups items by theme
    3. Sorts within groups by score (descending)
    4. Generates Markdown with summary and grouped items
    5. Writes to digests/YYYY-MM-DD.md
    """
    
    def __init__(self, storage: Storage, config: DigestConfig = None):
        """
        Initialize the digest generator.
        
        Args:
            storage: Storage backend to read items from.
            config: Digest configuration. Defaults to DigestConfig().
        """
        self.storage = storage
        self.config = config or DigestConfig()
    
    def generate(self, date: datetime = None) -> DigestResult:
        """
        Generate the daily digest.
        
        Args:
            date: Date for the digest filename. Defaults to today.
            
        Returns:
            DigestResult with success status and file path.
        """
        if date is None:
            date = datetime.now()
        
        try:
            # Step 1: Fetch items from storage
            items = self._fetch_items()
            
            if not items:
                return DigestResult(
                    success=True,
                    items_included=0,
                    themes_covered=[],
                    error="No items found for digest",
                )
            
            # Step 2: Group and sort items
            grouped_items = self._group_by_theme(items)
            
            # Step 3: Generate Markdown content
            content = self._generate_markdown(items, grouped_items, date)
            
            # Step 4: Write to file
            filepath = self._write_file(content, date)
            
            # Collect themes covered
            themes = [theme for theme in grouped_items.keys() if theme != "_ungrouped"]
            
            return DigestResult(
                success=True,
                filepath=str(filepath),
                items_included=len(items),
                themes_covered=themes,
            )
            
        except Exception as e:
            return DigestResult(
                success=False,
                error=str(e),
            )
    
    def _fetch_items(self) -> List[IdeaItem]:
        """
        Fetch items from storage based on config.
        
        Returns:
            List of IdeaItem sorted by score descending.
        """
        # Try get_top_items first for efficiency
        if self.config.limit > 0:
            items = self.storage.get_top_items(
                limit=self.config.limit,
                min_score=self.config.min_score,
            )
        else:
            # Get recent items if no limit
            items = self.storage.get_recent_items(days=self.config.days)
            
            # Filter by min_score
            if self.config.min_score > 0:
                items = [i for i in items if i.score >= self.config.min_score]
        
        # Sort by score descending (ensure deterministic order)
        items.sort(key=lambda x: (-x.score, x.title))
        
        return items
    
    def _group_by_theme(self, items: List[IdeaItem]) -> Dict[str, List[IdeaItem]]:
        """
        Group items by their themes.
        
        Items with multiple themes appear in multiple groups.
        Items with no themes go to "_ungrouped" if include_ungrouped is True.
        
        Args:
            items: List of items to group.
            
        Returns:
            Dict mapping theme name to list of items.
        """
        grouped: Dict[str, List[IdeaItem]] = defaultdict(list)
        
        for item in items:
            if item.tags:
                for tag in item.tags:
                    grouped[tag].append(item)
            elif self.config.include_ungrouped:
                grouped["_ungrouped"].append(item)
        
        # Sort items within each group by score descending
        for theme in grouped:
            grouped[theme].sort(key=lambda x: (-x.score, x.title))
        
        return dict(grouped)
    
    def _generate_markdown(
        self,
        all_items: List[IdeaItem],
        grouped_items: Dict[str, List[IdeaItem]],
        date: datetime,
    ) -> str:
        """
        Generate Markdown content for the digest.
        
        Args:
            all_items: All items (for summary stats).
            grouped_items: Items grouped by theme.
            date: Date for the digest header.
            
        Returns:
            Markdown string.
        """
        lines = []
        
        # Header
        lines.append(f"# Idea Digest - {date.strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append(f"*Generated on {date.strftime('%B %d, %Y at %H:%M')}*")
        lines.append("")
        
        # Summary section
        lines.extend(self._generate_summary(all_items, grouped_items))
        lines.append("")
        
        # Items by theme
        lines.extend(self._generate_themed_sections(grouped_items))
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Generated by Idea Digest*")
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_summary(
        self,
        all_items: List[IdeaItem],
        grouped_items: Dict[str, List[IdeaItem]],
    ) -> List[str]:
        """Generate the summary section."""
        lines = []
        
        lines.append("## 📊 Summary")
        lines.append("")
        
        # Total items
        lines.append(f"- **Total items:** {len(all_items)}")
        
        # Top themes (by item count)
        themes = [(t, len(items)) for t, items in grouped_items.items() if t != "_ungrouped"]
        themes.sort(key=lambda x: -x[1])
        
        if themes:
            top_themes = ", ".join(f"{t} ({c})" for t, c in themes[:5])
            lines.append(f"- **Top themes:** {top_themes}")
        
        # Highest scoring item
        if all_items:
            top_item = all_items[0]  # Already sorted by score
            lines.append(f"- **Top item:** [{top_item.title[:50]}...]({top_item.url}) (score: {top_item.score:.2f})")
        
        # Score distribution
        if all_items:
            scores = [i.score for i in all_items]
            avg_score = sum(scores) / len(scores)
            lines.append(f"- **Score range:** {min(scores):.2f} - {max(scores):.2f} (avg: {avg_score:.2f})")
        
        # Sources
        sources = set(i.source_name for i in all_items)
        lines.append(f"- **Sources:** {', '.join(sorted(sources))}")
        
        lines.append("")
        
        return lines
    
    def _generate_themed_sections(
        self,
        grouped_items: Dict[str, List[IdeaItem]],
    ) -> List[str]:
        """Generate themed sections with items."""
        lines = []
        
        # Sort themes: named themes first (alphabetically), then _ungrouped
        theme_order = sorted(
            grouped_items.keys(),
            key=lambda t: (t == "_ungrouped", t),
        )
        
        for theme in theme_order:
            items = grouped_items[theme]
            
            # Theme header
            if theme == "_ungrouped":
                lines.append("## 📁 Other Items")
            else:
                emoji = self._theme_emoji(theme)
                lines.append(f"## {emoji} {theme.replace('-', ' ').title()}")
            
            lines.append("")
            
            # Items in this theme
            for item in items:
                lines.extend(self._format_item(item))
            
            lines.append("")
        
        return lines
    
    def _format_item(self, item: IdeaItem) -> List[str]:
        """Format a single item as Markdown."""
        lines = []
        
        # Title with link and score badge
        score_badge = f"**[{item.score:.2f}]**"
        source_badge = f"`{item.source_name}`"
        lines.append(f"### {score_badge} [{item.title}]({item.url})")
        lines.append("")
        
        # Source and themes
        meta_parts = [source_badge]
        if item.tags:
            meta_parts.append(" | ".join(f"#{tag}" for tag in item.tags[:3]))
        lines.append(" ".join(meta_parts))
        lines.append("")
        
        # Description (truncated)
        if item.description:
            desc = item.description[:200]
            if len(item.description) > 200:
                desc += "..."
            lines.append(f"> {desc}")
            lines.append("")
        
        return lines
    
    def _theme_emoji(self, theme: str) -> str:
        """Get an emoji for a theme."""
        emoji_map = {
            "ai-ml": "🤖",
            "developer-tools": "🛠️",
            "programming": "💻",
            "startup": "🚀",
            "open-source": "📂",
            "security": "🔒",
            "data": "📊",
            "web-mobile": "🌐",
            "productivity": "⚡",
        }
        return emoji_map.get(theme, "📌")
    
    def _write_file(self, content: str, date: datetime) -> Path:
        """
        Write digest content to file.
        
        Args:
            content: Markdown content to write.
            date: Date for filename.
            
        Returns:
            Path to written file.
        """
        # Ensure output directory exists
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = f"{date.strftime('%Y-%m-%d')}.md"
        filepath = output_dir / filename
        
        # Write content
        filepath.write_text(content, encoding="utf-8")
        
        return filepath


# =============================================================================
# Convenience Functions
# =============================================================================

def generate_digest(
    storage: Storage,
    limit: int = 50,
    days: int = 1,
    min_score: float = 0.0,
    output_dir: str = "digests",
    date: datetime = None,
) -> DigestResult:
    """
    Generate a daily digest.
    
    Convenience function for simple usage.
    
    Args:
        storage: Storage backend to read items from.
        limit: Maximum items to include.
        days: Days to look back.
        min_score: Minimum score threshold.
        output_dir: Output directory for digest files.
        date: Date for digest (default: today).
        
    Returns:
        DigestResult with success status and file path.
    """
    config = DigestConfig(
        limit=limit,
        days=days,
        min_score=min_score,
        output_dir=output_dir,
    )
    
    generator = DigestGenerator(storage, config)
    return generator.generate(date)


def generate_digest_content(
    items: List[IdeaItem],
    date: datetime = None,
) -> str:
    """
    Generate digest content without writing to file.
    
    Useful for previewing or sending via other channels.
    
    Args:
        items: Items to include in digest.
        date: Date for digest header.
        
    Returns:
        Markdown content string.
    """
    if date is None:
        date = datetime.now()
    
    # Create a minimal generator for content generation
    from src.storage import MockAirtableStorage
    
    mock_storage = MockAirtableStorage()
    mock_storage.upsert_items(items)
    
    config = DigestConfig(limit=len(items))
    generator = DigestGenerator(mock_storage, config)
    
    grouped = generator._group_by_theme(items)
    return generator._generate_markdown(items, grouped, date)

