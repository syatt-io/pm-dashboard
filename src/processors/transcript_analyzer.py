"""AI-powered meeting transcript analyzer for extracting action items."""

import re
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class ActionItem(BaseModel):
    """Structured action item extracted from meeting."""
    title: str = Field(description="Brief title of the action item")
    description: str = Field(description="Detailed description of what needs to be done")
    assignee: Optional[str] = Field(description="Person responsible for this item", default=None)
    due_date: Optional[str] = Field(description="Due date if mentioned (ISO format)", default=None)
    priority: str = Field(description="Priority level: High, Medium, or Low", default="Medium")
    context: str = Field(description="Meeting context where this was discussed")
    dependencies: Optional[List[str]] = Field(description="Other tasks this depends on", default=None)


class MeetingAnalysis(BaseModel):
    """Complete analysis of a meeting transcript."""
    summary: str = Field(description="Executive summary of the meeting")
    key_decisions: List[str] = Field(description="Important decisions made")
    action_items: List[ActionItem] = Field(description="Action items identified")
    blockers: List[str] = Field(description="Blockers or risks identified")
    follow_ups: List[str] = Field(description="Topics requiring follow-up discussion")


@dataclass
class ProcessedMeeting:
    """Processed meeting with extracted information."""
    meeting_id: str
    title: str
    date: datetime
    analysis: MeetingAnalysis
    raw_transcript: str
    confidence_score: float


class TranscriptAnalyzer:
    """Analyzes meeting transcripts to extract actionable information."""

    def __init__(self, llm=None):
        """Initialize the analyzer with an LLM."""
        self.llm = llm or self._default_llm()
        self.parser = PydanticOutputParser(pydantic_object=MeetingAnalysis)

    @staticmethod
    def _default_llm():
        """Create default LLM instance."""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "2000"))
        )

    def analyze_transcript(self, transcript: str, meeting_title: str = None,
                          meeting_date: datetime = None) -> MeetingAnalysis:
        """Analyze a meeting transcript to extract structured information."""

        system_prompt = """You are an expert meeting analyst. Your job is to analyze meeting transcripts and extract:
        1. A concise executive summary
        2. Key decisions that were made
        3. Clear action items with assignees and deadlines where mentioned
        4. Any blockers or risks discussed
        5. Topics that need follow-up discussion

        For action items, be specific and actionable. Include:
        - Clear title and description
        - Assignee name if mentioned (otherwise null)
        - Due date if mentioned (in ISO format YYYY-MM-DD)
        - Priority based on urgency discussed (High/Medium/Low)
        - Relevant context from the meeting
        - Dependencies if any were mentioned

        {format_instructions}
        """

        human_prompt = f"""Meeting: {meeting_title or 'Team Meeting'}
        Date: {meeting_date.strftime('%Y-%m-%d') if meeting_date else 'Today'}

        Transcript:
        {transcript[:8000]}  # Limit to avoid token limits

        Please analyze this meeting transcript and extract structured information."""

        messages = [
            SystemMessage(content=system_prompt.format(
                format_instructions=self.parser.get_format_instructions()
            )),
            HumanMessage(content=human_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            analysis = self.parser.parse(response.content)

            # Post-process dates to ensure proper format
            for item in analysis.action_items:
                if item.due_date:
                    item.due_date = self._normalize_date(item.due_date, meeting_date)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing transcript: {e}")
            # Return minimal analysis on error
            return MeetingAnalysis(
                summary="Error analyzing meeting transcript",
                key_decisions=[],
                action_items=[],
                blockers=[],
                follow_ups=[]
            )

    def extract_action_items(self, transcript: str) -> List[ActionItem]:
        """Extract just action items from a transcript."""

        prompt = """Extract all action items from this meeting transcript.
        Focus on:
        - Tasks that someone needs to complete
        - Deadlines mentioned
        - Assignments to specific people
        - Follow-up actions

        Return as a JSON array of action items with title, description, assignee, due_date, and priority.
        """

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=transcript[:5000])
        ]

        try:
            response = self.llm.invoke(messages)
            # Parse the response as JSON
            items_data = json.loads(response.content)
            return [ActionItem(**item) for item in items_data]
        except Exception as e:
            logger.error(f"Error extracting action items: {e}")
            return []

    def prioritize_action_items(self, items: List[ActionItem]) -> List[ActionItem]:
        """Prioritize action items based on urgency and importance."""

        # Define priority weights
        priority_weights = {"High": 3, "Medium": 2, "Low": 1}

        # Sort by priority and due date
        sorted_items = sorted(
            items,
            key=lambda x: (
                -priority_weights.get(x.priority, 2),  # Higher priority first
                x.due_date or "9999-12-31"  # Earlier dates first
            )
        )

        return sorted_items

    def identify_blockers(self, transcript: str) -> List[str]:
        """Identify blockers and risks from the transcript."""

        prompt = """Identify any blockers, risks, or concerns mentioned in this meeting.
        Look for:
        - Dependencies that are blocking progress
        - Resource constraints
        - Technical challenges
        - Timeline concerns
        - Team capacity issues

        Return as a JSON array of strings describing each blocker/risk.
        """

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=transcript[:3000])
        ]

        try:
            response = self.llm.invoke(messages)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Error identifying blockers: {e}")
            return []

    def generate_meeting_summary(self, transcript: str, max_length: int = 500) -> str:
        """Generate a concise meeting summary."""

        prompt = f"""Create a concise summary of this meeting in {max_length} characters or less.
        Include:
        - Main topics discussed
        - Key decisions
        - Important outcomes
        - Next steps

        Be concise and focus on the most important points.
        """

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=transcript[:4000])
        ]

        try:
            response = self.llm.invoke(messages)
            return response.content[:max_length]
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Summary generation failed"

    @staticmethod
    def _normalize_date(date_str: str, reference_date: datetime = None) -> str:
        """Normalize date strings to ISO format."""
        if not date_str:
            return None

        reference = reference_date or datetime.now()

        # Common relative date patterns
        relative_patterns = {
            r"tomorrow": reference + timedelta(days=1),
            r"next week": reference + timedelta(weeks=1),
            r"next month": reference + timedelta(days=30),
            r"end of week": reference + timedelta(days=(4 - reference.weekday())),
            r"end of month": reference.replace(day=1) + timedelta(days=32)
        }

        date_str_lower = date_str.lower()
        for pattern, date_value in relative_patterns.items():
            if pattern in date_str_lower:
                return date_value.strftime("%Y-%m-%d")

        # Try to parse as-is
        try:
            from dateutil import parser
            parsed_date = parser.parse(date_str)
            return parsed_date.strftime("%Y-%m-%d")
        except:
            return None

    def calculate_confidence_score(self, analysis: MeetingAnalysis) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.5  # Base score

        # Increase score based on completeness
        if analysis.summary and len(analysis.summary) > 50:
            score += 0.1
        if analysis.key_decisions:
            score += 0.1
        if analysis.action_items:
            score += 0.2
        if any(item.assignee for item in analysis.action_items):
            score += 0.1

        return min(score, 1.0)