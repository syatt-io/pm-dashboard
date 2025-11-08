"""Epic matcher service using AI for semantic ticket-to-epic association."""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import json

logger = logging.getLogger(__name__)


class EpicMatch(BaseModel):
    """Structured output for epic matching."""
    suggested_epic_key: str = Field(description="The epic key that best matches the ticket")
    confidence: float = Field(description="Confidence score between 0 and 1")
    reason: str = Field(description="Brief explanation for the match")


class EpicMatcher:
    """AI-powered service to match Jira tickets to epics based on semantic similarity."""

    def __init__(self, llm=None):
        """
        Initialize the epic matcher.

        Args:
            llm: Optional LangChain LLM instance. If not provided, will use default from TranscriptAnalyzer.
        """
        if llm:
            self.llm = llm
        else:
            from src.processors.transcript_analyzer import TranscriptAnalyzer
            self.llm = TranscriptAnalyzer._default_llm()

        self.parser = JsonOutputParser(pydantic_object=EpicMatch)

    def match_ticket_to_epic(
        self,
        ticket_key: str,
        ticket_summary: str,
        ticket_description: Optional[str],
        available_epics: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Match a single ticket to the most appropriate epic using AI.

        Args:
            ticket_key: Jira ticket key (e.g., "SUBS-123")
            ticket_summary: Ticket title/summary
            ticket_description: Optional ticket description
            available_epics: List of dicts with 'key' and 'summary' for each epic

        Returns:
            Dict with suggested_epic_key, confidence, and reason, or None if match fails
        """
        if not available_epics:
            logger.warning(f"No epics available for matching ticket {ticket_key}")
            return None

        try:
            # Build epic list for prompt
            epic_list = "\n".join([
                f"{i+1}. {epic['key']}: {epic['summary']}"
                for i, epic in enumerate(available_epics)
            ])

            # Build description text (handle both string and ADF dict formats)
            if ticket_description:
                if isinstance(ticket_description, dict):
                    # Extract text from ADF (Atlassian Document Format)
                    # Just convert to string for now - proper ADF parsing could be added later
                    desc_str = str(ticket_description)[:500]
                elif isinstance(ticket_description, str):
                    desc_str = ticket_description[:500]
                else:
                    desc_str = str(ticket_description)[:500]
                desc_text = f"\nDescription: {desc_str}"
            else:
                desc_text = ""

            # Create AI prompt
            system_prompt = """You are an expert project manager analyzing Jira tickets. Your task is to suggest which epic a ticket belongs to based on semantic similarity between the ticket and epic descriptions.

Guidelines:
- Analyze the ticket summary and description
- Compare against available epic titles
- Consider thematic similarity, feature area, and technical scope
- Return confidence score 0-1 (0.8+ for strong matches, 0.5-0.79 for moderate, <0.5 for weak)
- If no epic is a good match, suggest the closest one but with low confidence

Response Format:
{
    "suggested_epic_key": "PROJ-123",
    "confidence": 0.85,
    "reason": "Brief explanation of why this epic matches the ticket"
}"""

            human_prompt = f"""Analyze this ticket and suggest which epic it belongs to:

Ticket: {ticket_key} - {ticket_summary}{desc_text}

Available Epics:
{epic_list}

Return your suggestion as JSON."""

            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            response = self.llm.invoke(messages)

            # Parse response
            response_text = response.content.strip()

            # Handle markdown code blocks
            if response_text.startswith("```"):
                # Extract JSON from code block
                lines = response_text.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                response_text = "\n".join(json_lines)

            # Parse JSON
            result = json.loads(response_text)

            # Validate the suggested epic exists
            suggested_key = result.get('suggested_epic_key')
            if suggested_key not in [e['key'] for e in available_epics]:
                logger.warning(f"AI suggested invalid epic key '{suggested_key}' for ticket {ticket_key}")
                return None

            # Return structured result
            return {
                'ticket_key': ticket_key,
                'suggested_epic_key': result['suggested_epic_key'],
                'confidence': float(result['confidence']),
                'reason': result['reason']
            }

        except Exception as e:
            logger.error(f"Error matching ticket {ticket_key} to epic: {e}", exc_info=True)
            return None

    def batch_match_tickets(
        self,
        tickets: List[Dict[str, Any]],
        available_epics: List[Dict[str, str]],
        confidence_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Match multiple tickets to epics in batch.

        Args:
            tickets: List of ticket dicts with 'key', 'summary', 'description'
            available_epics: List of epic dicts with 'key' and 'summary'
            confidence_threshold: Minimum confidence score to include in results

        Returns:
            List of match results (only matches above threshold)
        """
        results = []

        logger.info(f"Starting batch epic matching for {len(tickets)} tickets")

        for i, ticket in enumerate(tickets, 1):
            logger.info(f"Matching ticket {i}/{len(tickets)}: {ticket['key']}")

            match_result = self.match_ticket_to_epic(
                ticket_key=ticket['key'],
                ticket_summary=ticket['summary'],
                ticket_description=ticket.get('description'),
                available_epics=available_epics
            )

            if match_result and match_result['confidence'] >= confidence_threshold:
                results.append(match_result)
                logger.info(
                    f"  ✅ Matched to {match_result['suggested_epic_key']} "
                    f"(confidence: {match_result['confidence']:.2f})"
                )
            elif match_result:
                logger.info(
                    f"  ⚠️  Low confidence match ({match_result['confidence']:.2f}), skipping"
                )
            else:
                logger.warning(f"  ❌ Failed to match ticket {ticket['key']}")

        logger.info(f"Batch matching complete: {len(results)}/{len(tickets)} matches above threshold")

        return results

    def categorize_by_confidence(
        self,
        match_results: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize match results by confidence level.

        Args:
            match_results: List of match result dicts

        Returns:
            Dict with 'high', 'medium', 'low' keys containing categorized matches
        """
        categorized = {
            'high': [],    # 0.8+
            'medium': [],  # 0.5-0.79
            'low': []      # <0.5
        }

        for result in match_results:
            confidence = result['confidence']
            if confidence >= 0.8:
                categorized['high'].append(result)
            elif confidence >= 0.5:
                categorized['medium'].append(result)
            else:
                categorized['low'].append(result)

        return categorized
