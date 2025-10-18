"""Test script to debug why Beauchamp Fireflies meetings aren't showing up in search."""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.context_search import ContextSearchService
from config.settings import settings

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_beauchamp_search():
    """Test search for Beauchamp meetings."""

    # Initialize search service
    search_service = ContextSearchService()

    # Test query from user
    query = "what Beauchamp's been focused on for the last 4 weeks"

    logger.info(f"🔍 Testing search: '{query}'")
    logger.info("=" * 80)

    # Perform search with Fireflies only
    results = await search_service.search(
        query=query,
        days_back=30,  # 4 weeks
        sources=['fireflies'],  # Only search Fireflies
        user_id=1,  # Use user ID 1 (admin)
        debug=True  # Enable debug logging
    )

    logger.info("=" * 80)
    logger.info(f"✅ Search complete!")
    logger.info(f"Total results: {len(results.results)}")

    # Show results by source
    by_source = {}
    for result in results.results:
        by_source[result.source] = by_source.get(result.source, 0) + 1

    logger.info(f"Results by source: {by_source}")

    # Show top 5 results
    logger.info("\n" + "=" * 80)
    logger.info("Top 5 Results:")
    logger.info("=" * 80)

    for i, result in enumerate(results.results[:5], 1):
        logger.info(f"\n{i}. [{result.source.upper()}] {result.title}")
        logger.info(f"   Date: {result.date.strftime('%Y-%m-%d')}")
        logger.info(f"   Score: {result.relevance_score:.3f}")
        logger.info(f"   Content: {result.content[:200]}...")

    # Check if we got any Fireflies results
    fireflies_count = sum(1 for r in results.results if r.source == 'fireflies')

    if fireflies_count == 0:
        logger.error("\n❌ NO FIREFLIES RESULTS FOUND!")
        logger.info("\nDebugging steps:")
        logger.info("1. Check if Fireflies data is in Pinecone")
        logger.info("2. Check if project keywords are set up for Beauchamp")
        logger.info("3. Check if Fireflies meetings have been indexed with project_tags")

        # Check project keywords
        logger.info("\n" + "=" * 80)
        logger.info("Checking project keywords for Beauchamp...")
        logger.info("=" * 80)

        from src.utils.database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT project_key, keyword FROM project_keywords WHERE LOWER(keyword) LIKE '%beauchamp%'")
            )
            beauchamp_keywords = list(result)

            if beauchamp_keywords:
                logger.info(f"✅ Found {len(beauchamp_keywords)} Beauchamp-related keywords:")
                for row in beauchamp_keywords:
                    logger.info(f"   {row[0]}: {row[1]}")
            else:
                logger.error("❌ No Beauchamp keywords found in database!")
    else:
        logger.info(f"\n✅ Found {fireflies_count} Fireflies results")

if __name__ == "__main__":
    asyncio.run(test_beauchamp_search())
