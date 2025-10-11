#!/usr/bin/env python3
"""Test if Fireflies meetings exist in Pinecone that match SUBS keywords."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService

def test_fireflies_filter():
    """Test Fireflies filtering with SUBS project."""

    # Initialize service
    service = VectorSearchService()

    if not service.is_available():
        print("❌ Pinecone not available")
        return

    print("✅ Pinecone connected\n")

    # Test 1: Search without project filter (should show Fireflies)
    print("=" * 60)
    print("TEST 1: Search 'searchspring' WITHOUT project filter")
    print("=" * 60)
    results = service.search(
        query="searchspring",
        top_k=20,
        days_back=365,
        user_email="mike.samimi@syatt.io"
    )

    fireflies_count = len([r for r in results if r.source == 'fireflies'])
    print(f"✅ Total results: {len(results)}")
    print(f"📧 Fireflies results: {fireflies_count}")

    if fireflies_count > 0:
        print("\n🎯 Sample Fireflies titles:")
        for result in results[:5]:
            if result.source == 'fireflies':
                print(f"   - {result.title}")

    # Test 2: Search WITH project filter (should still show Fireflies if keywords match)
    print("\n" + "=" * 60)
    print("TEST 2: Search 'searchspring' WITH project=SUBS")
    print("=" * 60)
    results2 = service.search(
        query="searchspring",
        top_k=20,
        days_back=365,
        user_email="mike.samimi@syatt.io",
        project_key="SUBS"
    )

    fireflies_count2 = len([r for r in results2 if r.source == 'fireflies'])
    print(f"✅ Total results: {len(results2)}")
    print(f"📧 Fireflies results: {fireflies_count2}")

    if fireflies_count2 > 0:
        print("\n🎯 Sample Fireflies titles:")
        for result in results2[:5]:
            if result.source == 'fireflies':
                print(f"   - {result.title}")
    else:
        print("\n⚠️  No Fireflies results with project filter!")
        print("This means either:")
        print("  1. Keywords don't match any Fireflies meeting titles")
        print("  2. The filter logic has a bug")

    # Test 3: Check what keywords are configured for SUBS
    print("\n" + "=" * 60)
    print("TEST 3: Check SUBS project keywords")
    print("=" * 60)
    from src.utils.database import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT keyword FROM project_keywords WHERE project_key = 'SUBS'")
        )
        keywords = [row[0] for row in result]
        print(f"✅ SUBS keywords: {keywords}")

if __name__ == "__main__":
    test_fireflies_filter()
