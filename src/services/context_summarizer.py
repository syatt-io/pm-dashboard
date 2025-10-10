"""AI-powered context summarization with citations."""
import logging
from typing import List, Dict, Any, Tuple, Optional
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
    content: str  # Full content for reference
    key_quote: Optional[str] = None  # Most relevant excerpt (extracted by AI)


@dataclass
class SummarizedContext:
    """AI-generated summary with inline citations."""
    tldr: str  # 2-3 sentence executive summary
    project_context: str  # Structured project context (requirements, decisions, status, etc.)
    summary: str  # Main comprehensive narrative summary with inline [1], [2] citations
    open_questions: List[str]  # Unanswered questions or gaps
    action_items: List[str]  # Extracted action items
    citations: List[Citation]  # Ordered list of citations
    key_people: List[str]  # Key people involved
    timeline: List[Dict[str, str]]  # [{"date": "2024-01-15", "event": "..."}]
    confidence: str  # high, medium, low


class ContextSummarizer:
    """Generates AI summaries with citations from search results."""

    def __init__(self):
        """Initialize summarizer with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.ai.api_key)
        self.model = settings.ai.model  # Use configured model from OPENAI_MODEL env variable

    async def summarize(
        self,
        query: str,
        results: List[Any],
        debug: bool = False,
        project_context: Optional[Dict[str, Any]] = None,
        detail_level: str = "normal"
    ) -> SummarizedContext:
        """Generate AI summary with inline citations.

        Args:
            query: The original search query
            results: List of ContextSearchResult objects
            debug: Enable debug logging
            project_context: Optional dict with 'project_key' and 'keywords' for domain context
            detail_level: Detail level - 'brief', 'normal', or 'detailed' (default: 'normal')

        Returns:
            SummarizedContext with summary, citations, key people, and timeline
        """
        if not results:
            return SummarizedContext(
                tldr="No results found.",
                project_context="",
                summary="No results found.",
                open_questions=[],
                action_items=[],
                citations=[],
                key_people=[],
                timeline=[],
                confidence="low"
            )

        # Prepare context for LLM
        context_blocks = []
        citations = []

        for i, result in enumerate(results, 1):
            # Create citation with content
            citation = Citation(
                id=i,
                source=result.source,
                title=result.title,
                url=result.url,
                date=result.date,
                author=result.author or "Unknown",
                content=result.content,
                key_quote=None  # Will be extracted by AI
            )
            citations.append(citation)

            # Format context block for LLM
            context_blocks.append(
                f"[{i}] {result.source.upper()} - {result.title}\n"
                f"Date: {result.date.strftime('%Y-%m-%d')}\n"
                f"Author: {citation.author}\n"
                f"Content: {result.content}\n"
            )

        # Build prompt for LLM with optional project context and detail level
        prompt = self._build_summarization_prompt(query, context_blocks, project_context, detail_level)

        if debug:
            logger.info(f"📝 Summarization prompt: {len(prompt)} chars")
            logger.info(f"📊 Processing {len(results)} results into summary")

        try:
            # Build API parameters - some models don't support temperature/max_completion_tokens
            api_params = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert technical analyst helping engineers understand project context.\n\nYour goal: Synthesize all available information into a clear, comprehensive, well-structured explanation.\n\nGuidelines:\n- Write in a straightforward, matter-of-fact tone - like briefing a coworker\n- Synthesize information from multiple sources into a unified narrative\n- Focus on WHAT is known, not excessive WHO/WHERE/WHEN attribution\n- Only cite sources when it adds crucial context (decisions, disagreements, open questions)\n- Organize information logically by topic, not chronologically\n- Include ALL relevant technical details - be thorough and complete\n- Use clear structure with markdown formatting (headings, lists, code blocks)\n- Lead with the most important/actionable information\n- Write as if you're explaining the topic itself, not summarizing meetings\n\nStructure your response to fit the query:\n- Status checks → Summary + Current state + Context/background + Blockers + Next steps\n- Bug investigations → Summary + Problem description + Root cause + Impact + Solution + Status\n- Feature exploration → Summary + Requirements + Approach + Key decisions + Implementation details + Status\n- Technical questions → Summary + Direct answer + Supporting details + Context + Examples\n\nIMPORTANT - TEMPORAL PRIORITIZATION:\n- **Prioritize recent information over older information** - the most recent data is usually most accurate\n- **Concrete implementations (commits, deployed code, closed tickets) supersede old discussions**\n- If something was uncertain/debated in the past but now has a clear implementation, focus on the implementation\n- Old discussions are only relevant if they explain WHY something was done, not WHAT was done\n- When information conflicts, newer sources take precedence unless there's a good reason not to\n- Historical context is useful for understanding evolution, but current state is what matters most\n\nExample: If there was a 2-month-old discussion about \"should we use webhooks?\", but a recent commit shows webhooks were implemented, the fact they're now in use is what matters - not the old uncertainty.\n\nOTHER REQUIREMENTS:\n- Be complete - include all relevant information from the sources\n- Use clear headings (##) and bullet points (•) to organize information\n- Don't truncate or summarize away important technical details\n- Include specific requirements, decisions, blockers, and examples\n- End with clear next steps or remaining questions\n\nYour response should be thorough enough that the engineer doesn't need to read the original sources."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Only add temperature and max_completion_tokens for models that support them
            # Reasoning models like gpt-5/o1 don't support these parameters
            if not self.model.startswith('o1') and not self.model.startswith('gpt-5'):
                api_params["temperature"] = 0.2  # Very low temperature for maximum factual accuracy
                api_params["max_completion_tokens"] = 4000  # Increased from 1500 to allow comprehensive summaries

            # Call OpenAI
            response = await self.client.chat.completions.create(**api_params)

            # Extract response
            ai_response = response.choices[0].message.content

            if debug:
                logger.info(f"🤖 RAW AI RESPONSE:\n{ai_response[:500]}...")
                logger.info(f"📏 Full response length: {len(ai_response)} chars")

            # Parse structured response
            summary_data = self._parse_ai_response(ai_response)

            if debug:
                logger.info(f"✅ Generated summary: {len(summary_data['summary'])} chars")
                logger.info(f"  TL;DR: {summary_data['tldr'][:100]}...")
                logger.info(f"  PROJECT_CONTEXT: {len(summary_data['project_context'])} chars")
                logger.info(f"  Open questions: {len(summary_data['open_questions'])}")
                logger.info(f"  Action items: {len(summary_data['action_items'])}")
                logger.info(f"  Key quotes: {len(summary_data['key_quotes'])}")
                logger.info(f"  Key people: {summary_data['key_people']}")
                logger.info(f"  Timeline events: {len(summary_data['timeline'])}")

            # Add key quotes to citations
            for citation in citations:
                if citation.id in summary_data['key_quotes']:
                    citation.key_quote = summary_data['key_quotes'][citation.id]

            return SummarizedContext(
                tldr=summary_data['tldr'],
                project_context=summary_data['project_context'],
                summary=summary_data['summary'],
                open_questions=summary_data['open_questions'],
                action_items=summary_data['action_items'],
                citations=citations,
                key_people=summary_data['key_people'],
                timeline=summary_data['timeline'],
                confidence=summary_data['confidence']
            )

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Fallback to basic summary
            return SummarizedContext(
                tldr=f"Found {len(results)} results for '{query}'. AI summary failed.",
                project_context="",
                summary=f"Found {len(results)} results related to '{query}'. "
                        f"Unable to generate AI summary. Error: {str(e)}",
                open_questions=[],
                action_items=[],
                citations=citations,
                key_people=[],
                timeline=[],
                confidence="low"
            )

    def _build_summarization_prompt(self, query: str, context_blocks: List[str], project_context: Optional[Dict[str, Any]] = None, detail_level: str = "normal") -> str:
        """Build the LLM prompt for summarization.

        Args:
            query: Original search query
            context_blocks: Formatted context with citation numbers
            project_context: Optional dict with project_key and keywords for domain context
            detail_level: Detail level - 'brief', 'normal', or 'detailed'

        Returns:
            Complete prompt for LLM
        """
        context_text = "\n\n".join(context_blocks)

        # Build project context section if provided
        domain_context = ""
        if project_context and project_context.get('project_key') and project_context.get('keywords'):
            project_key = project_context['project_key']
            keywords = project_context['keywords']
            keywords_str = ", ".join(sorted(keywords)[:15])  # Limit to 15 most relevant
            domain_context = f"""
