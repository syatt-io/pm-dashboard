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
                        "content": "You are an expert technical analyst that creates comprehensive, detailed summaries from project documentation. Write in a casual, conversational tone - like you're explaining things to a teammate over coffee, not writing formal documentation. Your summaries should be thorough enough that engineers can spec and build features without needing to reference source material. Extract ALL relevant technical details, decisions, requirements, and context."
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

            # Parse structured response
            summary_data = self._parse_ai_response(ai_response)

            if debug:
                logger.info(f"✅ Generated summary: {len(summary_data['summary'])} chars")
                logger.info(f"  TL;DR: {summary_data['tldr'][:100]}...")
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
            "normal": "Aim for 400-800 words for complex topics (longer is better if information-dense).",
            "detailed": "Be as thorough as possible (800-1500 words). Include ALL relevant details, examples, and context."
        }
        detail_instruction = detail_instructions.get(detail_level, detail_instructions["normal"])

        return f"""You are helping summarize search results for the query: "{query}"
{domain_context}
CONTEXT FROM SEARCH RESULTS:
{context_text}

GOAL:
Create a COMPREHENSIVE summary that provides ALL the context needed to understand and work on this topic. The reader should NOT need to reference the source material. Think deeply about the topic and extract every relevant detail.

TASK:
Generate a detailed, thorough summary that:
1. **Provides complete context**: What is being discussed? What's the background?
2. **Extracts ALL technical details**: Requirements, specifications, implementations, integrations, APIs, data structures, UI elements, business logic
3. **Captures decisions made**: What was decided? Why? What alternatives were considered?
4. **Identifies blockers and issues**: What problems exist? What's being tested? What's pending?
5. **Includes specific examples**: Ticket numbers, URLs, specific features mentioned, code references
6. **Documents requirements**: What needs to be built? What are the acceptance criteria?
7. **Notes dependencies**: What depends on what? What needs to happen first?
8. **Preserves technical accuracy**: Use exact terminology, keep technical details precise
9. **Uses inline citations [1], [2]** after EVERY claim to maintain traceability
10. **Organizes information logically**: Most important/relevant first, then supporting details

FOR JIRA TICKETS:
- Include ticket numbers, status, and assignees
- Extract ALL requirements and acceptance criteria from descriptions AND comments
- Note any blockers, dependencies, or related tickets mentioned
- Capture implementation details discussed in comments

FOR MEETINGS (Fireflies):
- Capture decisions made and rationale
- Note action items and owners
- Extract technical discussions and specifications mentioned
- Include any demos or reviews discussed

FOR SLACK CONVERSATIONS:
- Capture questions asked and answers provided
- Note any decisions or consensus reached
- Extract technical details shared in discussions

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

TLDR:
[2-3 sentences that capture the essence - the absolute must-know information. Make it punchy and actionable.]

PROJECT_CONTEXT:
• Project start date: [if found in sources]
• Current status: [if found]
• Known requirements: [bulleted list if found]
• Completed work: [bulleted list if found]
• Pending/needs scoping: [bulleted list if found]
• Key decisions: [bulleted list if found]
• Blockers/risks: [bulleted list if found]
• Key people: [names if found]
• Important dates: [timeline if found]
• Open questions: [questions if found]
• Action items: [action items if found]
(Only include bullet points that have relevant information from the sources. Skip empty categories.)

DETAILED_SUMMARY:
[Comprehensive multi-paragraph narrative summary with inline citations [1], [2], etc. Include ALL relevant technical details organized logically. Aim for 400-800 words if needed to be thorough. This should complement the PROJECT_CONTEXT section with narrative flow and technical specifics.]

KEY_QUOTES:
For each citation you reference in the detailed summary, extract the single most important quote:
[1]: "Exact quote from source 1 that's most relevant"
[2]: "Exact quote from source 2 that's most relevant"
(Only include quotes for citations you actually used in DETAILED_SUMMARY)

CONFIDENCE: high|medium|low

GUIDELINES:
- Be COMPREHENSIVE - include ALL pertinent details from sources
- {detail_instruction}
- Organize into logical paragraphs by topic/theme
- Use precise technical terminology
- Write in a casual, conversational tone - avoid formal/corporate language
- Cite sources [1], [2] after every factual claim
- Extract the EXACT quotes that matter most for KEY_QUOTES section
- If a Jira ticket is mentioned, include its key and status
- Confidence = high if sources are direct/recent/complete, medium if partial, low if sparse
- Think step-by-step through the sources to ensure you don't miss any important details
"""

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured AI response.

        Args:
            response: Raw AI response text

        Returns:
            Dict with tldr, summary, open_questions, action_items, key_quotes, key_people, timeline, confidence
        """
        # Default values
        result = {
            'tldr': '',
            'project_context': '',
            'summary': '',
            'open_questions': [],
            'action_items': [],
            'key_quotes': {},  # Maps citation number to quote
            'key_people': [],
            'timeline': [],
            'confidence': 'medium'
        }

        # Split response into sections
        sections = {
            'TLDR:': 'tldr',
            'PROJECT_CONTEXT:': 'project_context',
            'DETAILED_SUMMARY:': 'summary',
            'KEY_QUOTES:': 'key_quotes',
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
                    elif remainder and section_key in ['summary', 'tldr']:
                        result[section_key] = remainder
                    break
            else:
                # Not a header, add to current section
                if current_section in ['summary', 'tldr', 'project_context']:
                    if result[current_section]:
                        result[current_section] += '\n' + line
                    else:
                        result[current_section] = line

                elif current_section == 'key_quotes':
                    # Parse "[1]: Quote text" format
                    if line.lower() != 'none' and line.startswith('['):
                        import re
                        match = re.match(r'\[(\d+)\]:\s*"?([^"]*)"?', line)
                        if match:
                            citation_num = int(match.group(1))
                            quote = match.group(2).strip()
                            result['key_quotes'][citation_num] = quote

        # Ensure confidence is valid
        if result['confidence'] not in ['high', 'medium', 'low']:
            result['confidence'] = 'medium'

        return result
