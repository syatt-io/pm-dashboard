"""
Meeting Deduplication Utility

Provides comprehensive deduplication logic for Fireflies meetings:
- Exact ID matching (same Fireflies ID)
- Fuzzy matching (similar title, date, and duration)
- Selection strategy: keep most complete meeting
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple

logger = logging.getLogger(__name__)


class MeetingDeduplicator:
    """Deduplicates meetings using exact and fuzzy matching strategies."""

    def __init__(self):
        self.stats = {
            "total": 0,
            "exact_duplicates_removed": 0,
            "fuzzy_duplicates_removed": 0,
            "final_count": 0,
        }

    def deduplicate(self, meetings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate meetings using both exact ID and fuzzy matching.

        Args:
            meetings: List of meeting dictionaries from Fireflies API

        Returns:
            Deduplicated list of meetings with most complete versions kept
        """
        if not meetings:
            return []

        self.stats["total"] = len(meetings)
        logger.info(f"Starting deduplication for {len(meetings)} meetings")

        # Phase 1: Remove exact duplicates by ID
        unique_by_id = self._remove_exact_duplicates(meetings)
        self.stats["exact_duplicates_removed"] = len(meetings) - len(unique_by_id)

        if self.stats["exact_duplicates_removed"] > 0:
            logger.info(
                f"Removed {self.stats['exact_duplicates_removed']} exact duplicate(s) by ID"
            )

        # Phase 2: Remove fuzzy duplicates
        final_meetings = self._remove_fuzzy_duplicates(unique_by_id)
        self.stats["fuzzy_duplicates_removed"] = len(unique_by_id) - len(final_meetings)

        if self.stats["fuzzy_duplicates_removed"] > 0:
            logger.info(
                f"Removed {self.stats['fuzzy_duplicates_removed']} fuzzy duplicate(s)"
            )

        self.stats["final_count"] = len(final_meetings)

        logger.info(
            f"Deduplication complete: {self.stats['total']} → {self.stats['final_count']} "
            f"(removed {self.stats['exact_duplicates_removed']} exact + "
            f"{self.stats['fuzzy_duplicates_removed']} fuzzy duplicates)"
        )

        return final_meetings

    def _remove_exact_duplicates(
        self, meetings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove meetings with duplicate Fireflies IDs, keeping the most complete one.

        Args:
            meetings: List of meetings to deduplicate

        Returns:
            List with exact duplicates removed
        """
        seen_ids: Set[str] = set()
        unique_meetings = []

        for meeting in meetings:
            meeting_id = meeting.get("id")
            if not meeting_id:
                # No ID, keep it (shouldn't happen but be defensive)
                unique_meetings.append(meeting)
                continue

            if meeting_id not in seen_ids:
                seen_ids.add(meeting_id)
                unique_meetings.append(meeting)
            else:
                # Found duplicate - log it
                logger.debug(
                    f"Exact duplicate found: ID={meeting_id}, "
                    f"Title='{meeting.get('title')}' (discarded)"
                )

        return unique_meetings

    def _remove_fuzzy_duplicates(
        self, meetings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove near-duplicate meetings using fuzzy matching.

        Groups similar meetings and keeps the most complete one from each group.

        Args:
            meetings: List of meetings to deduplicate

        Returns:
            List with fuzzy duplicates removed
        """
        if not meetings:
            return []

        # Track which meetings have been grouped
        processed_indices: Set[int] = set()
        final_meetings = []

        for i, meeting in enumerate(meetings):
            if i in processed_indices:
                continue

            # Find all meetings similar to this one
            similar_group = [meeting]
            similar_indices = {i}

            for j in range(i + 1, len(meetings)):
                if j in processed_indices:
                    continue

                if self._are_meetings_similar(meeting, meetings[j]):
                    similar_group.append(meetings[j])
                    similar_indices.add(j)

            # Mark all as processed
            processed_indices.update(similar_indices)

            # Select best from group
            if len(similar_group) > 1:
                best_meeting = self._select_best_meeting(similar_group)
                logger.info(
                    f"Fuzzy duplicate group found ({len(similar_group)} meetings): "
                    f"Title='{meeting.get('title')}', "
                    f"Kept ID={best_meeting.get('id')}"
                )
                final_meetings.append(best_meeting)
            else:
                # No duplicates, keep the meeting
                final_meetings.append(meeting)

        return final_meetings

    def _are_meetings_similar(self, m1: Dict[str, Any], m2: Dict[str, Any]) -> bool:
        """
        Determine if two meetings are similar enough to be considered duplicates.

        Criteria:
        - Same title (case-insensitive, normalized whitespace)
        - Date within 5 minutes
        - Duration within 10%

        Args:
            m1: First meeting
            m2: Second meeting

        Returns:
            True if meetings are similar, False otherwise
        """
        # Title matching (case-insensitive, normalized whitespace)
        title1 = " ".join(str(m1.get("title", "")).lower().split())
        title2 = " ".join(str(m2.get("title", "")).lower().split())

        if title1 != title2:
            return False

        # Date matching (within 5 minutes = 300 seconds)
        try:
            date1 = m1.get("date")
            date2 = m2.get("date")

            if date1 is None or date2 is None:
                return False

            # Handle both datetime objects and timestamps
            if isinstance(date1, datetime):
                ts1 = date1.timestamp()
            else:
                # Fireflies returns milliseconds, convert to seconds
                ts1 = float(date1) / 1000

            if isinstance(date2, datetime):
                ts2 = date2.timestamp()
            else:
                ts2 = float(date2) / 1000

            time_diff = abs(ts1 - ts2)
            if time_diff > 300:  # 5 minutes
                return False
        except (TypeError, ValueError) as e:
            logger.warning(f"Error comparing dates: {e}")
            return False

        # Duration matching (within 10%)
        try:
            dur1 = m1.get("duration")
            dur2 = m2.get("duration")

            if dur1 is None or dur2 is None:
                # If both missing, consider it a match (already matched by title + date)
                return True

            dur1 = float(dur1)
            dur2 = float(dur2)

            if dur1 == 0 and dur2 == 0:
                return True

            avg_duration = (dur1 + dur2) / 2
            if avg_duration == 0:
                return True

            duration_diff = abs(dur1 - dur2)
            threshold = avg_duration * 0.1  # 10% of average

            if duration_diff > threshold:
                return False
        except (TypeError, ValueError) as e:
            logger.warning(f"Error comparing durations: {e}")
            # If duration comparison fails but title and date match, consider it similar
            return True

        return True

    def _select_best_meeting(self, meetings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the most complete meeting from a group of duplicates.

        Priority:
        1. Most sentences (longest transcript)
        2. Most participants
        3. Most recent date

        Args:
            meetings: List of similar meetings

        Returns:
            The best meeting from the group
        """
        if not meetings:
            raise ValueError("Cannot select from empty meeting list")

        if len(meetings) == 1:
            return meetings[0]

        # Score each meeting
        scored_meetings = []
        for meeting in meetings:
            score = self._calculate_completeness_score(meeting)
            scored_meetings.append((score, meeting))

        # Sort by score (descending), then keep the best
        scored_meetings.sort(key=lambda x: x[0], reverse=True)
        best_meeting = scored_meetings[0][1]

        # Log the selection
        logger.debug(
            f"Selected best meeting: ID={best_meeting.get('id')}, "
            f"Score={scored_meetings[0][0]:.2f}"
        )

        return best_meeting

    def _calculate_completeness_score(self, meeting: Dict[str, Any]) -> float:
        """
        Calculate a completeness score for a meeting.

        Higher scores indicate more complete meetings.

        Scoring:
        - Sentences count: +1 per sentence (or +100 if 'sentences' field exists)
        - Participants count: +50 per participant
        - Recency: +0.001 per day since epoch (newer is better)

        Args:
            meeting: Meeting to score

        Returns:
            Completeness score (higher = more complete)
        """
        score = 0.0

        # Transcript completeness (highest priority)
        sentences = meeting.get("sentences", [])
        if sentences:
            sentence_count = len(sentences) if isinstance(sentences, list) else 0
            score += sentence_count * 1.0
        else:
            # If no sentences in this object, check if it has transcript data flag
            # (full transcript might be loaded separately)
            if meeting.get("has_transcript", False):
                score += 100.0

        # Participant count (second priority)
        participants = meeting.get("participants", [])
        if participants:
            participant_count = (
                len(participants) if isinstance(participants, list) else 0
            )
            score += participant_count * 50.0

        # Recency (third priority, small weight)
        try:
            date = meeting.get("date")
            if date:
                if isinstance(date, datetime):
                    timestamp = date.timestamp()
                else:
                    # Convert milliseconds to seconds
                    timestamp = float(date) / 1000

                # Days since epoch (newer meetings get higher scores)
                days_since_epoch = timestamp / 86400
                score += days_since_epoch * 0.001
        except (TypeError, ValueError):
            # Date comparison failed, skip this component
            pass

        return score

    def get_stats(self) -> Dict[str, int]:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with stats: total, exact_duplicates_removed,
            fuzzy_duplicates_removed, final_count
        """
        return self.stats.copy()
