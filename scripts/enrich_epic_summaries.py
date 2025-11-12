#!/usr/bin/env python3
"""
Enrich epic_hours table with actual epic summaries from Jira.

For records where epic_summary == epic_key (ticket key), this script
fetches the actual epic name from Jira and updates the epic_summary field.

Usage:
    python scripts/enrich_epic_summaries.py
    python scripts/enrich_epic_summaries.py --dry-run  # Preview without saving
"""

import sys
import logging
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
import httpx
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_epics_needing_enrichment(session) -> Dict[str, Set[str]]:
    """Get epic keys that need epic summary enrichment (where epic_summary == epic_key).

    Returns:
        Dict mapping project_key -> set of epic_keys that need enrichment
    """
    logger.info("Finding epics with epic_summary == epic_key...")

    # Query for records where epic_summary equals epic_key (using ticket key pattern)
    results = (
        session.query(EpicHours.project_key, EpicHours.epic_key, EpicHours.epic_summary)
        .distinct()
        .all()
    )

    # Group by project, filter where epic_summary == epic_key
    epics_by_project = defaultdict(set)

    for project_key, epic_key, epic_summary in results:
        # Check if epic_summary is the same as epic_key (needs enrichment)
        if epic_summary and epic_summary == epic_key:
            epics_by_project[project_key].add(epic_key)

    total_epics = sum(len(epics) for epics in epics_by_project.values())
    logger.info(f"Found {total_epics} epics across {len(epics_by_project)} projects needing enrichment")

    for project_key, epics in sorted(epics_by_project.items()):
        logger.info(f"  {project_key}: {len(epics)} epics")

    return dict(epics_by_project)


def fetch_epic_summaries_from_jira(epics_by_project: Dict[str, Set[str]]) -> Dict[str, str]:
    """Fetch actual epic summaries from Jira.

    Args:
        epics_by_project: Dict of project_key -> set of epic_keys

    Returns:
        Dict mapping epic_key -> epic_summary
    """
    logger.info("Fetching epic summaries from Jira...")

    # Get Jira credentials from environment
    jira_url = os.environ.get('JIRA_URL')
    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_token = os.environ.get('JIRA_API_TOKEN')

    if not all([jira_url, jira_username, jira_api_token]):
        logger.error("Jira credentials not configured. Ensure JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN are set.")
        return {}

    epic_summaries = {}
    total_epics = sum(len(epics) for epics in epics_by_project.values())
    processed = 0

    # Use httpx for API calls with basic auth
    auth = (jira_username, jira_api_token)

    with httpx.Client(auth=auth, timeout=30.0) as client:
        for project_key, epic_keys in sorted(epics_by_project.items()):
            logger.info(f"\nProcessing {project_key} ({len(epic_keys)} epics)...")

            for epic_key in sorted(epic_keys):
                try:
                    # Fetch epic details from Jira REST API
                    url = f"{jira_url}/rest/api/3/issue/{epic_key}?fields=summary"
                    response = client.get(url)

                    if response.status_code == 200:
                        epic_data = response.json()
                        if 'fields' in epic_data and 'summary' in epic_data['fields']:
                            epic_summary = epic_data['fields']['summary']
                            epic_summaries[epic_key] = epic_summary
                            logger.debug(f"  {epic_key} → {epic_summary}")
                        else:
                            logger.warning(f"  {epic_key}: No summary found, keeping original")
                            epic_summaries[epic_key] = epic_key
                    elif response.status_code == 404:
                        logger.warning(f"  {epic_key}: Not found in Jira (404), keeping original")
                        epic_summaries[epic_key] = epic_key
                    else:
                        logger.error(f"  {epic_key}: HTTP {response.status_code}, keeping original")
                        epic_summaries[epic_key] = epic_key

                    processed += 1

                    if processed % 10 == 0:
                        logger.info(f"  Progress: {processed}/{total_epics} epics")

                except Exception as e:
                    logger.error(f"  Error fetching {epic_key}: {e}")
                    # Keep the original epic_key as fallback
                    epic_summaries[epic_key] = epic_key

    logger.info(f"\n✅ Successfully fetched {len(epic_summaries)} epic summaries")
    return epic_summaries


