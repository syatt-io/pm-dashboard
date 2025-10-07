"""AI-powered context summarization with citations."""
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A citation reference to a source document."""
    id: int
    source: str  # slack, fireflies, jira, notion
    title: str
    url: str
    date: datetime
    author: str


@dataclass
class SummarizedContext:
    """AI-generated summary with inline citations."""
    summary: str  # Main summary with inline [1], [2] citations
    citations: List[Citation]  # Ordered list of citations
    key_people: List[str]  # Key people involved
    timeline: List[Dict[str, str]]  # [{"date": "2024-01-15", "event": "..."}]
    confidence: str  # high, medium, low


class ContextSummarizer:
    """Generates AI summaries with citations from search results."""

    def __init__(self):
        """Initialize summarizer with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.openai.api_key)
        self.model = "gpt-4o-mini"  # Fast and cost-effective

    async def summarize(
        self,
        query: str,
        results: List[Any],
        debug: bool = False
    ) -> SummarizedContext:
        """Generate AI summary with inline citations.

        Args:
            query: The original search query
            results: List of ContextSearchResult objects
            debug: Enable debug logging

        Returns:
            SummarizedContext with summary, citations, key people, and timeline
        """
        if not results:
            return SummarizedContext(
                summary="No results found.",
                citations=[],
                key_people=[],
                timeline=[],
                confidence="low"
            )

        # Prepare context for LLM
        context_blocks = []
        citations = []

        for i, result in enumerate(results, 1):
            # Create citation
            citation = Citation(
                id=i,
                source=result.source,
                title=result.title,
                url=result.url,
                date=result.date,
                author=result.author or "Unknown"
            )
            citations.append(citation)

            # Format context block for LLM
            context_blocks.append(
                f"[{i}] {result.source.upper()} - {result.title}\n"
                f"Date: {result.date.strftime('%Y-%m-%d')}\n"
                f"Author: {citation.author}\n"
                f"Content: {result.content}\n"
            )

        # Build prompt for LLM
        prompt = self._build_summarization_prompt(query, context_blocks)

        if debug:
            logger.info(f"📝 Summarization prompt: {len(prompt)} chars")
            logger.info(f"📊 Processing {len(results)} results into summary")

        try:
            # Call OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise, accurate summaries with inline citations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more factual summaries
                max_tokens=1500
            )

            # Extract response
            ai_response = response.choices[0].message.content

            # Parse structured response
            summary_data = self._parse_ai_response(ai_response)

            if debug:
                logger.info(f"✅ Generated summary: {len(summary_data['summary'])} chars")
                logger.info(f"  Key people: {summary_data['key_people']}")
                logger.info(f"  Timeline events: {len(summary_data['timeline'])}")

            return SummarizedContext(
                summary=summary_data['summary'],
                citations=citations,
                key_people=summary_data['key_people'],
                timeline=summary_data['timeline'],
                confidence=summary_data['confidence']
            )

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Fallback to basic summary
            return SummarizedContext(
                summary=f"Found {len(results)} results related to '{query}'. "
                        f"Unable to generate AI summary. Error: {str(e)}",
                citations=citations,
                key_people=[],
                timeline=[],
                confidence="low"
            )

    def _build_summarization_prompt(self, query: str, context_blocks: List[str]) -> str:
        """Build the LLM prompt for summarization.

        Args:
            query: Original search query
            context_blocks: Formatted context with citation numbers

        Returns:
            Complete prompt for LLM
        """
        context_text = "\n\n".join(context_blocks)

        return f"""You are helping summarize search results for the query: "{query}"

CONTEXT FROM SEARCH RESULTS:
{context_text}

TASK:
Generate a concise summary that:
1. Answers the query directly using information from the sources
2. Uses inline citations [1], [2], etc. after each claim
3. Highlights the most relevant information first
4. Identifies key people mentioned
5. Creates a timeline of significant events (if applicable)

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
SUMMARY:
[Your summary here with inline citations [1], [2], etc.]

KEY_PEOPLE:
- Person Name 1
- Person Name 2

TIMELINE:
- YYYY-MM-DD: Event description [citation]

CONFIDENCE: high|medium|low

GUIDELINES:
- Keep summary under 300 words
- Use direct quotes sparingly, prioritize paraphrasing
- Only cite sources that support each specific claim
- Confidence = high if sources are direct/recent, medium if partial, low if sparse
- If no timeline is relevant, write "TIMELINE: None"
- If no people are mentioned, write "KEY_PEOPLE: None"
"""

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured AI response.

        Args:
            response: Raw AI response text

        Returns:
            Dict with summary, key_people, timeline, confidence
        """
        # Default values
        result = {
            'summary': '',
            'key_people': [],
            'timeline': [],
            'confidence': 'medium'
        }

        # Split response into sections
        sections = {
            'SUMMARY:': 'summary',
            'KEY_PEOPLE:': 'key_people',
            'TIMELINE:': 'timeline',
            'CONFIDENCE:': 'confidence'
        }

        current_section = None
        lines = response.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a section header
            for header, section_key in sections.items():
                if line.upper().startswith(header):
                    current_section = section_key
                    # Extract content if it's on the same line
                    remainder = line[len(header):].strip()
                    if remainder and section_key == 'confidence':
                        result['confidence'] = remainder.lower()
                    elif remainder and section_key == 'summary':
                        result['summary'] = remainder
                    break
            else:
                # Not a header, add to current section
                if current_section == 'summary':
                    if result['summary']:
                        result['summary'] += ' ' + line
                    else:
                        result['summary'] = line

                elif current_section == 'key_people':
                    if line.lower() != 'none' and line.startswith('-'):
                        person = line[1:].strip()
                        if person:
                            result['key_people'].append(person)

                elif current_section == 'timeline':
                    if line.lower() != 'none' and line.startswith('-'):
                        # Parse "- YYYY-MM-DD: Event description"
                        timeline_parts = line[1:].split(':', 1)
                        if len(timeline_parts) == 2:
                            date_str = timeline_parts[0].strip()
                            event = timeline_parts[1].strip()
                            result['timeline'].append({
                                'date': date_str,
                                'event': event
                            })

        # Ensure confidence is valid
        if result['confidence'] not in ['high', 'medium', 'low']:
            result['confidence'] = 'medium'

        return result
