"""Test script to find meetings with 'Beauchamp' in the title."""

import asyncio
import logging
import os
import sys

import pytest

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

@pytest.mark.asyncio
async def test_beauchamp_titles():
    """Search for meetings with 'Beauchamp' in the title."""

    # Initialize search service
    search_service = ContextSearchService()

    # Search specifically for "Beauchamp Syatt" to find those weekly calls
    query = "Beauchamp Syatt weekly call"

    logger.info(f"🔍 Searching for: '{query}'")
    logger.info("=" * 80)

    # Perform search
    results = await search_service.search(
        query=query,
        days_back=30,
        sources=['fireflies'],
        user_id=1,
        debug=True
    )

    logger.info("=" * 80)
    logger.info(f"✅ Search complete! Found {len(results.results)} results")
    logger.info("=" * 80)

    # Look for meetings with "Beauchamp" in the title
    beauchamp_meetings = [r for r in results.results if 'beauchamp' in r.title.lower()]

    logger.info(f"\n📊 Meetings with 'Beauchamp' in title: {len(beauchamp_meetings)}")
    logger.info("=" * 80)

    if beauchamp_meetings:
        logger.info("\n✅ Found Beauchamp meetings:")
        for i, meeting in enumerate(beauchamp_meetings, 1):
            logger.info(f"\n{i}. {meeting.title}")
            logger.info(f"   Date: {meeting.date.strftime('%Y-%m-%d')}")
            logger.info(f"   Score: {meeting.relevance_score:.3f}")
            logger.info(f"   Source: {meeting.source}")
            logger.info(f"   Content preview: {meeting.content[:200]}...")
    else:
        logger.error("\n❌ NO meetings with 'Beauchamp' in the title found!")
        logger.info("\nShowing all results to debug:")
        logger.info("=" * 80)

        for i, result in enumerate(results.results[:10], 1):
            logger.info(f"\n{i}. [{result.source.upper()}] {result.title}")
            logger.info(f"   Date: {result.date.strftime('%Y-%m-%d')}")
            logger.info(f"   Score: {result.relevance_score:.3f}")

        # Check Pinecone directly to see if Beauchamp meetings exist
        logger.info("\n" + "=" * 80)
        logger.info("Checking Pinecone directly for Beauchamp meetings...")
        logger.info("=" * 80)

        from src.services.vector_search import VectorSearchService

        vector_search = VectorSearchService()

        # Query Pinecone with a filter for Fireflies source
        # and search for "Beauchamp" in metadata
        if vector_search.is_available():
            try:
                # Get embedding for "Beauchamp Syatt weekly"
                embedding = vector_search.get_embedding("Beauchamp Syatt weekly")

                if embedding:
                    # Query Pinecone directly
                    from datetime import datetime, timedelta
                    cutoff = datetime.now() - timedelta(days=30)

                    results = vector_search.pinecone_index.query(
                        vector=embedding,
                        top_k=100,  # Get more results
                        filter={
                            "$and": [
                                {"source": "fireflies"},
                                {"timestamp_epoch": {"$gte": int(cutoff.timestamp())}}
                            ]
                        },
                        include_metadata=True
                    )

                    # Look for Beauchamp in titles
                    beauchamp_in_pinecone = []
                    for match in results.get('matches', []):
                        metadata = match.get('metadata', {})
                        title = metadata.get('title', '').lower()
                        if 'beauchamp' in title:
                            beauchamp_in_pinecone.append({
                                'title': metadata.get('title'),
                                'date': metadata.get('date'),
                                'score': match.get('score'),
                                'id': match.get('id')
                            })

                    logger.info(f"\n📊 Pinecone direct query found {len(beauchamp_in_pinecone)} Beauchamp meetings:")

                    if beauchamp_in_pinecone:
                        for i, meeting in enumerate(beauchamp_in_pinecone[:20], 1):
                            logger.info(f"{i}. {meeting['title']} ({meeting['date']}) - Score: {meeting['score']:.3f}")
                    else:
                        logger.error("❌ No Beauchamp meetings found in Pinecone!")
                        logger.info("\nThis means the meetings haven't been indexed yet.")
                        logger.info("Run: POST /api/backfill/fireflies to index them.")

            except Exception as e:
                logger.error(f"Error querying Pinecone directly: {e}")

if __name__ == "__main__":
    asyncio.run(test_beauchamp_titles())
