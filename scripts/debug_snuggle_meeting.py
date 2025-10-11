#!/usr/bin/env python3
"""Debug: Find meetings with 'snuggle' in title to verify tagging works."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_snuggle_meetings():
    """Search for meetings with 'snuggle' in title without project filter."""

    service = VectorSearchService()

    if not service.is_available():
        print("❌ Pinecone not available")
        return

    print("✅ Pinecone connected\n")

    # Search for 'snuggle' WITHOUT project filter to see if meeting exists at all
    print("=" * 60)
    print("TEST 1: Search 'snuggle bugz weekly' WITHOUT project filter")
    print("=" * 60)
    results = service.search(
        query="snuggle bugz weekly syatt",
        top_k=50,
        days_back=365,
        user_email="mike.samimi@syatt.io"
    )

    fireflies_results = [r for r in results if r.source == 'fireflies']

    print(f"✅ Total results: {len(results)}")
    print(f"📧 Fireflies results: {len(fireflies_results)}")

    if fireflies_results:
        print("\n🎯 Fireflies meeting titles found:")
        for i, result in enumerate(fireflies_results[:10], 1):
            print(f"\n   {i}. {result.title}")
            print(f"      Date: {result.date}")
            print(f"      Score: {result.relevance_score:.3f}")
    else:
        print("\n⚠️  No Fireflies meetings found with 'snuggle bugz' in query")
        print("\nThis could mean:")
        print("  1. Meeting doesn't exist in Pinecone")
        print("  2. Meeting was filtered out by permissions")
        print("  3. Meeting is older than 365 days")

    # Now try WITH project filter
    print("\n" + "=" * 60)
    print("TEST 2: Search 'snuggle bugz weekly' WITH project=SUBS")
    print("=" * 60)
    results2 = service.search(
        query="snuggle bugz weekly syatt",
        top_k=50,
        days_back=365,
        user_email="mike.samimi@syatt.io",
        project_key="SUBS"
    )

    fireflies_results2 = [r for r in results2 if r.source == 'fireflies']

    print(f"✅ Total results: {len(results2)}")
    print(f"📧 Fireflies results: {len(fireflies_results2)}")

    if fireflies_results2:
        print("\n🎯 Fireflies meeting titles found:")
        for i, result in enumerate(fireflies_results2[:10], 1):
            print(f"\n   {i}. {result.title}")
            print(f"      Date: {result.date}")
            print(f"      Score: {result.relevance_score:.3f}")
    else:
        print("\n⚠️  No Fireflies meetings found with project filter")

if __name__ == "__main__":
    debug_snuggle_meetings()