DOMAIN CONTEXT:
This query relates to the "{project_key}" project. Related terms and concepts for this project include: {keywords_str}.
These keywords provide context for understanding project-specific acronyms, terminology, and abbreviations that may appear in the results.
"""

        # Configure detail level instructions
        detail_instructions = {
            "brief": "Keep your summary concise (150-300 words). Focus on the most critical information only.",
            "normal": "Target 250-400 words. Be concise and focus on what matters most - prioritize actionable information over background details.",
            "detailed": "Be as thorough as possible (800-1500 words). Include ALL relevant details, examples, and context.",
            "slack": "CRITICAL: Maximum 2500 characters total. Target 300-400 words MAX. Be extremely concise - mention each piece of information only ONCE. No repetition. Use Slack markdown: *bold* for section headers, • for bullets, `code` for tickets. Prioritize the most important/actionable information only. Omit background details unless critical."
        }
        detail_instruction = detail_instructions.get(detail_level, detail_instructions["normal"])

        return f"""Query: "{query}"
{domain_context}
SEARCH RESULTS:
{context_text}

---

Synthesize all the search results into a concise, actionable answer. Focus on what matters most.

CRITICAL REQUIREMENTS:
1. BE CONCISE - prioritize actionable insights over background details
2. SYNTHESIZE information - don't list facts from different sources
3. Focus on WHAT is known, not WHO said it or WHERE it was said
4. {detail_instruction}
5. Include only the most important technical details - omit nice-to-know information
6. Organize by logical topic flow, NOT chronologically or by source
7. **TEMPORAL PRIORITIZATION**: Always prioritize recent information (newer dates) over older information. Recent discussions, commits, or tickets supersede older ones on the same subject.

