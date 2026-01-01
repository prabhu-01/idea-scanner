"""
AI Summarization Service using Groq.

Provides fast, free AI summarization for idea descriptions.
Uses Groq's API which offers free tier access to LLaMA and Mixtral models.
"""

import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.config import GROQ_API_KEY, GROQ_MODEL


@dataclass
class SummaryResult:
    """Result of an AI summarization request."""
    success: bool
    summary: str
    error: Optional[str] = None
    model: Optional[str] = None
    tokens_used: int = 0


class AISummarizer:
    """AI-powered summarization using Groq API."""
    
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        
    def is_available(self) -> bool:
        """Check if AI summarization is available (API key configured)."""
        return bool(self.api_key)
    
    def summarize_idea(self, title: str, description: str, source: str) -> SummaryResult:
        """
        Generate a concise summary of an idea.
        
        Args:
            title: The idea's title
            description: The idea's description (can be long)
            source: Source platform (hackernews, producthunt, github)
            
        Returns:
            SummaryResult with the generated summary or error
        """
        if not self.is_available():
            return SummaryResult(
                success=False,
                summary="",
                error="AI summarization not configured. Add GROQ_API_KEY to .env"
            )
        
        # Build the prompt
        prompt = self._build_summary_prompt(title, description, source)
        
        try:
            response = self._call_api(prompt)
            return response
        except Exception as e:
            return SummaryResult(
                success=False,
                summary="",
                error=f"API error: {str(e)}"
            )
    
    def generate_insights(self, ideas: List[Dict[str, Any]]) -> SummaryResult:
        """
        Generate insights and trends from multiple ideas.
        
        Args:
            ideas: List of idea dictionaries with title, description, source
            
        Returns:
            SummaryResult with insights
        """
        if not self.is_available():
            return SummaryResult(
                success=False,
                summary="",
                error="AI summarization not configured. Add GROQ_API_KEY to .env"
            )
        
        prompt = self._build_insights_prompt(ideas)
        
        try:
            return self._call_api(prompt, max_tokens=800)
        except Exception as e:
            return SummaryResult(
                success=False,
                summary="",
                error=f"API error: {str(e)}"
            )
    
    def _build_summary_prompt(self, title: str, description: str, source: str) -> str:
        """Build prompt for single idea summarization."""
        source_context = {
            "hackernews": "a Hacker News post (tech/startup focused)",
            "producthunt": "a Product Hunt launch (new product/tool)",
            "github": "a GitHub repository (open source project)",
        }.get(source, "a tech idea")
        
        return f"""Summarize this {source_context} in 2-3 concise sentences. Focus on:
- What it does / solves
- Key value proposition
- Why it's interesting

Title: {title}

Description: {description[:1500]}

Write a clear, informative summary (no bullet points, just flowing text):"""

    def analyze_idea_deeply(self, title: str, description: str, source: str, 
                           maker_name: str = None, maker_bio: str = None) -> SummaryResult:
        """
        Generate a comprehensive analysis of an idea with maker context.
        
        Args:
            title: The idea's title
            description: The idea's description
            source: Source platform
            maker_name: Name of the creator (optional)
            maker_bio: Bio/headline of the creator (optional)
            
        Returns:
            SummaryResult with detailed analysis
        """
        if not self.is_available():
            return SummaryResult(
                success=False,
                summary="",
                error="AI not configured. Add GROQ_API_KEY to .env"
            )
        
        source_context = {
            "hackernews": "Hacker News post",
            "producthunt": "Product Hunt launch", 
            "github": "GitHub repository",
        }.get(source, "tech idea")
        
        maker_section = ""
        if maker_name:
            maker_section = f"\n\nMaker/Creator: {maker_name}"
            if maker_bio:
                maker_section += f"\nBio: {maker_bio}"
        
        prompt = f"""Analyze this {source_context} and provide insights in the following JSON format:

Title: {title}
Description: {description[:2000]}{maker_section}

Respond with ONLY valid JSON (no markdown, no extra text):
{{
    "summary": "2-3 sentence summary of what this is and why it matters",
    "problem_solved": "What problem does this solve? (1 sentence)",
    "target_audience": "Who is this for? (1 sentence)", 
    "unique_value": "What makes this unique or innovative? (1 sentence)",
    "potential_impact": "low/medium/high with brief reason",
    "tags": ["tag1", "tag2", "tag3"],
    "maker_insight": "Brief insight about the maker/team if info available, or null"
}}"""

        try:
            return self._call_api(prompt, max_tokens=500)
        except Exception as e:
            return SummaryResult(
                success=False,
                summary="",
                error=f"API error: {str(e)}"
            )

    def _build_insights_prompt(self, ideas: List[Dict[str, Any]]) -> str:
        """Build prompt for multi-idea insights."""
        ideas_text = "\n".join([
            f"- [{i.get('source', 'unknown')}] {i.get('title', 'Untitled')}: {(i.get('description', '')[:200])}"
            for i in ideas[:15]  # Limit to 15 ideas
        ])
        
        return f"""Analyze these tech ideas/projects and provide insights:

{ideas_text}

Provide a brief analysis covering:
1. **Key Themes**: What common themes or trends do you see? (2-3 sentences)
2. **Standout Ideas**: Which 2-3 ideas seem most innovative or impactful? (brief explanation)
3. **Emerging Patterns**: Any notable patterns in what's being built? (1-2 sentences)

Keep the total response under 200 words. Be specific and insightful."""

    def _call_api(self, prompt: str, max_tokens: int = 300) -> SummaryResult:
        """Make API call to Groq."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise tech analyst. Provide clear, informative summaries without fluff."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,  # Lower for more focused responses
        }
        
        response = requests.post(
            self.API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            error_msg = response.json().get("error", {}).get("message", response.text)
            return SummaryResult(
                success=False,
                summary="",
                error=f"API error ({response.status_code}): {error_msg}"
            )
        
        data = response.json()
        summary = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        
        return SummaryResult(
            success=True,
            summary=summary,
            model=self.model,
            tokens_used=tokens
        )


# Singleton instance
_summarizer: Optional[AISummarizer] = None


def get_summarizer() -> AISummarizer:
    """Get the singleton AI summarizer instance."""
    global _summarizer
    if _summarizer is None:
        _summarizer = AISummarizer()
    return _summarizer

