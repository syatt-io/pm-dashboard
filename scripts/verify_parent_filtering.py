#!/usr/bin/env python3
"""Quick test to verify parent-based filtering works with newly ingested pages."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
from src.services.vector_ingest import VectorIngestService
from src.integrations.notion_api import NotionAPIClient
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_parent_filtering():
    """Verify parent-based filtering by:
    1. Ingest recent pages with parent metadata
    2. Query using a known parent page ID
    3. Verify child pages are returned
    """

    logger.info("🧪 Verifying parent-based filtering...\n")

    try:
        # Initialize services
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)
        vector_service = VectorSearchService()
        ingest_service = VectorIngestService()

        if not vector_service.is_available():
            logger.error("❌ Pinecone not available")
            return

        # Step 1: Get recent pages and ingest with parent metadata
        logger.info("📥 Fetching recent Notion pages (90 days)...")
        pages = notion_client.get_all_pages(days_back=90)
        logger.info(f"   Found {len(pages)} pages")

        # Get full content for pages
        logger.info("📝 Fetching full content...")
        full_content_map = {}
        for i, page in enumerate(pages):
            if i % 10 == 0 and i > 0:
                logger.info(f"   Progress: {i}/{len(pages)} pages...")

            page_id = page['id']
            try:
                blocks = notion_client.get_page_blocks(page_id)
                full_content_map[page_id] = notion_client.extract_text_from_blocks(blocks)
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to get content for {page_id}: {e}")
                full_content_map[page_id] = ""

        # Step 2: Ingest pages with parent metadata
        logger.info(f"\n📤 Ingesting {len(pages)} pages with parent metadata...")
        count = ingest_service.ingest_notion_pages(pages, full_content_map)
        logger.info(f"✅ Ingested {count} pages\n")

        # Step 3: Find a parent with children to test
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

        # Get the parent with most children
        sorted_parents = sorted(
            parent_map.items(),
            key=lambda x: len(x[1]['children']),
            reverse=True
        )

        if not sorted_parents:
            logger.error("❌ No parent pages found to test")
            return

        test_parent_id = sorted_parents[0][0]
        test_children = sorted_parents[0][1]['children']

        logger.info(f"🎯 Testing with parent: {test_parent_id[:8]}...")
        logger.info(f"   Has {len(test_children)} child pages:")
        for child in test_children[:3]:
            logger.info(f"   • {child['title'][:60]}")
        if len(test_children) > 3:
            logger.info(f"   ... and {len(test_children) - 3} more\n")

        # Step 4: Query Pinecone directly to verify parent filtering
        logger.info("🔍 Testing direct Pinecone query with parent filter...")

        query_embedding = vector_service.get_embedding("test query")
        if not query_embedding:
            logger.error("❌ Failed to get query embedding")
            return

        # Test filter with parent ID
        test_filter = {
            "$or": [
                {"page_id": test_parent_id},
                {"parent_id": test_parent_id}
            ]
        }

        logger.info(f"   Filter: {test_filter}")

        results = vector_service.pinecone_index.query(
            vector=query_embedding,
            top_k=50,
            filter=test_filter,
            include_metadata=True
        )

        matches = results.get('matches', [])
        logger.info(f"✅ Found {len(matches)} results using parent filter\n")

        if matches:
            logger.info("📄 Sample results:")
            for i, match in enumerate(matches[:5], 1):
                metadata = match.get('metadata', {})
                title = metadata.get('title', 'Untitled')
                page_id = metadata.get('page_id', 'unknown')
                parent_id = metadata.get('parent_id', 'none')

                is_parent = page_id == test_parent_id
                is_child = parent_id == test_parent_id

                logger.info(f"   {i}. {title[:60]}")
                logger.info(f"      page_id: {page_id[:8]}...")
                logger.info(f"      parent_id: {parent_id[:8] if parent_id else 'None'}...")
                logger.info(f"      Match type: {'PARENT PAGE' if is_parent else 'CHILD PAGE' if is_child else 'UNKNOWN'}")
                logger.info("")

            # Verify we got both parent and children
            parent_matches = [m for m in matches if m.get('metadata', {}).get('page_id') == test_parent_id]
            child_matches = [m for m in matches if m.get('metadata', {}).get('parent_id') == test_parent_id]

            logger.info(f"✅ Verification Summary:")
            logger.info(f"   • Parent page matches: {len(parent_matches)}")
            logger.info(f"   • Child page matches: {len(child_matches)}")
            logger.info(f"   • Total matches: {len(matches)}")

            if len(parent_matches) > 0 or len(child_matches) > 0:
                logger.info(f"\n✅ SUCCESS: Parent-based filtering is working!")
            else:
                logger.warning(f"\n⚠️  WARNING: Got results but none matched parent/child criteria")
        else:
            logger.warning("⚠️  No results found - may need to wait for backfill to complete")

    except Exception as e:
        logger.error(f"❌ Error verifying parent filtering: {e}", exc_info=True)


if __name__ == "__main__":
    verify_parent_filtering()
