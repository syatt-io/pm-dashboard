"""AI-powered context summarization with citations."""
import logging
from typing import List, Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import google.generativeai as genai
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
        """Initialize summarizer with AI client.

        Supports OpenAI, Anthropic, and Google providers. Will use fresh config on each summarize() call.
        """
        # Client will be created fresh on each summarize() call to support config updates
        self.client = None
        self.model = None
        self.provider = None

        # Load prompts from configuration
        from src.utils.prompt_manager import get_prompt_manager
        self.prompt_manager = get_prompt_manager()

    def _get_fresh_client(self):
        """Get fresh AI client with latest configuration.

        Returns:
            Tuple of (client, model, provider) where client type depends on provider
        """
        from config.settings import Settings
        ai_config = Settings.get_fresh_ai_config()

        logger.info(f"Creating summarizer client with provider={ai_config.provider}, model={ai_config.model}")

        if ai_config.provider == "openai":
            return AsyncOpenAI(api_key=ai_config.api_key), ai_config.model, "openai"

        elif ai_config.provider == "anthropic":
            return AsyncAnthropic(api_key=ai_config.api_key), ai_config.model, "anthropic"

        elif ai_config.provider == "google":
            genai.configure(api_key=ai_config.api_key)
            return genai, ai_config.model, "google"

        else:
            raise ValueError(f"Unsupported AI provider: {ai_config.provider}")

    async def summarize(
        self,
        query: str,
        results: List[Any],
        debug: bool = False,
        project_context: Optional[Dict[str, Any]] = None,
        detail_level: str = "normal",
        entity_links: Optional[Dict[str, Any]] = None,
        progress_analysis: Optional[Any] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> SummarizedContext:
        """Generate AI summary with inline citations.

        Args:
            query: The original search query
            results: List of ContextSearchResult objects
            debug: Enable debug logging
            project_context: Optional dict with 'project_key' and 'keywords' for domain context
            detail_level: Detail level - 'brief', 'normal', or 'detailed' (default: 'normal')
            entity_links: Optional dict with entity cross-references
            progress_analysis: Optional ProgressAnalysis object with progress signals
            conversation_history: Optional list of prior conversation turns [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

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

            # Format context block for LLM with source-specific metadata
            context_block = (
                f"[{i}] {result.source.upper()} - {result.title}\n"
                f"Date: {result.date.strftime('%Y-%m-%d')}\n"
                f"Author: {citation.author}\n"
            )

            # Add Jira-specific metadata if available
            if result.source == 'jira' and hasattr(result, 'status'):
                if result.status:
                    context_block += f"Status: {result.status}\n"
                if result.priority:
                    context_block += f"Priority: {result.priority}\n"
                if result.issue_key:
                    context_block += f"Issue: {result.issue_key}\n"

            context_block += f"Content: {result.content}\n"
            context_blocks.append(context_block)

        # Get fresh AI client with latest configuration
        client, model, provider = self._get_fresh_client()

        # Build prompt for LLM with optional project context, detail level, entity links, progress analysis, and conversation history
        prompt = self._build_summarization_prompt(query, context_blocks, project_context, detail_level, entity_links, results, progress_analysis, conversation_history)

        if debug:
            logger.info(f"📝 Summarization prompt: {len(prompt)} chars")
            logger.info(f"📊 Processing {len(results)} results into summary")
            logger.info(f"🤖 Using AI provider: {provider}, model: {model}")

        try:
            # Get system message from configuration
            system_message = self.prompt_manager.get_prompt(
                'context_search',
                'system_message',
                default="You are an expert technical analyst helping engineers understand project context. IMPORTANT: When analyzing Jira tickets, always use the explicit Status, Priority, and Issue fields provided in the search results - DO NOT infer status from content text. If a result shows 'Status: Closed', treat it as closed regardless of what the content says."
            )

            # Call AI provider based on configured provider
            if provider == "openai":
                # Build API parameters - some models don't support temperature/max_completion_tokens
                api_params = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_message
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }

                # Only add temperature and max_completion_tokens for models that support them
                # Reasoning models like gpt-5/o1 don't support these parameters
                if not model.startswith('o1') and not model.startswith('gpt-5'):
                    api_params["temperature"] = 0.2  # Very low temperature for maximum factual accuracy
                    api_params["max_completion_tokens"] = 4000  # Increased from 1500 to allow comprehensive summaries

                response = await client.chat.completions.create(**api_params)
                ai_response = response.choices[0].message.content

            elif provider == "anthropic":
                # Anthropic uses a different API structure
                response = await client.messages.create(
                    model=model,
                    max_tokens=4000,
                    temperature=0.2,
                    system=system_message,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                ai_response = response.content[0].text

            elif provider == "google":
                # Google uses a different API structure
                from google.generativeai.types import GenerationConfig

                # For Google, combine system message and prompt
                combined_prompt = f"{system_message}\n\n{prompt}"

                model_instance = genai.GenerativeModel(model)
                response = await model_instance.generate_content_async(
                    combined_prompt,
                    generation_config=GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=4000,
                    )
                )
                ai_response = response.text

            else:
                raise ValueError(f"Unsupported provider: {provider}")

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

    def _build_summarization_prompt(self, query: str, context_blocks: List[str], project_context: Optional[Dict[str, Any]] = None, detail_level: str = "normal", entity_links: Optional[Dict[str, Any]] = None, results: List[Any] = None, progress_analysis: Optional[Any] = None, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Build the LLM prompt for summarization.

        Args:
            query: Original search query
            context_blocks: Formatted context with citation numbers
            project_context: Optional dict with project_key and keywords for domain context
            detail_level: Detail level - 'brief', 'normal', or 'detailed'
            entity_links: Optional dict with entity cross-references
            results: Optional list of search results for entity linking
            progress_analysis: Optional ProgressAnalysis object with progress signals
            conversation_history: Optional list of prior conversation turns

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

            # Get domain context template from config
            domain_context_template = self.prompt_manager.get_prompt(
                'context_search',
                'domain_context_template',
                default="\nDOMAIN CONTEXT:\nThis query relates to the \"{project_key}\" project. Related terms: {keywords_str}.\n"
            )
            domain_context = domain_context_template.format(
                project_key=project_key,
                keywords_str=keywords_str
            )

        # Build entity context section if provided
        entity_context = ""
        if entity_links and results:
            entity_context = self._format_entity_links(entity_links, results)

        # Build progress context section if provided
        progress_context = ""
        if progress_analysis:
            progress_context = self._format_progress_analysis(progress_analysis)

        # Build conversation history section if provided
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = self._format_conversation_history(conversation_history)

        # Get detail level instructions from config
        detail_levels = self.prompt_manager.get_prompt('context_search', 'detail_levels', default={})
        detail_instruction = detail_levels.get(
            detail_level,
            "Target 150-250 words. Be brief and direct - cut unnecessary words, get straight to the point."
        )

        # Get user prompt template from config
        user_prompt_template = self.prompt_manager.get_prompt(
            'context_search',
            'user_prompt_template',
            default='Query: "{query}"\n{domain_context}\nSEARCH RESULTS:\n{context_text}\n\nSynthesize the results into a concise answer.'
        )

        return user_prompt_template.format(
            query=query,
            domain_context=domain_context,
            entity_context=entity_context,
            progress_context=progress_context,
            conversation_context=conversation_context,
            context_text=context_text,
            detail_instruction=detail_instruction
        )

    def _format_entity_links(self, entity_links: Dict[str, Any], results: List[Any]) -> str:
        """Format entity links for AI context.

        Args:
            entity_links: Dict with 'jira_tickets', 'github_prs', 'people' keys
            results: List of search results for source attribution

        Returns:
            Formatted entity context string
        """
        lines = []

        # Show Jira tickets mentioned in multiple sources
        if entity_links.get('jira_tickets'):
            jira_lines = []
            for ticket, indices in sorted(entity_links['jira_tickets'].items()):
                if len(indices) > 1:  # Only show cross-referenced entities
                    # Filter out invalid indices
                    valid_indices = [i for i in indices[:5] if i < len(results)]
                    if valid_indices:
                        sources = [f"[{i+1}] ({results[i].source})" for i in valid_indices]
                        jira_lines.append(f"  - {ticket}: Mentioned in {', '.join(sources)}")

            if jira_lines:
                lines.append("\n\nCROSS-REFERENCED JIRA TICKETS:")
                lines.extend(jira_lines)

        # Show GitHub PRs mentioned in multiple sources
        if entity_links.get('github_prs'):
            pr_lines = []
            for pr, indices in sorted(entity_links['github_prs'].items()):
                if len(indices) > 1:
                    # Filter out invalid indices
                    valid_indices = [i for i in indices[:5] if i < len(results)]
                    if valid_indices:
                        sources = [f"[{i+1}] ({results[i].source})" for i in valid_indices]
                        pr_lines.append(f"  - PR {pr}: Mentioned in {', '.join(sources)}")

            if pr_lines:
                lines.append("\n\nCROSS-REFERENCED GITHUB PRS:")
                lines.extend(pr_lines)

        return "\n".join(lines) if lines else ""

    def _format_progress_analysis(self, progress_analysis: Any) -> str:
        """Format progress analysis for AI context.

        Args:
            progress_analysis: ProgressAnalysis object with progress signals

        Returns:
            Formatted progress context string
        """
        lines = []

        # Summary line
        if progress_analysis.progress_summary:
            lines.append(f"\n\nPROGRESS OVERVIEW:\n{progress_analysis.progress_summary}")

        # Jira status breakdown
        if progress_analysis.jira_status and progress_analysis.jira_status.get('total_count', 0) > 0:
            breakdown = progress_analysis.jira_status['breakdown']
            lines.append("\n\nJIRA TICKET STATUS:")

            # In Progress tickets
            if breakdown.get('in_progress'):
                lines.append("  In Progress:")
                for ticket in breakdown['in_progress'][:5]:  # Limit to 5
                    days_ago = (datetime.now() - ticket['last_updated']).days
                    lines.append(f"    - {ticket['ticket']}: {ticket['status']} (updated {days_ago}d ago)")

            # Blocked tickets (IMPORTANT)
            if breakdown.get('blocked'):
                lines.append("  Blocked:")
                for ticket in breakdown['blocked']:
                    days_ago = (datetime.now() - ticket['last_updated']).days
                    lines.append(f"    - {ticket['ticket']}: {ticket['status']} (updated {days_ago}d ago)")

            # Recently completed
            if breakdown.get('done'):
                recent_done = [t for t in breakdown['done'] if (datetime.now() - t['last_updated']).days <= 7]
                if recent_done:
                    lines.append("  Recently Completed (last 7 days):")
                    for ticket in recent_done[:3]:
                        days_ago = (datetime.now() - ticket['last_updated']).days
                        lines.append(f"    - {ticket['ticket']} (completed {days_ago}d ago)")

        # GitHub activity
        if progress_analysis.github_activity and progress_analysis.github_activity.get('total_pr_count', 0) > 0:
            lines.append("\n\nGITHUB ACTIVITY:")

            # Recent PRs
            recent_prs = progress_analysis.github_activity.get('recent_prs', [])
            if recent_prs:
                lines.append("  Recent PRs:")
                for pr in recent_prs[:5]:
                    days_ago = (datetime.now() - pr['date']).days
                    lines.append(f"    - PR {pr['pr']}: {pr['status']} ({days_ago}d ago)")

            # Recent commits
            recent_commits = progress_analysis.github_activity.get('recent_commits', [])
            if recent_commits:
                lines.append(f"  Recent Commits: {len(recent_commits)} commits in last 7 days")

        # Blockers (CRITICAL INFORMATION)
        if progress_analysis.blockers:
            lines.append("\n\nBLOCKERS:")
            for blocker in progress_analysis.blockers[:5]:
                lines.append(f"  - {blocker['entity']}: {blocker['description'][:150]} ({blocker['days_ago']}d ago)")

        # Stale items (items with no updates in 14+ days)
        if progress_analysis.stale_items:
            lines.append("\n\nSTALE ITEMS (14+ days no update):")
            for item in progress_analysis.stale_items[:5]:
                lines.append(f"  - {item['entity']}: {item['status']} (last updated {item['days_ago']}d ago)")

        # Recent activity summary
        if progress_analysis.recent_activity:
            lines.append(f"\n\nRECENT ACTIVITY: {len(progress_analysis.recent_activity)} updates in last 7 days")

        return "\n".join(lines) if lines else ""

    def _format_conversation_history(self, conversation_history: List[Dict[str, str]]) -> str:
        """Format conversation history for AI context.

        Args:
            conversation_history: List of conversation turns with 'role' and 'content'

        Returns:
            Formatted conversation history string
        """
        if not conversation_history:
            return ""

        lines = ["\n\nPREVIOUS CONVERSATION:"]

        for turn in conversation_history:
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')

            if role == 'user':
                lines.append(f"User: {content}")
            elif role == 'assistant':
                # Truncate long assistant responses to save tokens
                truncated_content = content[:500] + "..." if len(content) > 500 else content
                lines.append(f"Assistant: {truncated_content}")

        lines.append("\nThe current query is a follow-up to this conversation. Use the conversation context to better understand the user's intent.")

        return "\n".join(lines)

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
