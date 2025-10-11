"""Fireflies.ai API integration for fetching meeting transcripts."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class MeetingTranscript:
    """Structured meeting transcript data."""
    id: str
    title: str
    date: datetime
    duration: int  # in minutes
    attendees: List[str]
    transcript: str
    summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    topics: Optional[List[str]] = None


class FirefliesClient:
    """Client for interacting with Fireflies.ai API."""

    def __init__(self, api_key: str, base_url: str = "https://api.fireflies.ai/graphql"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def get_recent_meetings(self, days_back: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch meetings from the last N days with pagination support."""
        all_transcripts = []
        skip = 0
        batch_size = 50  # Fireflies API max per request

        while len(all_transcripts) < limit:
            # Fetch batch with skip offset for pagination
            query = f"""
            query {{
                transcripts(limit: {batch_size}, skip: {skip}) {{
                    id
                    title
                    date
                    duration
                }}
            }}
            """

            response = self._make_request(query, {})
            transcripts = response.get("data", {}).get("transcripts", [])

            # No more results
            if not transcripts:
                break

            all_transcripts.extend(transcripts)
            skip += batch_size

            # Stop if we got fewer than batch_size (last page)
            if len(transcripts) < batch_size:
                break

        # Trim to requested limit
        transcripts = all_transcripts[:limit]

        # Filter by date in Python since the API date format is unclear
        if transcripts and days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            filtered = []
            for t in transcripts:
                # Handle millisecond timestamps
                if t.get('date'):
                    try:
                        # If date is in milliseconds
                        if isinstance(t['date'], (int, float)) and t['date'] > 1000000000000:
                            meeting_date = datetime.fromtimestamp(t['date'] / 1000)
                        else:
                            meeting_date = datetime.fromisoformat(str(t['date']))

                        if meeting_date >= cutoff_date:
                            filtered.append(t)
                    except:
                        filtered.append(t)  # Include if we can't parse date
            return filtered

        return transcripts

    def get_meeting_transcript(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed transcript for a specific meeting with sharing settings.

        Returns raw dict with all fields including sharing/permission data.
        """
        query = """
        query GetTranscript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                duration
                user {
                    email
                    name
                }
                participants
                organizer_email
                sentences {
                    text
                    speaker_name
                }
            }
        }
        """

        variables = {"id": meeting_id}
        response = self._make_request(query, variables)

        if not response or "data" not in response:
            logger.error(f"Failed to fetch transcript for meeting {meeting_id}")
            return None

        data = response["data"].get("transcript")
        if not data:
            return None

        # Combine sentences into full transcript
        sentences = data.get("sentences", [])
        full_transcript = self._format_transcript(sentences)

        # Handle date conversion
        date_value = data.get("date")
        if isinstance(date_value, (int, float)) and date_value > 1000000000000:
            meeting_date = datetime.fromtimestamp(date_value / 1000)
        else:
            try:
                meeting_date = datetime.fromisoformat(str(date_value))
            except:
                meeting_date = datetime.now()

        # Get participants (attendees) as list of emails
        participants = data.get("participants", [])
        organizer_email = data.get("organizer_email", "")
        user_email = data.get("user", {}).get("email", "") if data.get("user") else ""

        # Build attendee list with emails
        attendees = []
        if participants:
            attendees = [{"email": p, "name": p} for p in participants]

        # Ensure organizer is in attendees
        if organizer_email and organizer_email not in participants:
            attendees.append({"email": organizer_email, "name": organizer_email})

        # Return raw dict with all data for ingestion
        return {
            "id": data["id"],
            "title": data.get("title", "Untitled Meeting"),
            "date": meeting_date.timestamp() * 1000,  # Convert to milliseconds
            "duration": data.get("duration", 0),
            "attendees": attendees,
            "transcript": full_transcript,
            "sharing_settings": {
                # By default, all attendees have access
                # Fireflies doesn't have explicit sharing API, so we use attendees as access list
                "shared_with": participants if participants else [],
                "is_public": False  # Meetings are private by default
            }
        }

    def get_unprocessed_meetings(self, last_processed_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get meetings that haven't been processed yet."""
        meetings = self.get_recent_meetings(days_back=7)

        if not last_processed_id:
            return meetings

        # Filter out already processed meetings
        try:
            last_index = next(i for i, m in enumerate(meetings) if m["id"] == last_processed_id)
            return meetings[:last_index]
        except StopIteration:
            # Last processed meeting not in recent list, return all
            return meetings

    def search_meetings(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search meetings by keyword."""
        graphql_query = """
        query SearchMeetings($search: String!, $limit: Int!) {
            transcripts(
                filter: {
                    search: $search
                }
                limit: $limit
            ) {
                id
                title
                date
                duration
                summary
                participants
            }
        }
        """

        variables = {
            "search": query,
            "limit": limit
        }

        response = self._make_request(graphql_query, variables)
        return response.get("data", {}).get("transcripts", [])

    def _make_request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Make GraphQL request to Fireflies API."""
        payload = {
            "query": query,
            "variables": variables
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Fireflies API request failed: {e}")
            raise
        except ValueError as e:
            logger.error(f"Failed to parse Fireflies API response: {e}")
            raise

    @staticmethod
    def _format_transcript(sentences: List[Dict[str, Any]]) -> str:
        """Format transcript sentences into readable text."""
        if not sentences:
            return ""

        formatted_lines = []
        current_speaker = None

        for sentence in sentences:
            speaker = sentence.get("speaker_name", "Unknown")
            text = sentence.get("text", "")

            if speaker != current_speaker:
                formatted_lines.append(f"\n{speaker}:")
                current_speaker = speaker

            formatted_lines.append(f"  {text}")

        return "\n".join(formatted_lines)