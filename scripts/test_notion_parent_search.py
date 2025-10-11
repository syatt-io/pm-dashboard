#!/usr/bin/env python3
"""Test how parent-based Notion filtering would work in actual search queries.

This script demonstrates:
1. Current individual page filtering
2. Proposed parent-based filtering
3. Comparison of results
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
from src.integrations.notion_api import NotionAPIClient
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_parent_search():
    """Test search with parent-based filtering vs individual pages."""

    logger.info("🔍 Testing Notion parent-based search filtering...\n")

    try:
        # Initialize services
        vector_service = VectorSearchService()
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)

        if not vector_service.is_available():
            logger.error("❌ Pinecone not available")
            return

        # Fetch recent pages to identify parents
        logger.info("📥 Fetching Notion hierarchy...")
        pages = notion_client.get_all_pages(days_back=90)

        # Find a parent with multiple children (use the Projects database)
        parent_map = {}
        for page in pages:
            parent = page.get('parent', {})
            parent_type = parent.get('type', 'workspace')

            parent_id = None
            if parent_type == 'page_id':
                parent_id = parent.get('page_id')
            elif parent_type == 'database_id':
                parent_id = parent.get('database_id')

            if parent_id:
                if parent_id not in parent_map:
                    parent_map[parent_id] = {
                        'type': parent_type,
                        'children': []
                    }
                parent_map[parent_id]['children'].append({
                    'id': page['id'],
                    'title': notion_client.get_page_title(page)
                })

        # Get the Projects database (most children)
        sorted_parents = sorted(
            parent_map.items(),
            key=lambda x: len(x[1]['children']),
            reverse=True
        )

        if not sorted_parents:
            logger.error("❌ No parent pages found")
            return

        # Use the parent with most children (Projects database)
        test_parent_id = sorted_parents[0][0]
        test_parent_type = sorted_parents[0][1]['type']
        test_children = sorted_parents[0][1]['children']

        logger.info(f"✅ Found test parent: {test_parent_id[:8]}... ({test_parent_type})")
        logger.info(f"   └─ Has {len(test_children)} child pages\n")

        # Show some example child pages
        logger.info("📄 Example child pages:")
        for child in test_children[:5]:
            logger.info(f"   • {child['title'][:60]}")
        if len(test_children) > 5:
            logger.info(f"   ... and {len(test_children) - 5} more\n")

        # Test search query
        test_query = "Snuggle Bugz"  # Known project
        logger.info(f"🔎 Test query: '{test_query}'\n")

        # ====================================================================
        # TEST 1: Pure semantic search (no filters)
        # ====================================================================
        logger.info("=" * 80)
        logger.info("TEST 1: Pure Semantic Search (No Filters)")
        logger.info("=" * 80)

        results_no_filter = vector_service.search(
            query=test_query,
            top_k=10,
            days_back=90,
            user_email="mike.samimi@syatt.io"
        )

        notion_results_no_filter = [r for r in results_no_filter if r.source == 'notion']
        logger.info(f"✅ Found {len(notion_results_no_filter)} Notion results\n")

        if notion_results_no_filter:
            for i, result in enumerate(notion_results_no_filter[:5], 1):
                logger.info(f"   {i}. {result.title[:70]}")
                logger.info(f"      Score: {result.relevance_score:.3f}\n")

        # ====================================================================
        # TEST 2: Current approach - filter by individual page IDs
        # ====================================================================
        logger.info("=" * 80)
        logger.info("TEST 2: Current Approach - Individual Page IDs")
        logger.info("=" * 80)

        # Simulate current filtering (get individual child IDs)
        individual_page_ids = [child['id'] for child in test_children]
        logger.info(f"Filter: {len(individual_page_ids)} individual page IDs")
        logger.info(f"Filter query: {{'page_id': {{'$in': [{individual_page_ids[0][:8]}..., ...]}}}}\n")

        # Note: This would require custom filter - current implementation doesn't support it
        logger.info("⚠️  Current implementation doesn't support arbitrary page_id filters")
        logger.info("    Would need to be implemented as project resource mapping\n")

        # ====================================================================
        # TEST 3: Proposed approach - filter by parent ID
        # ====================================================================
        logger.info("=" * 80)
        logger.info("TEST 3: Proposed Approach - Parent ID Filter")
        logger.info("=" * 80)

        logger.info(f"Filter: Single parent ID: {test_parent_id[:8]}...")
        logger.info(f"Filter query:")
        logger.info(f"  {{'$or': [")
        logger.info(f"    {{'page_id': '{test_parent_id}'}},")
        logger.info(f"    {{'parent_id': '{test_parent_id}'}}")
        logger.info(f"  ]}}\n")

        logger.info("Benefits:")
        logger.info(f"  ✅ Just 1 parent ID instead of {len(individual_page_ids)} individual IDs")
        logger.info(f"  ✅ Automatically includes new child pages (no manual updates)")
        logger.info(f"  ✅ Captures hierarchical relationships")
        logger.info(f"  ✅ More scalable for large workspaces\n")

        # ====================================================================
        # COMPARISON SUMMARY
        # ====================================================================
        logger.info("=" * 80)
        logger.info("📊 COMPARISON SUMMARY")
        logger.info("=" * 80 + "\n")

        logger.info("Current Approach (Individual Pages):")
        logger.info(f"  • Requires mapping: {len(individual_page_ids)} page IDs")
        logger.info(f"  • Manual updates: Required when new pages added")
        logger.info(f"  • Scalability: Poor (grows linearly with pages)")
        logger.info(f"  • Maintenance: High (need to track every page)\n")

        logger.info("Proposed Approach (Parent Pages):")
        logger.info(f"  • Requires mapping: 1 parent ID")
        logger.info(f"  • Manual updates: None (automatic)")
        logger.info(f"  • Scalability: Excellent (constant complexity)")
        logger.info(f"  • Maintenance: Low (set once and forget)\n")

        logger.info("Efficiency Gain:")
        efficiency = (1 - (1 / len(individual_page_ids))) * 100
        logger.info(f"  🎯 {efficiency:.1f}% reduction in IDs to manage")
        logger.info(f"  🎯 {len(individual_page_ids)}x fewer IDs in filter query\n")

        # ====================================================================
        # IMPLEMENTATION REQUIREMENTS
        # ====================================================================
        logger.info("=" * 80)
        logger.info("🔧 IMPLEMENTATION REQUIREMENTS")
        logger.info("=" * 80 + "\n")

        logger.info("1. Update Vector Ingestion (src/services/vector_ingest.py):")
        logger.info("   • Extract parent_id from page.parent")
        logger.info("   • Add parent_id and parent_type to metadata")
        logger.info("   • Store during Notion page ingestion\n")

        logger.info("2. Update Vector Search (src/services/vector_search.py):")
        logger.info("   • Modify _get_project_resource_filters()")
        logger.info("   • Change filter from page_id to parent_id")
        logger.info("   • Support both page_id match AND parent_id match\n")

        logger.info("3. Update UI Labels (frontend/src/components/Projects.tsx):")
        logger.info("   • Change 'Notion Pages' to 'Notion Parent Pages/Databases'")
        logger.info("   • Add tooltip explaining parent-based filtering\n")

        logger.info("4. Run Notion Backfill:")
        logger.info("   • Re-ingest existing pages with parent_id metadata")
        logger.info("   • POST /api/backfill/notion?days=365\n")

        logger.info("✅ Test complete!")

    except Exception as e:
        logger.error(f"❌ Error testing parent search: {e}", exc_info=True)


if __name__ == "__main__":
    test_parent_search()
