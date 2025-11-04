"""Diagnostic test for context search - verify all sources are being searched."""
import asyncio
import logging
from src.services.context_search import ContextSearchService

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_search():
    """Test search across all sources."""
    search_service = ContextSearchService()

    # Test query
    query = "PDP changes for SUBS"

    print(f"\n{'='*80}")
    print(f"Testing search for: '{query}'")
    print(f"{'='*80}\n")

    # Search with debug enabled
    results = await search_service.search(
        query=query,
        days_back=90,
        sources=['slack', 'fireflies', 'jira', 'notion'],
        user_id=1,  # Use user_id 1 for testing
        debug=True
    )

    print(f"\n{'='*80}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Total results: {len(results.results)}")

    # Count by source
    source_counts = {}
    for result in results.results:
        source_counts[result.source] = source_counts.get(result.source, 0) + 1

    print(f"\nResults by source:")
    for source in ['slack', 'fireflies', 'jira', 'notion']:
        count = source_counts.get(source, 0)
        print(f"  {source}: {count}")

    print(f"\nSummary: {results.summary[:200] if results.summary else 'No summary'}")

    print(f"\n{'='*80}")
    print(f"TOP 5 RESULTS")
    print(f"{'='*80}")
    for i, result in enumerate(results.results[:5], 1):
        print(f"\n[{i}] {result.source.upper()} - {result.title}")
        print(f"    Score: {result.relevance_score:.3f}")
        print(f"    Date: {result.date}")
        print(f"    Preview: {result.content[:100]}...")
        if result.url:
            print(f"    URL: {result.url}")

if __name__ == "__main__":
    asyncio.run(test_search())
