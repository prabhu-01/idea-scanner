"""
Services module.

Contains external service integrations like AI summarization.
"""

from src.services.ai_summarizer import AISummarizer, SummaryResult, get_summarizer

__all__ = [
    "AISummarizer",
    "SummaryResult", 
    "get_summarizer",
]

