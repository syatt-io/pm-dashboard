"""Test JIRA search only."""

import asyncio
import logging

import pytest

from src.services.context_search import ContextSearchService

# Enable debug logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


@pytest.mark.asyncio
async def test_jira():
    """Test Jira source only."""
    search_service = ContextSearchService()
    query = "PDP changes for SUBS"

    print(f"\n{'='*80}")
    print(f"Testing JIRA search for: '{query}'")
    print(f"{'='*80}\n")

    try:
        results = await search_service.search(
            query=query,
            days_back=90,
            sources=["jira"],  # Only Jira
            user_id=1,
            debug=True,  # Enable debug to see what's happening
        )

        print(f"\n✅ JIRA: Found {len(results.results)} results")
        if results.results:
            for i, result in enumerate(results.results[:5], 1):
                print(f"  [{i}] {result.title[:80]}")
                print(f"      Score: {result.relevance_score:.3f}")
                print(f"      URL: {result.url}")
        else:
            print("  No results found")
    except Exception as e:
        print(f"❌ JIRA: Error - {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_jira())
