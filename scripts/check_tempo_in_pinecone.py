#!/usr/bin/env python3
"""Check if Tempo worklogs exist in Pinecone and show sample data."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_tempo_data():
    """Check if any Tempo worklogs exist in Pinecone."""

    logger.info("🔍 Checking for Tempo data in Pinecone...\n")

    try:
        vector_service = VectorSearchService()

        if not vector_service.is_available():
            logger.error("❌ Pinecone not available")
            return

        # Get query embedding
        query_embedding = vector_service.get_embedding("tempo")

        # Query for ANY Tempo worklogs (no date filter)
        filter_query = {"source": "tempo"}

        logger.info(f"🔍 Querying for any Tempo worklogs...\n")

        results = vector_service.pinecone_index.query(
            vector=query_embedding,
            top_k=10,  # Get first 10 to inspect
            filter=filter_query,
            include_metadata=True,
        )

        matches = results.get("matches", [])
        logger.info(f"✅ Found {len(matches)} Tempo worklogs in Pinecone\n")

        if not matches:
            logger.warning("⚠️  No Tempo worklogs found in Pinecone at all")
            logger.warning("    Run the backfill: python src/tasks/backfill_tempo.py")
            return

        # Show sample metadata from first few worklogs
        logger.info("=" * 80)
        logger.info("📋 SAMPLE TEMPO WORKLOGS (First 10)")
        logger.info("=" * 80)

        for i, match in enumerate(matches[:10], 1):
            metadata = match.get("metadata", {})

            logger.info(f"\n{i}. Worklog ID: {match.get('id', 'unknown')}")
            logger.info(f"   Author: {metadata.get('author_name', 'N/A')}")
            logger.info(f"   Issue: {metadata.get('issue_key', 'N/A')}")
            logger.info(f"   Date: {metadata.get('start_date', 'N/A')}")
            logger.info(
                f"   Hours: {float(metadata.get('time_spent_seconds', 0)) / 3600:.2f}"
            )
            logger.info(f"   Description: {metadata.get('description', 'N/A')[:100]}")

            # Check if timestamp_epoch exists
            if "timestamp_epoch" in metadata:
                from datetime import datetime

                epoch = metadata["timestamp_epoch"]
                date = datetime.fromtimestamp(epoch)
                logger.info(
                    f"   Timestamp: {date.strftime('%Y-%m-%d %H:%M:%S')} (epoch: {epoch})"
                )
            else:
                logger.warning(f"   ⚠️  No timestamp_epoch field!")

        logger.info("\n" + "=" * 80)
        logger.info("✅ Tempo data exists in Pinecone!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error checking Tempo data: {e}", exc_info=True)


if __name__ == "__main__":
    check_tempo_data()
