"""Test script to debug Snuggle Bugz / Searchspring search query."""

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

async def test_snuggle_bugz_search():
    """Test search for Snuggle Bugz / Searchspring project."""

    # Initialize search service
    search_service = ContextSearchService()

    # Original query
    query = "what's the searchspring project about for snuggle bugz?"

    logger.info(f"🔍 Searching for: '{query}'")
    logger.info("=" * 80)

    # Perform search with all sources
    results = await search_service.search(
        query=query,
        days_back=90,
        sources=None,  # Search all sources
        user_id=1,
        debug=True
    )

    logger.info("=" * 80)
    logger.info(f"✅ Search complete! Found {len(results.results)} results")
    logger.info("=" * 80)

    # Show results by source
    by_source = {}
    for result in results.results:
        by_source[result.source] = by_source.get(result.source, 0) + 1

    logger.info(f"Results by source: {by_source}")

    if len(results.results) == 0:
        logger.error("\n❌ NO RESULTS FOUND!")
        logger.info("\nDebugging steps:")
        logger.info("1. Check if 'Snuggle Bugz' project exists in database")
        logger.info("2. Check if 'Searchspring' keyword is mapped to the project")
        logger.info("3. Check if there's any data in Pinecone with these keywords")

        # Check database for project
        logger.info("\n" + "=" * 80)
        logger.info("Checking database for Snuggle Bugz project...")
        logger.info("=" * 80)

        from src.utils.database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            # Check projects table
            result = conn.execute(
                text("SELECT key, name FROM projects WHERE LOWER(name) LIKE '%snuggle%'")
            )
            projects = list(result)

            if projects:
                logger.info(f"✅ Found {len(projects)} Snuggle Bugz-related projects:")
                for row in projects:
                    logger.info(f"   {row[0]}: {row[1]}")
                    
                    # Check keywords for this project
                    keyword_result = conn.execute(
                        text("SELECT keyword FROM project_keywords WHERE project_key = :key"),
                        {"key": row[0]}
                    )
                    keywords = [k[0] for k in keyword_result]
                    logger.info(f"   Keywords: {keywords}")
            else:
                logger.error("❌ No Snuggle Bugz projects found in database!")

            # Check for Searchspring keyword
            logger.info("\n" + "=" * 80)
            logger.info("Checking for 'Searchspring' keyword...")
            logger.info("=" * 80)

            result = conn.execute(
                text("SELECT project_key, keyword FROM project_keywords WHERE LOWER(keyword) LIKE '%searchspring%'")
            )
            searchspring_keywords = list(result)

            if searchspring_keywords:
                logger.info(f"✅ Found {len(searchspring_keywords)} Searchspring-related keywords:")
                for row in searchspring_keywords:
                    logger.info(f"   {row[0]}: {row[1]}")
            else:
                logger.error("❌ No Searchspring keywords found in database!")

        # Check Pinecone directly
        logger.info("\n" + "=" * 80)
        logger.info("Checking Pinecone for Searchspring/Snuggle Bugz data...")
        logger.info("=" * 80)

        from src.services.vector_search import VectorSearchService
        from datetime import datetime, timedelta

        vector_search = VectorSearchService()

        if vector_search.is_available():
            try:
                # Get embedding for query
                embedding = vector_search.get_embedding("searchspring snuggle bugz")

                if embedding:
                    # Query Pinecone directly without filters
                    cutoff = datetime.now() - timedelta(days=90)

                    pinecone_results = vector_search.pinecone_index.query(
                        vector=embedding,
                        top_k=100,
                        filter={
                            "timestamp_epoch": {"$gte": int(cutoff.timestamp())}
                        },
                        include_metadata=True
                    )

                    # Look for Searchspring or Snuggle Bugz mentions
                    searchspring_matches = []
                    snuggle_bugz_matches = []

                    for match in pinecone_results.get('matches', []):
                        metadata = match.get('metadata', {})
                        title = metadata.get('title', '').lower()
                        content = metadata.get('content_preview', '').lower()

                        if 'searchspring' in title or 'searchspring' in content:
                            searchspring_matches.append({
                                'title': metadata.get('title'),
                                'source': metadata.get('source'),
                                'score': match.get('score'),
                                'date': metadata.get('date')
                            })

                        if 'snuggle' in title or 'snuggle' in content:
                            snuggle_bugz_matches.append({
                                'title': metadata.get('title'),
                                'source': metadata.get('source'),
                                'score': match.get('score'),
                                'date': metadata.get('date')
                            })

                    logger.info(f"\n📊 Pinecone results with 'searchspring': {len(searchspring_matches)}")
                    if searchspring_matches:
                        for i, match in enumerate(searchspring_matches[:10], 1):
                            logger.info(f"{i}. [{match['source']}] {match['title']} (Score: {match['score']:.3f})")

                    logger.info(f"\n📊 Pinecone results with 'snuggle': {len(snuggle_bugz_matches)}")
                    if snuggle_bugz_matches:
                        for i, match in enumerate(snuggle_bugz_matches[:10], 1):
                            logger.info(f"{i}. [{match['source']}] {match['title']} (Score: {match['score']:.3f})")

            except Exception as e:
                logger.error(f"Error querying Pinecone directly: {e}")
    else:
        logger.info("\n✅ Found results! Top 5:")
        for i, result in enumerate(results.results[:5], 1):
            logger.info(f"\n{i}. [{result.source.upper()}] {result.title}")
            logger.info(f"   Date: {result.date.strftime('%Y-%m-%d')}")
            logger.info(f"   Score: {result.relevance_score:.3f}")

if __name__ == "__main__":
    asyncio.run(test_snuggle_bugz_search())
