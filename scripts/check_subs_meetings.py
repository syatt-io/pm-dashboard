#!/usr/bin/env python3
"""Check if any Fireflies meetings were tagged with SUBS project."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_subs_meetings():
    """Check for Fireflies meetings tagged with SUBS."""

    service = VectorSearchService()

    if not service.is_available():
        print("❌ Pinecone not available")
        return

    print("✅ Pinecone connected\n")

    # Search for general term that should match SUBS meetings
    print("=" * 60)
    print("TEST: Search 'meeting' for SUBS project")
    print("=" * 60)
    results = service.search(
        query="meeting",
        top_k=50,
        days_back=365,
        user_email="mike.samimi@syatt.io",
        project_key="SUBS"
    )

    fireflies_results = [r for r in results if r.source == 'fireflies']

    print(f"✅ Total results: {len(results)}")
    print(f"📧 Fireflies results: {len(fireflies_results)}")

    if fireflies_results:
        print("\n🎯 Fireflies meeting titles:")
        for result in fireflies_results[:10]:
            print(f"   - {result.title}")
    else:
        print("\n⚠️  No Fireflies meetings found with SUBS project tag")
        print("\nPossible reasons:")
        print("  1. No Fireflies meetings in the last year have SUBS keywords in titles")
        print("  2. Keywords might be too specific - try adding more variations")
        print(f"\nCurrent SUBS keywords: {['bugz', 'sb', 'snuggle', 'snuggle bugz', 'snugglebugz', 'subs', 'subscription', 'sbug', 'snugz']}")

if __name__ == "__main__":
    check_subs_meetings()