What to synthesize from the sources (prioritizing recent data):

TECHNICAL UNDERSTANDING:
- What is the current state/status?
- What is the root cause or key issue?
- What are the requirements or constraints?
- What decisions have been made and why?
- What solutions or approaches are being used?
- What are the blockers or open questions?

ACTIONABLE INFORMATION:
- Ticket numbers and their status
- Implementation details and technical approaches
- Next steps or recommendations
- Dependencies and related work

PRESENTATION STYLE:
- Lead with the most important/actionable information first
- Write in a straightforward, matter-of-fact tone - no fluff
- Use clear, concise sections (headings, bullet points)
- Only mention sources when it adds crucial context
- Include specific examples only when they clarify the point (ticket numbers, key decisions)
- Avoid repetition - say each thing once
- Skip obvious background information
"""

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse the flexible AI response.

        With the new flexible format, the AI can structure the response however it wants.
        We just need to extract citations if they're present in [1], [2] format.

        Args:
            response: Raw AI response text

        Returns:
            Dict with summary and extracted metadata
        """
        import re

        # Default values
        result = {
            'tldr': '',  # No longer used, kept for backwards compatibility
            'project_context': '',  # No longer used, kept for backwards compatibility
            'summary': response.strip(),  # The entire response IS the summary
            'open_questions': [],  # Not extracted anymore
            'action_items': [],  # Not extracted anymore
            'key_quotes': {},  # Extract inline citations if present
            'key_people': [],  # Not extracted anymore
            'timeline': [],  # Not extracted anymore
            'confidence': 'medium'  # Default confidence
        }

        # Extract inline citations [1], [2] etc. and try to find corresponding quotes
        # Look for patterns like [1]: "quote" or [1] "quote" in the text
        citation_pattern = re.compile(r'\[(\d+)\][\s:]*["]([^"]+)["]')
        for match in citation_pattern.finditer(response):
            citation_num = int(match.group(1))
            quote = match.group(2).strip()
            result['key_quotes'][citation_num] = quote

        return result
