"""Simulate the exact Slack bot search flow to debug why results show as empty."""

import asyncio
import logging
import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.context_search import ContextSearchService

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_slack_search():
    """Simulate exact Slack bot search flow."""

    # Initialize search service
    search_service = ContextSearchService()

    # Original query
    query = "what's the searchspring project about for snuggle bugz?"
    
    logger.info(f"=== SIMULATING SLACK BOT SEARCH ===")
    logger.info(f"Query: '{query}'")
    logger.info("=" * 80)

    # Simulate Slack bot search (same parameters as slack_chat_service.py line 530-536)
    results = await search_service.search(
        query=query,
        days_back=90,  # Default in handle_question
        user_id=1,  # Assuming user ID 1 exists
        detail_level="slack",  # IMPORTANT: Slack uses "slack" detail level
        project=None  # No explicit project in this query
    )

    logger.info("=" * 80)
    logger.info("=== SEARCH RESULTS ===")
    logger.info(f"results.query: {results.query}")
    logger.info(f"len(results.results): {len(results.results)}")
    logger.info(f"results.summary: {results.summary[:200] if results.summary else 'None'}...")
    logger.info(f"results.citations: {len(results.citations) if results.citations else 0} citations")
    logger.info("=" * 80)

    # Check the condition that Slack bot uses (line 538)
    if not results.results:
        logger.error("❌ CONDITION TRIGGERED: not results.results is TRUE")
        logger.error("    This is why Slack bot shows 'No results found'")
        return
    else:
        logger.info("✅ CONDITION NOT TRIGGERED: results.results has items")

    # Check the summary condition (line 548)
    if results.summary:
        logger.info("✅ results.summary exists - Slack bot would show summary")
        logger.info(f"   Summary preview: {results.summary[:200]}...")
    else:
        logger.error("❌ results.summary is None or empty - Slack bot would fall back to streaming")

if __name__ == "__main__":
    asyncio.run(test_slack_search())
