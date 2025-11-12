#!/usr/bin/env python3
"""
Generate epic baseline estimates from historical project data.

This script analyzes epic_hours data to identify common epics (appearing in 3+ projects)
and calculates statistical baselines for forecasting and project scoping.

Usage:
    python scripts/generate_epic_baselines.py
"""

import sys
from pathlib import Path
from collections import defaultdict
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours, EpicBaseline
from src.utils.database import get_session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_epic_name(epic_summary: str) -> str:
    """
    Normalize and consolidate epic names for grouping.

    Combines similar epic names into canonical categories:
    - Product details, PDP details, PDP image & summary -> product details
    - Globals & style guide, Globals -> globals & style guide
    """
    normalized = epic_summary.strip().lower()

    # Consolidation mappings (order matters - check specific patterns first)
    consolidations = {
        # Product detail page variants
        "pdp details": "product details",
        "pdp image & summary": "product details",
        "product detail page": "product details",
        # Globals variants
        "globals": "globals & style guide",
    }

    # Apply consolidation mapping
    for pattern, canonical in consolidations.items():
        if normalized == pattern:
            return canonical

    return normalized


def classify_variance(cv: float) -> str:
    """
    Classify variance level based on coefficient of variation.

    - Low: CV < 80% (predictable, use median)
    - Medium: CV 80-120% (moderate variance, use P75)
    - High: CV > 120% (highly variable, use P90 or custom scoping)
    """
    if cv < 80:
        return "low"
    elif cv < 120:
        return "medium"
    else:
        return "high"


def generate_baselines(min_project_count: int = None):
    """
    Generate epic baselines from historical data.

    Args:
        min_project_count: Minimum number of projects an epic must appear in to be included.
                          If None (default), automatically determined based on available data:
                          - 1 project: min = 1 (show all epics)
                          - 2-3 projects: min = 2 (require 2+ projects)
                          - 4+ projects: min = 3 (require 3+ projects for quality)
    """
    session = get_session()

    try:
        logger.info("Fetching epic hours data...")
        all_records = session.query(EpicHours).all()
        logger.info(f"Found {len(all_records)} total epic hour records")

        # Determine unique project count for adaptive threshold
        if min_project_count is None:
            unique_projects = set(record.project_key for record in all_records if record.project_key)
            total_projects = len(unique_projects)

            # Use permissive threshold to show all historical epic data for forecasting
            # The coefficient_of_variation field indicates reliability of each estimate
            if total_projects <= 10:
                min_project_count = 1
                logger.info(f"{total_projects} project(s) found - showing all epics (min_project_count=1)")
            elif total_projects <= 20:
                min_project_count = 2
                logger.info(f"{total_projects} projects found - requiring 2+ projects per epic (min_project_count=2)")
            else:
                min_project_count = 3
                logger.info(f"{total_projects} projects found - requiring 3+ projects per epic (min_project_count=3)")
        else:
            logger.info(f"Using explicitly set min_project_count={min_project_count}")

        # Group by normalized epic summary
        # First, aggregate hours by project+epic (sum across all months)
        project_epic_hours = defaultdict(lambda: defaultdict(float))

        for record in all_records:
            if not record.epic_summary:
                continue

            normalized_name = normalize_epic_name(record.epic_summary)
            project_epic_hours[normalized_name][record.project_key] += record.hours

        # Now calculate statistics across project totals
        epic_data = defaultdict(
            lambda: {"hours": [], "projects": set(), "occurrences": 0}
        )

        for epic_name, projects in project_epic_hours.items():
            for project_key, total_hours in projects.items():
                epic_data[epic_name]["hours"].append(total_hours)
                epic_data[epic_name]["projects"].add(project_key)
                epic_data[epic_name]["occurrences"] += 1

        # Filter to common epics (3+ projects) and calculate statistics
        baselines = []
        for epic_name, data in epic_data.items():
            project_count = len(data["projects"])

            if project_count < min_project_count:
                continue

            hours = data["hours"]
            mean_hours = statistics.mean(hours)
            median_hours = statistics.median(hours)

            min_hours = min(hours)
            max_hours = max(hours)

            # Handle single data point case
            if len(hours) == 1:
                p75_hours = hours[0]
                p90_hours = hours[0]
                std_dev = 0
                cv = 0
            else:
                # Calculate percentiles
                sorted_hours = sorted(hours)
                p75_hours = statistics.quantiles(sorted_hours, n=4)[2]  # 75th percentile
                p90_index = int(len(sorted_hours) * 0.9)
                p90_hours = sorted_hours[p90_index]

                # Coefficient of variation (CV% = std_dev / mean * 100)
                std_dev = statistics.stdev(hours)
                cv = (std_dev / mean_hours * 100) if mean_hours > 0 else 0

            variance_level = classify_variance(cv)

            baselines.append(
                {
                    "epic_category": epic_name,
                    "median_hours": round(median_hours, 2),
                    "mean_hours": round(mean_hours, 2),
                    "p75_hours": round(p75_hours, 2),
                    "p90_hours": round(p90_hours, 2),
                    "min_hours": round(min_hours, 2),
                    "max_hours": round(max_hours, 2),
                    "project_count": project_count,
                    "occurrence_count": data["occurrences"],
                    "coefficient_of_variation": round(cv, 2),
                    "variance_level": variance_level,
                }
            )

        logger.info(
            f"Found {len(baselines)} common epics (appearing in {min_project_count}+ projects)"
        )

        # Sort by project count (most common first)
        baselines.sort(
            key=lambda x: (x["project_count"], x["median_hours"]), reverse=True
        )

        # Clear existing baselines and insert new ones
        logger.info("Clearing existing baselines...")
        session.query(EpicBaseline).delete()

        logger.info("Inserting new baselines...")
        for baseline_data in baselines:
            baseline = EpicBaseline(**baseline_data)
            session.add(baseline)

        session.commit()
        logger.info("✅ Baselines generated successfully!")

        # Print summary
        print("\n" + "=" * 80)
        print("EPIC BASELINES SUMMARY")
        print("=" * 80)
        print(f"Total common epics: {len(baselines)}")
        print()

        # Group by variance level
        by_variance = defaultdict(list)
        for b in baselines:
            by_variance[b["variance_level"]].append(b)

        for level in ["low", "medium", "high"]:
            count = len(by_variance[level])
            print(f"{level.upper()} variance epics: {count}")

        print("\n" + "-" * 80)
        print("TOP 10 MOST COMMON EPICS")
        print("-" * 80)
        print(f"{'Epic':<40} {'Projects':<10} {'Median':<10} {'CV%':<10} {'Level':<10}")
        print("-" * 80)

        for baseline in baselines[:10]:
            print(
                f"{baseline['epic_category']:<40} "
                f"{baseline['project_count']:<10} "
                f"{baseline['median_hours']:<10.1f} "
                f"{baseline['coefficient_of_variation']:<10.1f} "
                f"{baseline['variance_level']:<10}"
            )

        print("=" * 80)

        return baselines

    except Exception as e:
        logger.error(f"Error generating baselines: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """Main entry point."""
    logger.info("Generating epic baselines from historical data...")
    baselines = generate_baselines()  # Use adaptive threshold based on available data
    logger.info(f"Generated {len(baselines)} baseline estimates")


if __name__ == "__main__":
    main()