def update_epic_summaries(session, epic_summaries: Dict[str, str], dry_run: bool = False):
    """Update epic_summary field in epic_hours table.

    Args:
        session: SQLAlchemy session
        epic_summaries: Dict of epic_key -> epic_summary
        dry_run: If True, don't actually save to database
    """
    if dry_run:
        logger.info("\nDRY RUN: Would update the following epic summaries:")
        for epic_key, epic_summary in sorted(epic_summaries.items())[:20]:
            logger.info(f"  {epic_key} → {epic_summary}")
        if len(epic_summaries) > 20:
            logger.info(f"  ... and {len(epic_summaries) - 20} more")
        return

    logger.info(f"\nUpdating {len(epic_summaries)} epic summaries in database...")

    updated = 0
    for epic_key, epic_summary in epic_summaries.items():
        # Skip if epic_summary is the same as epic_key (no enrichment)
        if epic_summary == epic_key:
            continue

        # Update all records for this epic_key
        result = (
            session.query(EpicHours)
            .filter_by(epic_key=epic_key)
            .update({"epic_summary": epic_summary})
        )

        if result > 0:
            updated += result
            logger.debug(f"  Updated {result} records for {epic_key}")

    session.commit()
    logger.info(f"✅ Updated {updated} records successfully!")


def generate_report(epic_summaries: Dict[str, str]):
    """Generate summary report of enrichment."""
    enriched = {k: v for k, v in epic_summaries.items() if k != v}
    unchanged = {k: v for k, v in epic_summaries.items() if k == v}

    print("\n" + "=" * 80)
    print("EPIC SUMMARY ENRICHMENT REPORT")
    print("=" * 80)
    print(f"Total epics processed: {len(epic_summaries)}")
    print(f"Epics enriched (got real summary): {len(enriched)}")
    print(f"Epics unchanged (kept ticket key): {len(unchanged)}")
    print()

    if enriched:
        print("-" * 80)
        print("SAMPLE ENRICHED EPICS (First 15)")
        print("-" * 80)
        for i, (epic_key, epic_summary) in enumerate(sorted(enriched.items())[:15]):
            print(f"{epic_key:<15} → {epic_summary}")

        if len(enriched) > 15:
            print(f"\n... and {len(enriched) - 15} more enriched epics")

    if unchanged:
        print()
        print("-" * 80)
        print("EPICS THAT COULD NOT BE ENRICHED")
        print("-" * 80)
        for epic_key in sorted(unchanged.keys())[:10]:
            print(f"  {epic_key}")

        if len(unchanged) > 10:
            print(f"  ... and {len(unchanged) - 10} more")

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Enrich epic summaries from Jira')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving to database')
    args = parser.parse_args()

    logger.info("Starting epic summary enrichment...")

    # Initialize database session
    session = get_session()

    try:
        # Step 1: Find epics needing enrichment
        epics_by_project = get_epics_needing_enrichment(session)

        if not epics_by_project:
            logger.info("No epics need enrichment. All epic_summary fields are already set.")
            return 0

        # Step 2: Fetch epic summaries from Jira
        epic_summaries = fetch_epic_summaries_from_jira(epics_by_project)

        # Step 3: Generate report
        generate_report(epic_summaries)

        # Step 4: Update database
        update_epic_summaries(session, epic_summaries, dry_run=args.dry_run)

        if args.dry_run:
            print("\n⚠️  DRY RUN MODE: No changes were saved to database")
            print("Run without --dry-run to apply changes")
        else:
            print("\n✅ Enrichment complete! Epic summaries updated in epic_hours table")
            print("\nNext steps:")
            print("1. Re-run 'python scripts/analyze_epic_groups.py' to regenerate AI groupings")
            print("2. Run 'python scripts/generate_epic_baselines.py' to rebuild baselines")

        return 0

    except Exception as e:
        logger.error(f"Error during enrichment: {e}", exc_info=True)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
