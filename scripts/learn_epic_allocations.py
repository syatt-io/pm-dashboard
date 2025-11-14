"""Learn epic category allocation ranges from historical data.

This script analyzes all historical projects to learn the typical allocation
percentages for each epic category (e.g., FE Dev, BE Dev, Design). This replaces
hardcoded ranges in AI prompts with data-driven ranges learned from real projects.

Example hardcoded ranges being replaced:
    - **FE Dev** (30-45%)    # HARDCODED
    - **BE Dev** (15-30%)    # HARDCODED

With learned ranges:
    - **FE Dev** (35-62%)    # LEARNED from 15 projects
    - **BE Dev** (10-35%)    # LEARNED from 12 projects

Usage:
    python scripts/learn_epic_allocations.py [--dry-run]
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List
import logging
import argparse
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from src.models import EpicHours, EpicAllocationBaseline, Project
from src.utils.database import get_session

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Minimum sample size to consider pattern valid
MIN_SAMPLE_SIZE = 2


def get_epic_category_allocations(session) -> Dict[str, List[float]]:
    """
    Get epic category allocation percentages for each project.

    Returns:
        Dict mapping epic_category to list of allocation percentages across projects
    """
    logger.info("Calculating epic category allocations from epic_hours...")

    # Get total hours by project and epic_category
    results = (
        session.query(
            EpicHours.project_key,
            EpicHours.epic_category,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .filter(EpicHours.epic_category.isnot(None))  # Skip rows without category
        .group_by(EpicHours.project_key, EpicHours.epic_category)
        .all()
    )

    # Calculate project totals first
    project_totals = defaultdict(float)
    category_hours = defaultdict(lambda: defaultdict(float))

    for row in results:
        project_key = row.project_key
        epic_category = row.epic_category
        hours = float(row.total_hours)

        project_totals[project_key] += hours
        category_hours[project_key][epic_category] = hours

    # Calculate allocation percentages per project
    category_allocations = defaultdict(list)

    for project_key, total_hours in project_totals.items():
        if total_hours > 0:
            for epic_category, hours in category_hours[project_key].items():
                allocation_pct = (hours / total_hours) * 100
                category_allocations[epic_category].append(allocation_pct)

    logger.info(
        f"Calculated allocations for {len(category_allocations)} epic categories "
        f"across {len(project_totals)} projects"
    )
    return dict(category_allocations)


def calculate_epic_allocation_baselines(
    category_allocations: Dict[str, List[float]],
) -> List[Dict]:
    """
    Calculate min, max, avg, and std_dev for each epic category.

    Args:
        category_allocations: Dict mapping epic_category to list of allocation percentages

    Returns:
        List of baseline dicts with epic allocation statistics
    """
    logger.info("Calculating epic allocation baselines...")

    baselines = []

    for epic_category, allocations_list in category_allocations.items():
        sample_size = len(allocations_list)

        # Skip if insufficient data
        if sample_size < MIN_SAMPLE_SIZE:
            logger.debug(
                f"Skipping {epic_category}: "
                f"only {sample_size} samples (need {MIN_SAMPLE_SIZE})"
            )
            continue

        min_allocation = min(allocations_list)
        max_allocation = max(allocations_list)
        avg_allocation = statistics.mean(allocations_list)
        std_dev = statistics.stdev(allocations_list) if sample_size > 1 else 0.0

        baselines.append(
            {
                "epic_category": epic_category,
                "min_allocation_pct": round(min_allocation, 2),
                "max_allocation_pct": round(max_allocation, 2),
                "avg_allocation_pct": round(avg_allocation, 2),
                "std_dev": round(std_dev, 2),
                "sample_size": sample_size,
            }
        )

    logger.info(f"Generated {len(baselines)} epic allocation baselines")
    return baselines


def save_baselines(session, baselines: List[Dict], dry_run: bool = False):
    """Save or display calculated baselines."""

    if dry_run:
        logger.info("\n=== DRY RUN: Would save the following baselines ===\n")
        for baseline in sorted(baselines, key=lambda x: x["epic_category"]):
            logger.info(
                f"{baseline['epic_category']:30} → "
                f"{baseline['min_allocation_pct']:5.1f}%-{baseline['max_allocation_pct']:5.1f}% "
                f"(avg: {baseline['avg_allocation_pct']:5.1f}%, "
                f"±{baseline['std_dev']:4.1f}%, n={baseline['sample_size']})"
            )
        return

    # Clear existing baselines
    logger.info("Clearing existing epic allocation baselines...")
    session.query(EpicAllocationBaseline).delete()
    session.commit()

    # Insert new baselines
    logger.info("Inserting new epic allocation baselines...")
    for baseline_data in baselines:
        baseline_data["last_updated"] = datetime.now(timezone.utc)
        baseline = EpicAllocationBaseline(**baseline_data)
        session.add(baseline)

    session.commit()
    logger.info(f"✅ Successfully saved {len(baselines)} epic allocation baselines")


def print_summary(baselines: List[Dict]):
    """Print summary of learned patterns."""
    logger.info("\n" + "=" * 80)
    logger.info("EPIC ALLOCATION LEARNING SUMMARY")
    logger.info("=" * 80)

    # Sort by average allocation descending
    sorted_baselines = sorted(
        baselines, key=lambda x: x["avg_allocation_pct"], reverse=True
    )

    logger.info(f"\n{'Epic Category':<30} {'Range':<15} {'Average':<10} {'Samples':<8}")
    logger.info("-" * 80)

    for baseline in sorted_baselines:
        range_str = f"{baseline['min_allocation_pct']:.1f}-{baseline['max_allocation_pct']:.1f}%"
        avg_str = f"{baseline['avg_allocation_pct']:.1f}%"
        logger.info(
            f"{baseline['epic_category']:<30} {range_str:<15} {avg_str:<10} {baseline['sample_size']:<8}"
        )

    # Print key insights
    logger.info("\n" + "=" * 80)
    logger.info("KEY INSIGHTS")
    logger.info("=" * 80)

    # Find categories with widest ranges (high variability)
    high_variability = sorted(
        baselines,
        key=lambda x: x["max_allocation_pct"] - x["min_allocation_pct"],
        reverse=True,
    )[:3]

    logger.info("\nCategories with highest variability:")
    for baseline in high_variability:
        range_width = baseline["max_allocation_pct"] - baseline["min_allocation_pct"]
        logger.info(
            f"  {baseline['epic_category']}: {range_width:.1f}% range "
            f"({baseline['min_allocation_pct']:.1f}%-{baseline['max_allocation_pct']:.1f}%)"
        )

    # Find categories with most consistent allocations (low variability)
    low_variability = sorted(baselines, key=lambda x: x["std_dev"])[:3]

    logger.info("\nCategories with most consistent allocations:")
    for baseline in low_variability:
        logger.info(
            f"  {baseline['epic_category']}: {baseline['avg_allocation_pct']:.1f}% "
            f"(±{baseline['std_dev']:.1f}%, n={baseline['sample_size']})"
        )

    # Find top 5 categories by average allocation
    top_categories = sorted(
        baselines, key=lambda x: x["avg_allocation_pct"], reverse=True
    )[:5]

    logger.info("\nTop 5 categories by average allocation:")
    for baseline in top_categories:
        logger.info(
            f"  {baseline['epic_category']}: {baseline['avg_allocation_pct']:.1f}% average"
        )

    logger.info("\n" + "=" * 80)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Learn epic allocation ranges from historical project data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print calculated baselines without saving to database",
    )
    args = parser.parse_args()

    logger.info("Starting epic allocation learning...")

    session = get_session()

    try:
        # 1. Get epic category allocations
        category_allocations = get_epic_category_allocations(session)

        if not category_allocations:
            logger.error(
                "No epic hours data found. "
                "Please ensure epic_hours table is populated."
            )
            return

        # 2. Calculate allocation baselines
        baselines = calculate_epic_allocation_baselines(category_allocations)

        if not baselines:
            logger.error(
                "No baselines generated. Insufficient data or no epic categories found."
            )
            return

        # 3. Save or display baselines
        save_baselines(session, baselines, dry_run=args.dry_run)

        # 4. Print summary
        print_summary(baselines)

        logger.info("\n✅ Epic allocation learning completed successfully!")

    except Exception as e:
        logger.error(f"Error during epic allocation learning: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
