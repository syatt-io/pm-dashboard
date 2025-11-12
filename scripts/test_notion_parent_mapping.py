#!/usr/bin/env python3
"""Test script to demonstrate how parent page mapping would work in practice.

This script:
1. Fetches sample Notion pages from the API
2. Shows parent page hierarchy information
3. Demonstrates how parent-based filtering would work
4. Validates whether this approach captures relevant pages
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.notion_api import NotionAPIClient
from config.settings import settings
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_notion_hierarchy():
    """Analyze Notion workspace to understand parent page structure."""

    logger.info("🔍 Analyzing Notion workspace hierarchy...\n")

    try:
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)

        # Fetch recent pages to analyze
        logger.info("📥 Fetching recent pages from Notion...")
        pages = notion_client.get_all_pages(days_back=90)

        logger.info(f"✅ Found {len(pages)} pages\n")

        if not pages:
            logger.warning("⚠️  No pages found in workspace")
            return

        # Analyze parent structure
        parent_map = defaultdict(list)  # parent_id -> list of child pages
        parent_info = {}  # parent_id -> parent details
        pages_without_parents = []

        logger.info("=" * 80)
        logger.info("PARENT PAGE ANALYSIS")
        logger.info("=" * 80 + "\n")

        for page in pages:
            page_id = page.get("id", "")
            title = get_page_title(page)
            parent = page.get("parent", {})
            parent_type = parent.get("type", "workspace")

            # Extract parent ID based on type
            parent_id = None
            if parent_type == "page_id":
                parent_id = parent.get("page_id")
            elif parent_type == "database_id":
                parent_id = parent.get("database_id")
            elif parent_type == "workspace":
                parent_id = "workspace"

            if parent_id and parent_id != "workspace":
                parent_map[parent_id].append(
                    {"id": page_id, "title": title, "parent_type": parent_type}
                )

                # Store parent info if we haven't seen it
                if parent_id not in parent_info:
                    parent_info[parent_id] = {"type": parent_type, "child_count": 0}
                parent_info[parent_id]["child_count"] += 1
            else:
                pages_without_parents.append({"id": page_id, "title": title})

        # Display results
        logger.info(f"📊 SUMMARY:")
        logger.info(f"   Total pages: {len(pages)}")
        logger.info(
            f"   Pages with parents: {sum(len(children) for children in parent_map.values())}"
        )
        logger.info(f"   Root/workspace pages: {len(pages_without_parents)}")
        logger.info(f"   Unique parents: {len(parent_map)}\n")

        # Show parent hierarchy
        logger.info("=" * 80)
        logger.info("PARENT → CHILD HIERARCHY (Top 10 Parents)")
        logger.info("=" * 80 + "\n")

        # Sort parents by child count
        sorted_parents = sorted(
            parent_map.items(), key=lambda x: len(x[1]), reverse=True
        )[:10]

        for parent_id, children in sorted_parents:
            parent_type = parent_info.get(parent_id, {}).get("type", "unknown")
            logger.info(f"📁 Parent: {parent_id[:8]}... ({parent_type})")
            logger.info(f"   └─ {len(children)} child pages:")

            for child in children[:5]:  # Show first 5 children
                logger.info(f"      • {child['title'][:60]}")

            if len(children) > 5:
                logger.info(f"      ... and {len(children) - 5} more")
            logger.info("")

        # Show root pages
        logger.info("=" * 80)
        logger.info("ROOT/WORKSPACE PAGES (Top 10)")
        logger.info("=" * 80 + "\n")

        for page in pages_without_parents[:10]:
            logger.info(f"   • {page['title'][:70]}")

        if len(pages_without_parents) > 10:
            logger.info(f"   ... and {len(pages_without_parents) - 10} more\n")

        # Practical recommendation
        logger.info("\n" + "=" * 80)
        logger.info("💡 RECOMMENDATION FOR PARENT-BASED FILTERING")
        logger.info("=" * 80 + "\n")

        # Calculate percentage of pages with parents
        pages_with_parents = sum(len(children) for children in parent_map.values())
        parent_coverage = (pages_with_parents / len(pages)) * 100 if pages else 0

        logger.info(f"✅ {parent_coverage:.1f}% of pages have a parent page/database")

        if parent_coverage > 70:
            logger.info("\n🎯 VERDICT: Parent-based filtering is HIGHLY VIABLE")
            logger.info("   • Most pages have parent pages/databases")
            logger.info(
                "   • Mapping ~{} parents would cover ~{} pages".format(
                    len(parent_map), pages_with_parents
                )
            )
            logger.info("   • This is much more scalable than mapping individual pages")
        elif parent_coverage > 40:
            logger.info("\n⚠️  VERDICT: Parent-based filtering is PARTIALLY VIABLE")
            logger.info("   • Significant portion of pages have parents")
            logger.info(
                "   • Recommend hybrid approach: parent filters + semantic search fallback"
            )
        else:
            logger.info("\n❌ VERDICT: Parent-based filtering is NOT VIABLE")
            logger.info("   • Most pages are root-level (no parent)")
            logger.info("   • Recommend pure semantic search without filters")

        # Show example filter query
        logger.info("\n" + "=" * 80)
        logger.info("📝 EXAMPLE: How Parent Filtering Would Work in Pinecone")
        logger.info("=" * 80 + "\n")

        if sorted_parents:
            example_parent_id = sorted_parents[0][0]
            example_children_count = len(sorted_parents[0][1])

            logger.info(f"If you map parent: {example_parent_id[:8]}...")
            logger.info(
                f"It would automatically include {example_children_count} child pages\n"
            )

            logger.info("Current Filter (individual pages):")
            logger.info('  {"page_id": {"$in": ["page1", "page2", "page3", ...]}}')
            logger.info(
                f"  ❌ Requires mapping {example_children_count} page IDs individually\n"
            )

            logger.info("Proposed Filter (parent-based):")
            logger.info('  {"$or": [')
            logger.info(
                f'    {{"page_id": "{example_parent_id}"}},  # Include parent page itself'
            )
            logger.info(
                f'    {{"parent_id": "{example_parent_id}"}}  # Include all children'
            )
            logger.info("  ]}")
            logger.info(
                f"  ✅ Just map 1 parent ID, get {example_children_count} pages automatically"
            )

        logger.info("\n✅ Analysis complete!")

    except Exception as e:
        logger.error(f"❌ Error analyzing Notion hierarchy: {e}", exc_info=True)


def get_page_title(page: dict) -> str:
    """Extract page title from Notion page object."""
    properties = page.get("properties", {})

    # Try to find title property
    for prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title":
            title_content = prop_value.get("title", [])
            if title_content:
                return title_content[0].get("plain_text", "Untitled")

    return "Untitled"


if __name__ == "__main__":
    analyze_notion_hierarchy()
