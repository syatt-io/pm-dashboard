"""Unit tests for EpicMatcher service."""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json

from src.services.epic_matcher import EpicMatcher, EpicMatch


class TestEpicMatcher(unittest.TestCase):
    """Test cases for the EpicMatcher service."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock LLM
        self.mock_llm = Mock()
        self.matcher = EpicMatcher(llm=self.mock_llm)

        # Sample epic data
        self.sample_epics = [
            {"key": "PROJ-10", "summary": "User Authentication System"},
            {"key": "PROJ-20", "summary": "Payment Gateway Integration"},
            {"key": "PROJ-30", "summary": "Product Catalog and Search"},
        ]

    def test_match_ticket_to_epic_success(self):
        """Test successful ticket-to-epic matching."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "suggested_epic_key": "PROJ-10",
                "confidence": 0.92,
                "reason": "Ticket mentions login and authentication features",
            }
        )
        self.mock_llm.invoke.return_value = mock_response

        # Test matching
        result = self.matcher.match_ticket_to_epic(
            ticket_key="PROJ-123",
            ticket_summary="Implement OAuth2 login flow",
            ticket_description="Add Google and GitHub OAuth2 authentication",
            available_epics=self.sample_epics,
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["ticket_key"], "PROJ-123")
        self.assertEqual(result["suggested_epic_key"], "PROJ-10")
        self.assertEqual(result["confidence"], 0.92)
        self.assertIn("authentication", result["reason"].lower())

    def test_match_ticket_with_markdown_code_block(self):
        """Test parsing LLM response with markdown code blocks."""
        # Mock LLM response with markdown
        mock_response = Mock()
        mock_response.content = """```json
{
    "suggested_epic_key": "PROJ-20",
    "confidence": 0.85,
    "reason": "Payment processing related"
}
```"""
        self.mock_llm.invoke.return_value = mock_response

        result = self.matcher.match_ticket_to_epic(
            ticket_key="PROJ-456",
            ticket_summary="Add Stripe payment processing",
            ticket_description=None,
            available_epics=self.sample_epics,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["suggested_epic_key"], "PROJ-20")
        self.assertEqual(result["confidence"], 0.85)

    def test_match_ticket_invalid_epic_key(self):
        """Test handling of invalid epic key from AI."""
        # Mock LLM response with invalid epic
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "suggested_epic_key": "PROJ-999",  # Not in available epics
                "confidence": 0.70,
                "reason": "Some reason",
            }
        )
        self.mock_llm.invoke.return_value = mock_response

        result = self.matcher.match_ticket_to_epic(
            ticket_key="PROJ-789",
            ticket_summary="Test ticket",
            ticket_description=None,
            available_epics=self.sample_epics,
        )

        # Should return None for invalid epic
        self.assertIsNone(result)

    def test_match_ticket_no_epics_available(self):
        """Test matching with no available epics."""
        result = self.matcher.match_ticket_to_epic(
            ticket_key="PROJ-999",
            ticket_summary="Test ticket",
            ticket_description=None,
            available_epics=[],
        )

        self.assertIsNone(result)

    def test_match_ticket_llm_error(self):
        """Test handling of LLM API errors."""
        # Mock LLM to raise exception
        self.mock_llm.invoke.side_effect = Exception("API Error")

        result = self.matcher.match_ticket_to_epic(
            ticket_key="PROJ-111",
            ticket_summary="Test ticket",
            ticket_description=None,
            available_epics=self.sample_epics,
        )

        self.assertIsNone(result)

    def test_batch_match_tickets(self):
        """Test batch matching of multiple tickets."""
        # Setup mock responses for multiple tickets
        responses = [
            {
                "suggested_epic_key": "PROJ-10",
                "confidence": 0.90,
                "reason": "Auth related",
            },
            {
                "suggested_epic_key": "PROJ-20",
                "confidence": 0.85,
                "reason": "Payment related",
            },
            {
                "suggested_epic_key": "PROJ-30",
                "confidence": 0.45,
                "reason": "Low confidence",
            },  # Below threshold
        ]

        def mock_invoke(messages):
            response = Mock()
            response.content = json.dumps(responses.pop(0))
            return response

        self.mock_llm.invoke.side_effect = mock_invoke

        tickets = [
            {"key": "PROJ-100", "summary": "Login feature", "description": ""},
            {"key": "PROJ-101", "summary": "Payment processing", "description": ""},
            {"key": "PROJ-102", "summary": "Search feature", "description": ""},
        ]

        results = self.matcher.batch_match_tickets(
            tickets=tickets, available_epics=self.sample_epics, confidence_threshold=0.5
        )

        # Should only return 2 matches (third is below threshold)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["suggested_epic_key"], "PROJ-10")
        self.assertEqual(results[1]["suggested_epic_key"], "PROJ-20")

    def test_categorize_by_confidence(self):
        """Test confidence-based categorization."""
        match_results = [
            {"ticket_key": "T1", "confidence": 0.95, "suggested_epic_key": "E1"},
            {"ticket_key": "T2", "confidence": 0.82, "suggested_epic_key": "E2"},
            {"ticket_key": "T3", "confidence": 0.65, "suggested_epic_key": "E3"},
            {"ticket_key": "T4", "confidence": 0.45, "suggested_epic_key": "E4"},
        ]

        categorized = self.matcher.categorize_by_confidence(match_results)

        # Check counts
        self.assertEqual(len(categorized["high"]), 2)  # 0.95, 0.82
        self.assertEqual(len(categorized["medium"]), 1)  # 0.65
        self.assertEqual(len(categorized["low"]), 1)  # 0.45

        # Verify correct categorization
        self.assertEqual(categorized["high"][0]["confidence"], 0.95)
        self.assertEqual(categorized["high"][1]["confidence"], 0.82)
        self.assertEqual(categorized["medium"][0]["confidence"], 0.65)
        self.assertEqual(categorized["low"][0]["confidence"], 0.45)


if __name__ == "__main__":
    unittest.main()
