"""Learn characteristic impacts on team allocations from historical data.

This script analyzes all historical projects to learn how project characteristics
(1-5 scale) actually impact team allocations. This replaces hardcoded multipliers
with data-driven patterns learned from real project history.

Example hardcoded multiplier being replaced:
    design_multiplier = 1.0 + (custom_designs - 1) * 0.75  # HARDCODED 0.75

With learned data:
    Projects with custom_designs=5 averaged 18.5% Design allocation
    Projects with custom_designs=1 averaged  6.2% Design allocation

Usage:
    python scripts/learn_characteristic_impacts.py [--dry-run]
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Tuple
import logging
import argparse
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from src.models import (
    EpicHours,
    ProjectCharacteristics,
    CharacteristicImpactBaseline,
    Project,
)
from src.utils.database import get_session

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Characteristics to analyze (maps to ProjectCharacteristics columns)
CHARACTERISTICS = [
    "be_integrations",
    "custom_theme",
    "custom_designs",
    "ux_research",
    "extensive_customizations",
    "project_oversight",
]

# Team mapping for impact analysis
TEAM_CHARACTERISTIC_MAPPING = {
    "custom_designs": ["Design"],
    "ux_research": ["UX"],
    "custom_theme": ["FE Devs"],
    "be_integrations": ["BE Devs"],
    "extensive_customizations": ["BE Devs"],
    "project_oversight": ["PMs"],
}

# Minimum sample size to consider pattern valid
MIN_SAMPLE_SIZE = 2


def get_project_characteristics(session) -> Dict[str, Dict]:
    """
    Fetch all projects with their characteristics.

    Returns:
        Dict mapping project_key to characteristic values
    """
    logger.info("Fetching project characteristics...")

    results = (
        session.query(ProjectCharacteristics, Project.is_active)
        .join(Project, ProjectCharacteristics.project_key == Project.key)
        .filter(Project.is_active == True)  # Only active projects
        .all()
    )

    characteristics_map = {}
    for char, is_active in results:
        characteristics_map[char.project_key] = {
            "be_integrations": char.be_integrations,
            "custom_theme": char.custom_theme,
            "custom_designs": char.custom_designs,
            "ux_research": char.ux_research,
            "extensive_customizations": char.extensive_customizations,
            "project_oversight": char.project_oversight,
        }

    logger.info(f"Found {len(characteristics_map)} projects with characteristics")
    return characteristics_map


def get_team_allocations(session) -> Dict[str, Dict[str, float]]:
    """
    Get team allocation percentages for each project.

    Returns:
        Dict mapping project_key to {team: allocation_pct}
    """
    logger.info("Calculating team allocations from epic_hours...")

    # Get total hours by project and team
    results = (
        session.query(
            EpicHours.project_key,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .group_by(EpicHours.project_key, EpicHours.team)
        .all()
    )

    # Calculate project totals first
    project_totals = defaultdict(float)
    team_hours = defaultdict(lambda: defaultdict(float))

    for row in results:
        project_key = row.project_key
        team = row.team
        hours = float(row.total_hours)

        project_totals[project_key] += hours
        team_hours[project_key][team] = hours

    # Calculate allocation percentages
    allocations = {}
    for project_key, total_hours in project_totals.items():
        if total_hours > 0:
            allocations[project_key] = {
                team: (hours / total_hours) * 100
                for team, hours in team_hours[project_key].items()
            }

    logger.info(f"Calculated allocations for {len(allocations)} projects")
    return allocations


def calculate_characteristic_impacts(
    characteristics_map: Dict[str, Dict],
    allocations: Dict[str, Dict[str, float]],
) -> List[Dict]:
    """
    Calculate average team allocations grouped by characteristic values.

    Args:
        characteristics_map: project_key -> characteristic values
        allocations: project_key -> {team: allocation_pct}

    Returns:
        List of baseline dicts with characteristic impacts
    """
    logger.info("Calculating characteristic impacts...")

    # Group projects by (characteristic_name, characteristic_value, team)
    grouped = defaultdict(lambda: defaultdict(list))

    for project_key, chars in characteristics_map.items():
        if project_key not in allocations:
            continue

        for char_name in CHARACTERISTICS:
            char_value = chars[char_name]

            # Get all teams for this project
            for team, allocation_pct in allocations[project_key].items():
                # Store allocation for this combination
                key = (char_name, char_value, team)
                grouped[key]["allocations"].append(allocation_pct)
                grouped[key]["projects"].append(project_key)

    # Calculate statistics for each group
    baselines = []

    for (char_name, char_value, team), data in grouped.items():
        allocations_list = data["allocations"]
        projects_list = data["projects"]

        sample_size = len(allocations_list)

        # Skip if insufficient data
        if sample_size < MIN_SAMPLE_SIZE:
            logger.debug(
                f"Skipping {char_name}={char_value}, {team}: "
                f"only {sample_size} samples (need {MIN_SAMPLE_SIZE})"
            )
            continue

        avg_allocation = statistics.mean(allocations_list)
        std_dev = statistics.stdev(allocations_list) if sample_size > 1 else 0.0

        baselines.append(
            {
                "characteristic_name": char_name,
                "characteristic_value": char_value,
                "team": team,
                "avg_allocation_pct": round(avg_allocation, 2),
                "std_dev": round(std_dev, 2),
                "sample_size": sample_size,
                "sample_projects": projects_list[:5],  # For logging
            }
        )

    logger.info(f"Generated {len(baselines)} characteristic impact baselines")
    return baselines


def save_baselines(session, baselines: List[Dict], dry_run: bool = False):
    """Save or display calculated baselines."""

    if dry_run:
        logger.info("\n=== DRY RUN: Would save the following baselines ===\n")
        for baseline in sorted(
            baselines,
            key=lambda x: (
                x["characteristic_name"],
                x["characteristic_value"],
                x["team"],
            ),
        ):
            logger.info(
                f"{baseline['characteristic_name']}={baseline['characteristic_value']} → "
                f"{baseline['team']}: {baseline['avg_allocation_pct']}% "
                f"(±{baseline['std_dev']}%, n={baseline['sample_size']})"
            )
            logger.info(
                f"  Sample projects: {', '.join(baseline['sample_projects'])}\n"
            )
        return

    # Clear existing baselines
    logger.info("Clearing existing characteristic impact baselines...")
    session.query(CharacteristicImpactBaseline).delete()
    session.commit()

    # Insert new baselines
    logger.info("Inserting new characteristic impact baselines...")
    for baseline_data in baselines:
        # Remove sample_projects before saving (just for logging)
        baseline_data_clean = {
            k: v for k, v in baseline_data.items() if k != "sample_projects"
        }
        baseline_data_clean["last_updated"] = datetime.now(timezone.utc)

        baseline = CharacteristicImpactBaseline(**baseline_data_clean)
        session.add(baseline)

    session.commit()
    logger.info(
        f"✅ Successfully saved {len(baselines)} characteristic impact baselines"
    )


def print_summary(baselines: List[Dict]):
    """Print summary of learned patterns."""
    logger.info("\n" + "=" * 80)
    logger.info("CHARACTERISTIC IMPACT LEARNING SUMMARY")
    logger.info("=" * 80)

    # Group by characteristic
    by_characteristic = defaultdict(list)
    for baseline in baselines:
        by_characteristic[baseline["characteristic_name"]].append(baseline)

    for char_name in sorted(by_characteristic.keys()):
        logger.info(f"\n{char_name.upper()}")
        logger.info("-" * 80)

        char_baselines = sorted(
            by_characteristic[char_name],
            key=lambda x: (x["characteristic_value"], x["team"]),
        )

        current_value = None
        for baseline in char_baselines:
            if baseline["characteristic_value"] != current_value:
                current_value = baseline["characteristic_value"]
                logger.info(f"\n  Value {current_value}:")

            logger.info(
                f"    {baseline['team']:15} → {baseline['avg_allocation_pct']:5.1f}% "
                f"(±{baseline['std_dev']:4.1f}%, n={baseline['sample_size']})"
            )

    # Print key insights
    logger.info("\n" + "=" * 80)
    logger.info("KEY INSIGHTS")
    logger.info("=" * 80)

    # Find highest/lowest allocations for each characteristic
    for char_name in CHARACTERISTICS:
        if char_name not in by_characteristic:
            continue

        char_baselines = by_characteristic[char_name]

        # Group by team for this characteristic
        by_team = defaultdict(list)
        for baseline in char_baselines:
            by_team[baseline["team"]].append(baseline)

        for team, team_baselines in by_team.items():
            if len(team_baselines) < 2:
                continue

            lowest = min(team_baselines, key=lambda x: x["avg_allocation_pct"])
            highest = max(team_baselines, key=lambda x: x["avg_allocation_pct"])

            multiplier = (
                highest["avg_allocation_pct"] / lowest["avg_allocation_pct"]
                if lowest["avg_allocation_pct"] > 0
                else 0
            )

            logger.info(f"\n{char_name} impact on {team}:")
            logger.info(
                f"  Value {lowest['characteristic_value']}: {lowest['avg_allocation_pct']:.1f}%"
            )
            logger.info(
                f"  Value {highest['characteristic_value']}: {highest['avg_allocation_pct']:.1f}%"
            )
            logger.info(f"  Multiplier: {multiplier:.2f}x")

    logger.info("\n" + "=" * 80)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Learn characteristic impacts from historical project data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print calculated baselines without saving to database",
    )
    args = parser.parse_args()

    logger.info("Starting characteristic impact learning...")

    session = get_session()

    try:
        # 1. Get project characteristics
        characteristics_map = get_project_characteristics(session)

        if not characteristics_map:
            logger.error(
                "No projects with characteristics found. "
                "Please ensure project_characteristics table is populated."
            )
            return

        # 2. Get team allocations from epic_hours
        allocations = get_team_allocations(session)

        if not allocations:
            logger.error(
                "No epic hours data found. "
                "Please ensure epic_hours table is populated."
            )
            return

        # 3. Calculate characteristic impacts
        baselines = calculate_characteristic_impacts(characteristics_map, allocations)

        if not baselines:
            logger.error(
                "No baselines generated. Insufficient data or no matching projects."
            )
            return

        # 4. Save or display baselines
        save_baselines(session, baselines, dry_run=args.dry_run)

        # 5. Print summary
        print_summary(baselines)

        logger.info("\n✅ Characteristic impact learning completed successfully!")

    except Exception as e:
        logger.error(f"Error during characteristic impact learning: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
