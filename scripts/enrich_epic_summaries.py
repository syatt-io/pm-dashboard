#!/usr/bin/env python3
"""
Enrich epic_hours table with actual epic summaries from Jira.

For records where epic_summary == epic_key (ticket key), this script
fetches the actual epic name from Jira and updates the epic_summary field.

Usage:
    python scripts/enrich_epic_summaries.py
    python scripts/enrich_epic_summaries.py --dry-run  # Preview without saving
    python scripts/enrich_epic_summaries.py --project PROJ  # Enrich specific project
"""

import sys
import logging
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.epic_enrichment_service import EpicEnrichmentService
from src.utils.database import get_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_report(result: dict):
    """Generate summary report of enrichment."""
    print("\n" + "=" * 80)
    print("EPIC SUMMARY ENRICHMENT REPORT")
    print("=" * 80)
    print(f"Total epics found: {result['epics_found']}")
    print(f"Records updated: {result['records_updated']}")
    print(f"Epics enriched: {result['enriched_count']}")
    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Enrich epic summaries from Jira')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving to database')
    parser.add_argument('--project', type=str, help='Enrich specific project only')
    args = parser.parse_args()

    logger.info("Starting epic summary enrichment...")

    # Initialize database session
    session = get_session()

    try:
        # Initialize enrichment service
        service = EpicEnrichmentService(session)

        # Run enrichment
        if args.project:
            logger.info(f"Enriching project: {args.project}")
            result = service.enrich_project_epics(args.project)
        else:
            logger.info("Enriching all projects")
            result = service.enrich_all_epics()

        # Generate report
        if result['success']:
            generate_report(result)

            print("\n✅ Enrichment complete! Epic summaries updated in epic_hours table")
            print("\nNext steps:")
            print("1. Re-run 'python scripts/analyze_epic_groups.py' to regenerate AI groupings")
            print("2. Run 'python scripts/generate_epic_baselines.py' to rebuild baselines")
        else:
            logger.error(f"Enrichment failed: {result.get('error', 'Unknown error')}")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error during enrichment: {e}", exc_info=True)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
