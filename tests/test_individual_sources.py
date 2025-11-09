"""Test each search source individually to isolate issues."""
import asyncio
import logging

import pytest

from src.services.context_search import ContextSearchService

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

@pytest.mark.asyncio
async def test_individual_sources():
    """Test each source separately."""
    search_service = ContextSearchService()
    query = "PDP changes for SUBS"

    print(f"\n{'='*80}")
    print(f"Testing: '{query}'")
    print(f"{'='*80}\n")

    # Test each source individually
    for source in ['slack', 'jira', 'fireflies', 'notion']:
        print(f"\n{'='*80}")
        print(f"Testing {source.upper()} only")
        print(f"{'='*80}")

        try:
            results = await search_service.search(
                query=query,
                days_back=90,
                sources=[source],  # Only this source
                user_id=1,
                debug=False  # Disable verbose debug
            )

            print(f"✅ {source.upper()}: Found {len(results.results)} results")
            if results.results:
                for i, result in enumerate(results.results[:3], 1):
                    print(f"  [{i}] {result.title[:60]}... (score: {result.relevance_score:.3f})")
        except Exception as e:
            print(f"❌ {source.upper()}: Error - {e}")

if __name__ == "__main__":
    asyncio.run(test_individual_sources())
