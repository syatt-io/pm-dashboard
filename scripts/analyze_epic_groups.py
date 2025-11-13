#!/usr/bin/env python3
"""
AI-powered epic grouping analysis script.

This script fetches all unique epic names from the database,
uses AI to propose natural groupings (canonical categories),
and saves the mappings to the epic_baseline_mappings table.

The AI analyzes the data organically rather than forcing predefined categories,
allowing the number of groups to be driven by the actual data (could be 15, 20, 40, etc.).

Usage:
    python scripts/analyze_epic_groups.py
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.epic_analysis_service import EpicAnalysisService
from src.utils.database import get_session

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_report(result: dict):
    """Generate summary report of the groupings."""
    print("\n" + "=" * 80)
    print("EPIC GROUPING ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total epic names analyzed: {result['total_epics']}")
    print(f"Total canonical categories created: {result['total_categories']}")
    print()

    print("-" * 80)
    print("TOP 10 CATEGORIES")
    print("-" * 80)
    print(f"{'Category':<40} {'Epic Count':<15}")
    print("-" * 80)

    for category, count in list(result["top_categories"].items())[:10]:
        print(f"{category:<40} {count:<15}")

    print("=" * 80)


def main():
    """Main entry point."""
    logger.info("Starting AI-powered epic grouping analysis...")

    # Get database session
    session = get_session()

    try:
        # Initialize analysis service
        service = EpicAnalysisService(session)

        # Run analysis
        result = service.analyze_and_group_epics()

        if result["success"]:
            # Generate report
            generate_report(result)

            print(
                "\n✅ Analysis complete! Mappings saved to epic_baseline_mappings table"
            )
            print("\nNext steps:")
            print("1. Review the mappings in the database")
            print(
                "2. Run 'python scripts/generate_epic_baselines.py' to regenerate baselines"
            )
            print("3. The Epic Baselines tab should now show grouped categories")

            return 0
        else:
            logger.error(f"Analysis failed: {result.get('error', 'Unknown error')}")
            return 1

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
