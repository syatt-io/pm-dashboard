#!/usr/bin/env python3
"""Quick test to verify parent-based filtering query works in Pinecone."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_parent_filter_query():
    """Test that parent_id filtering works in Pinecone queries."""

    logger.info("🧪 Testing parent_id filter in Pinecone queries...\n")

    try:
        vector_service = VectorSearchService()

        if not vector_service.is_available():
            logger.error("❌ Pinecone not available")
            return

        # Get a test query embedding
        query_embedding = vector_service.get_embedding("test query")
        if not query_embedding:
            logger.error("❌ Failed to get query embedding")
            return

        # Test 1: Query with parent_id filter to see if field exists
        logger.info("📊 Test 1: Check if parent_id field exists in any documents")
        logger.info("   Query: Find documents with parent_id field populated\n")

        test_filter_1 = {
            "$and": [{"source": "notion"}, {"parent_id": {"$exists": True}}]
        }

        results_1 = vector_service.pinecone_index.query(
            vector=query_embedding, top_k=5, filter=test_filter_1, include_metadata=True
        )

        matches_1 = results_1.get("matches", [])
        logger.info(
            f"✅ Found {len(matches_1)} Notion documents with parent_id field\n"
        )

        if matches_1:
            logger.info("📄 Sample documents with parent_id:")
            for i, match in enumerate(matches_1[:3], 1):
                metadata = match.get("metadata", {})
                logger.info(f"   {i}. {metadata.get('title', 'Untitled')[:60]}")
                logger.info(f"      page_id: {metadata.get('page_id', 'none')[:12]}...")
                logger.info(
                    f"      parent_id: {metadata.get('parent_id', 'none')[:12] if metadata.get('parent_id') else 'None'}..."
                )
                logger.info(f"      parent_type: {metadata.get('parent_type', 'none')}")
                logger.info("")
        else:
            logger.warning(
                "⚠️  No documents with parent_id found - backfill may still be in progress\n"
            )

        # Test 2: Query specific source to check total Notion documents
        logger.info("📊 Test 2: Count total Notion documents in index")

        test_filter_2 = {"source": "notion"}

        results_2 = vector_service.pinecone_index.query(
            vector=query_embedding,
            top_k=100,
            filter=test_filter_2,
            include_metadata=True,
        )

        matches_2 = results_2.get("matches", [])
        logger.info(f"✅ Found {len(matches_2)} total Notion documents\n")

        # Test 3: Verify the $or filter syntax works
        logger.info("📊 Test 3: Test $or filter syntax for parent-based filtering")

        if matches_1:
            # Use first parent_id we found
            test_parent_id = matches_1[0].get("metadata", {}).get("parent_id")

            if test_parent_id:
                logger.info(f"   Using parent_id: {test_parent_id[:12]}...\n")

                test_filter_3 = {
                    "$or": [{"page_id": test_parent_id}, {"parent_id": test_parent_id}]
                }

                results_3 = vector_service.pinecone_index.query(
                    vector=query_embedding,
                    top_k=50,
                    filter=test_filter_3,
                    include_metadata=True,
                )

                matches_3 = results_3.get("matches", [])
                logger.info(f"✅ $or filter returned {len(matches_3)} results")

                if matches_3:
                    parent_matches = [
                        m
                        for m in matches_3
                        if m.get("metadata", {}).get("page_id") == test_parent_id
                    ]
                    child_matches = [
                        m
                        for m in matches_3
                        if m.get("metadata", {}).get("parent_id") == test_parent_id
                    ]

                    logger.info(f"   • Parent page matches: {len(parent_matches)}")
                    logger.info(f"   • Child page matches: {len(child_matches)}\n")

                    logger.info(
                        "✅ SUCCESS: Parent-based filtering query syntax works!\n"
                    )
                else:
                    logger.warning("⚠️  WARNING: $or filter returned no results\n")

        # Summary
        logger.info("=" * 80)
        logger.info("📋 SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Pinecone connection: Working")
        logger.info(f"✅ Total Notion documents: {len(matches_2)}")
        logger.info(f"✅ Documents with parent_id: {len(matches_1)}")
        logger.info(
            f"✅ Parent filter query: {'Working' if matches_1 else 'Waiting for backfill'}"
        )

        if len(matches_1) > 0:
            percentage = (
                (len(matches_1) / len(matches_2) * 100) if len(matches_2) > 0 else 0
            )
            logger.info(
                f"✅ Backfill progress: {percentage:.1f}% of documents have parent_id"
            )

        logger.info("")

    except Exception as e:
        logger.error(f"❌ Error testing parent filter: {e}", exc_info=True)


if __name__ == "__main__":
    test_parent_filter_query()
