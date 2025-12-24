"""
Idea Digest Pipeline - Core execution logic.

This module orchestrates the complete pipeline:

    Sources → Scoring → Storage → Digest → Summary

Steps:
1. Load configuration from environment and CLI overrides
2. Instantiate sources (HackerNews, ProductHunt, GitHub)
3. Fetch items from each source (with error isolation)
4. Score and tag items based on themes, recency, popularity
5. Persist to storage (Airtable) with deduplication
6. Generate daily digest (Markdown)
7. Print execution summary

Design principles:
- Error isolation: one source failure doesn't stop others
- Idempotency: safe to run multiple times per day
- Dry-run support: test without writes (`--dry-run`)
- CLI flexibility: all settings overridable via arguments
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import traceback

from src.models.idea_item import IdeaItem
from src.sources.base import Source
from src.sources import HackerNewsSource, ProductHuntSource, GitHubTrendingSource
from src.scoring import score_item, compute_interest_score
from src.storage.base import Storage, UpsertResult
from src.storage import AirtableStorage, MockAirtableStorage
from src.config import (
    AIRTABLE_API_KEY,
    DEFAULT_LIMIT_PER_SOURCE,
    print_config_summary,
    validate_config,
)
from src.digest import DigestGenerator, DigestConfig, DigestResult


# =============================================================================
# Pipeline Result Data Structures
# =============================================================================

@dataclass
class SourceResult:
    """Result of fetching from a single source."""
    source_name: str
    items_fetched: int
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class PipelineResult:
    """Complete result of a pipeline execution."""
    started_at: datetime
    finished_at: Optional[datetime] = None
    
    # Source results
    source_results: List[SourceResult] = field(default_factory=list)
    
    # Aggregate counts
    total_items_fetched: int = 0
    total_items_scored: int = 0
    
    # Storage results (None if dry-run)
    storage_result: Optional[UpsertResult] = None
    dry_run: bool = False
    
    # Digest results (None if dry-run or disabled)
    digest_result: Optional[DigestResult] = None
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    @property
    def sources_succeeded(self) -> int:
        """Number of sources that fetched successfully."""
        return sum(1 for r in self.source_results if r.success)
    
    @property
    def sources_failed(self) -> int:
        """Number of sources that failed."""
        return sum(1 for r in self.source_results if not r.success)
    
    @property
    def duration_seconds(self) -> float:
        """Total pipeline duration in seconds."""
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0
    
    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 60,
            "PIPELINE EXECUTION SUMMARY",
            "=" * 60,
            f"Started:  {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {self.duration_seconds:.2f}s",
            f"Mode:     {'DRY RUN' if self.dry_run else 'LIVE'}",
            "",
            "Sources:",
        ]
        
        for sr in self.source_results:
            status = "✓" if sr.success else "✗"
            lines.append(f"  {status} {sr.source_name}: {sr.items_fetched} items ({sr.duration_ms:.0f}ms)")
            if sr.error:
                lines.append(f"      Error: {sr.error}")
        
        lines.extend([
            "",
            f"Total fetched: {self.total_items_fetched}",
            f"Total scored:  {self.total_items_scored}",
        ])
        
        if self.storage_result and not self.dry_run:
            lines.extend([
                "",
                "Storage:",
                f"  Inserted: {self.storage_result.inserted}",
                f"  Updated:  {self.storage_result.updated}",
                f"  Failed:   {self.storage_result.failed}",
            ])
        elif self.dry_run:
            lines.append("\nStorage: SKIPPED (dry-run mode)")
        
        if self.digest_result and self.digest_result.success:
            lines.extend([
                "",
                "Digest:",
                f"  File: {self.digest_result.filepath}",
                f"  Items: {self.digest_result.items_included}",
                f"  Themes: {', '.join(self.digest_result.themes_covered) or '(none)'}",
            ])
        elif self.dry_run:
            lines.append("\nDigest: SKIPPED (dry-run mode)")
        
        if self.errors:
            lines.extend([
                "",
                "Errors:",
            ])
            for error in self.errors[:5]:  # Show first 5
                lines.append(f"  - {error}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# Pipeline Configuration
# =============================================================================

@dataclass
class PipelineConfig:
    """
    Configuration for a pipeline run.
    
    CLI arguments override config file defaults.
    """
    limit_per_source: int = DEFAULT_LIMIT_PER_SOURCE
    dry_run: bool = False
    since_days: str = "daily"  # For GitHub: daily, weekly, monthly
    verbose: bool = False
    
    # Source selection (None = all sources)
    sources: Optional[List[str]] = None
    
    # Digest configuration
    digest_limit: int = 50
    digest_days: int = 1
    digest_output_dir: str = "digests"
    skip_digest: bool = False
    
    @classmethod
    def from_args(cls, args) -> "PipelineConfig":
        """Create config from argparse namespace."""
        return cls(
            limit_per_source=args.limit_per_source if hasattr(args, 'limit_per_source') and args.limit_per_source else DEFAULT_LIMIT_PER_SOURCE,
            dry_run=args.dry_run if hasattr(args, 'dry_run') else False,
            since_days=args.since_days if hasattr(args, 'since_days') and args.since_days else "daily",
            verbose=args.verbose if hasattr(args, 'verbose') else False,
            sources=args.sources if hasattr(args, 'sources') and args.sources else None,
            digest_limit=args.digest_limit if hasattr(args, 'digest_limit') and args.digest_limit else 50,
            digest_days=args.digest_days if hasattr(args, 'digest_days') and args.digest_days else 1,
            skip_digest=args.skip_digest if hasattr(args, 'skip_digest') else False,
        )


# =============================================================================
# Pipeline Class
# =============================================================================

class IdeaDigestPipeline:
    """
    Main pipeline for fetching, scoring, and storing ideas.
    
    Usage:
        config = PipelineConfig(limit_per_source=10, dry_run=True)
        pipeline = IdeaDigestPipeline(config)
        result = pipeline.run()
        print(result.to_summary())
    
    The pipeline:
    1. Instantiates all registered sources
    2. Fetches from each source independently (errors isolated)
    3. Scores and tags all items
    4. Stores to configured backend (unless dry-run)
    5. Returns comprehensive result
    """
    
    def __init__(self, config: PipelineConfig = None):
        """
        Initialize the pipeline.
        
        Args:
            config: Pipeline configuration. Defaults to PipelineConfig().
        """
        self.config = config or PipelineConfig()
        self._sources: List[Source] = []
        self._storage: Optional[Storage] = None
    
    def _get_registered_sources(self) -> List[Source]:
        """
        Get all registered sources.
        
        Returns sources filtered by config.sources if specified.
        """
        all_sources = [
            HackerNewsSource(),
            ProductHuntSource(),
            GitHubTrendingSource(since=self.config.since_days),
        ]
        
        if self.config.sources:
            # Filter to only requested sources
            return [s for s in all_sources if s.name in self.config.sources]
        
        return all_sources
    
    def _get_storage(self) -> Storage:
        """Get the configured storage backend."""
        if AIRTABLE_API_KEY:
            return AirtableStorage()
        return MockAirtableStorage()
    
    def _fetch_from_source(self, source: Source, limit: int) -> SourceResult:
        """
        Fetch items from a single source with error isolation.
        
        Args:
            source: The source to fetch from.
            limit: Maximum items to fetch.
            
        Returns:
            SourceResult with success/failure status and items.
        """
        start_time = datetime.now()
        
        try:
            items = source.fetch_items(limit=limit)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            return SourceResult(
                source_name=source.name,
                items_fetched=len(items),
                success=True,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            if self.config.verbose:
                error_msg += f"\n{traceback.format_exc()}"
            
            return SourceResult(
                source_name=source.name,
                items_fetched=0,
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )
    
    def _fetch_all_items(self, sources: List[Source], limit: int) -> tuple[List[IdeaItem], List[SourceResult]]:
        """
        Fetch items from all sources with error isolation.
        
        One source failing does not affect others.
        
        Args:
            sources: List of sources to fetch from.
            limit: Maximum items per source.
            
        Returns:
            Tuple of (all_items, source_results).
        """
        all_items: List[IdeaItem] = []
        source_results: List[SourceResult] = []
        
        for source in sources:
            if self.config.verbose:
                print(f"[{source.name}] Fetching up to {limit} items...")
            
            # Fetch with error isolation
            result = self._fetch_from_source(source, limit)
            source_results.append(result)
            
            # If successful, actually get the items
            if result.success:
                try:
                    items = source.fetch_items(limit=limit)
                    all_items.extend(items)
                    # Update result with actual count
                    result.items_fetched = len(items)
                except Exception:
                    # Already handled in _fetch_from_source
                    pass
        
        return all_items, source_results
    
    def _score_items(self, items: List[IdeaItem]) -> List[IdeaItem]:
        """
        Score and tag all items.
        
        Args:
            items: List of items to score.
            
        Returns:
            List of scored items.
        """
        scored_items = []
        for item in items:
            try:
                scored = score_item(item)
                scored_items.append(scored)
            except Exception as e:
                if self.config.verbose:
                    print(f"[scoring] Error scoring item {item.id}: {e}")
                # Keep original item if scoring fails
                scored_items.append(item)
        
        return scored_items
    
    def _generate_digest(self, storage: Storage) -> DigestResult:
        """
        Generate the daily digest.
        
        Args:
            storage: Storage backend to read items from.
            
        Returns:
            DigestResult with success status and file path.
        """
        if self.config.verbose:
            print(f"Generating digest (limit={self.config.digest_limit}, days={self.config.digest_days})...")
        
        digest_config = DigestConfig(
            limit=self.config.digest_limit,
            days=self.config.digest_days,
            output_dir=self.config.digest_output_dir,
        )
        
        generator = DigestGenerator(storage, digest_config)
        return generator.generate()
    
    def run(self) -> PipelineResult:
        """
        Execute the full pipeline.
        
        Steps:
        1. Initialize sources
        2. Fetch from all sources (errors isolated)
        3. Score and tag items
        4. Store to backend (unless dry-run)
        5. Return result
        
        Returns:
            PipelineResult with execution details.
        """
        result = PipelineResult(started_at=datetime.now(), dry_run=self.config.dry_run)
        
        try:
            # Step 1: Get sources
            sources = self._get_registered_sources()
            if self.config.verbose:
                print(f"Initialized {len(sources)} sources: {[s.name for s in sources]}")
            
            # Step 2: Fetch from all sources
            all_items, source_results = self._fetch_all_items(
                sources, 
                self.config.limit_per_source
            )
            result.source_results = source_results
            result.total_items_fetched = len(all_items)
            
            # Step 3: Score and tag
            if all_items:
                scored_items = self._score_items(all_items)
                result.total_items_scored = len(scored_items)
            else:
                scored_items = []
                result.total_items_scored = 0
            
            # Step 4: Store (unless dry-run)
            if not self.config.dry_run and scored_items:
                storage = self._get_storage()
                if self.config.verbose:
                    print(f"Storing {len(scored_items)} items to {storage.name}...")
                
                storage_result = storage.upsert_items(scored_items)
                result.storage_result = storage_result
                
                # Step 5: Generate digest (unless dry-run or skip_digest)
                if not self.config.skip_digest:
                    digest_result = self._generate_digest(storage)
                    result.digest_result = digest_result
            
        except Exception as e:
            result.errors.append(f"Pipeline error: {str(e)}")
            if self.config.verbose:
                result.errors.append(traceback.format_exc())
        
        result.finished_at = datetime.now()
        return result


# =============================================================================
# Convenience Functions
# =============================================================================

def run_pipeline(
    limit_per_source: int = None,
    dry_run: bool = False,
    since_days: str = "daily",
    verbose: bool = False,
    sources: List[str] = None,
    digest_limit: int = 50,
    digest_days: int = 1,
    skip_digest: bool = False,
) -> PipelineResult:
    """
    Run the pipeline with specified options.
    
    Convenience function for programmatic use.
    
    Args:
        limit_per_source: Max items per source (default: config value).
        dry_run: If True, skip storage and digest.
        since_days: Time range for GitHub (daily/weekly/monthly).
        verbose: If True, print detailed progress.
        sources: List of source names to use (None = all).
        digest_limit: Max items in digest.
        digest_days: Days to include in digest.
        skip_digest: If True, skip digest generation.
        
    Returns:
        PipelineResult with execution details.
    """
    config = PipelineConfig(
        limit_per_source=limit_per_source or DEFAULT_LIMIT_PER_SOURCE,
        dry_run=dry_run,
        since_days=since_days,
        verbose=verbose,
        sources=sources,
        digest_limit=digest_limit,
        digest_days=digest_days,
        skip_digest=skip_digest,
    )
    
    pipeline = IdeaDigestPipeline(config)
    return pipeline.run()

