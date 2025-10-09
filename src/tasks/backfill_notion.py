#!/usr/bin/env python3
"""One-time Notion backfill script for production.

This script fetches all Notion pages from the last 365 days and ingests
them into the Pinecone vector database. Run once to populate historical data.

Usage:
    python src/tasks/backfill_notion.py
"""

import logging
import sys
from src.services.vector_ingest import VectorIngestService
from src.integrations.notion_api import NotionAPIClient
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_notion_pages(days_back: int = 365):
    """Backfill all Notion pages from the last N days."""
    logger.info(f"🔄 Starting Notion backfill ({days_back} days)...")

    # Initialize services
    try:
        ingest_service = VectorIngestService()
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        return 1

    # Get all pages (with pagination)
    logger.info("📥 Fetching all pages from Notion (this may take a while)...")
    try:
        pages = notion_client.get_all_pages(days_back=days_back)
        logger.info(f"✅ Found {len(pages)} pages")
    except Exception as e:
        logger.error(f"❌ Failed to fetch pages: {e}")
        return 1

    if not pages:
        logger.warning("⚠️  No pages found - check Notion API key and permissions")
        return 0

    # Fetch full content for each page
    logger.info("📝 Fetching full content for each page...")
    full_content_map = {}
    failed_count = 0

    for i, page in enumerate(pages, 1):
        try:
            if i % 10 == 0:
                logger.info(f"   Progress: {i}/{len(pages)} pages processed...")

            page_id = page.get('id', '')
            if page_id:
                full_content = notion_client.get_full_page_content(page_id)
                if full_content and full_content.strip():
                    full_content_map[page_id] = full_content
                else:
                    failed_count += 1
        except Exception as e:
            logger.error(f"Error fetching content for page {page_id}: {e}")
            failed_count += 1

    logger.info(f"✅ Fetched content for {len(full_content_map)} pages")
    if failed_count > 0:
        logger.warning(
            f"⚠️  Failed to fetch content for {failed_count} pages "
            "(likely empty or permission issues)"
        )

    # Ingest into Pinecone
    logger.info("📊 Ingesting into Pinecone...")
    try:
        total_ingested = ingest_service.ingest_notion_pages(
            pages=pages,
            full_content_map=full_content_map
        )
        logger.info(f"✅ Notion backfill complete! Total ingested: {total_ingested} pages")
        return 0
    except Exception as e:
        logger.error(f"❌ Failed to ingest pages: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(backfill_notion_pages())
