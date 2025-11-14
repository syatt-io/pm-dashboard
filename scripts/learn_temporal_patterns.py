"""Learn temporal patterns from historical epic hours data.

This script analyzes all historical projects in the epic_hours table and learns
temporal distribution patterns for each team. Patterns are normalized by timeline
percentage (duration-agnostic) so they can be applied to projects of any length.

Example:
    Design teams typically complete 45% of their work in the first 10% of timeline,
    while FE Devs complete only 3% of their work in the first 10% of timeline.

Usage:
    python scripts/learn_temporal_patterns.py [--dry-run]
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Tuple
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from src.models import EpicHours, TemporalPatternBaseline
from src.utils.database import get_session

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Timeline buckets (10% increments)
TIMELINE_BUCKETS = [(i, i + 10) for i in range(0, 100, 10)]


def get_project_timeline_data(session) -> Dict[str, Dict]:
    """
    Get all projects with their month-by-month data and calculate timeline info.

    Returns:
        Dict mapping project_key to {
            'months': List of months sorted,
            'duration_months': int,
            'hours_by_month_team': {(month, team): hours}
        }
    """
    logger.info("Fetching project timeline data from epic_hours table...")

    # Get all project data grouped by project, month, and team
    results = (
        session.query(
            EpicHours.project_key,
            EpicHours.month,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .group_by(EpicHours.project_key, EpicHours.month, EpicHours.team)
        .order_by(EpicHours.project_key, EpicHours.month)
        .all()
    )

    # Organize data by project
    projects = defaultdict(lambda: {"months": set(), "hours_by_month_team": {}})

    for row in results:
        project_key = row.project_key
        month = row.month
        team = row.team
        hours = float(row.total_hours)

        projects[project_key]["months"].add(month)
        projects[project_key]["hours_by_month_team"][(month, team)] = hours

    # Convert months to sorted lists and calculate duration
    for project_key, data in projects.items():
        data["months"] = sorted(list(data["months"]))
        data["duration_months"] = len(data["months"])

    logger.info(f"Found {len(projects)} projects with historical data")

    return dict(projects)


def normalize_to_timeline_percentage(month_index: int, total_months: int) -> float:
    """
    Convert a month index to timeline percentage.

    Args:
        month_index: 0-based month index (0 = first month)
        total_months: Total duration in months

    Returns:
        Midpoint percentage of timeline for this month

    Example:
        For a 6-month project:
        - Month 0 (first month) covers 0-16.7%, midpoint = 8.35%
        - Month 1 covers 16.7-33.3%, midpoint = 25%
    """
    month_pct = 100.0 / total_months
    start_pct = month_index * month_pct
    end_pct = (month_index + 1) * month_pct
    midpoint = (start_pct + end_pct) / 2
    return midpoint


def assign_to_bucket(timeline_pct: float) -> Tuple[int, int]:
    """Assign a timeline percentage to a 10% bucket."""
    for start, end in TIMELINE_BUCKETS:
        if start <= timeline_pct < end:
            return (start, end)
    # Handle edge case of 100%
    return (90, 100)


def calculate_team_totals(hours_by_month_team: Dict[Tuple, float]) -> Dict[str, float]:
    """Calculate total hours for each team across all months."""
    team_totals = defaultdict(float)
    for (month, team), hours in hours_by_month_team.items():
        team_totals[team] += hours
    return dict(team_totals)


def analyze_project_temporal_patterns(
    project_data: Dict[str, Dict],
) -> Dict[Tuple[int, int, str], List[float]]:
    """
    Analyze temporal patterns across all projects.

    For each (timeline_bucket, team) combination, collect the % of work
    done in that bucket across all projects.

    Args:
        project_data: Dict from get_project_timeline_data()

    Returns:
        Dict mapping (start_pct, end_pct, team) to List[work_pct_samples]
    """
    logger.info("Analyzing temporal patterns across projects...")

    # Collect samples for each (bucket, team) combination
    pattern_samples = defaultdict(list)

    for project_key, data in project_data.items():
        months = data["months"]
        duration = data["duration_months"]
        hours_by_month_team = data["hours_by_month_team"]

        # Skip projects with less than 2 months of data
        if duration < 2:
            logger.warning(f"Skipping {project_key}: only {duration} month(s) of data")
            continue

        # Calculate team totals for this project
        team_totals = calculate_team_totals(hours_by_month_team)

        # For each month, determine what % of each team's total work was done
        for month_idx, month in enumerate(months):
            # Convert month to timeline percentage
            timeline_pct = normalize_to_timeline_percentage(month_idx, duration)
            bucket = assign_to_bucket(timeline_pct)

            # For each team that worked in this month
            for (m, team), hours in hours_by_month_team.items():
                if m == month:
                    team_total = team_totals.get(team, 0)
                    if team_total > 0:
                        work_pct = (hours / team_total) * 100.0
                        pattern_samples[(*bucket, team)].append(work_pct)

    logger.info(
        f"Collected pattern samples for {len(pattern_samples)} (bucket, team) combinations"
    )

    return dict(pattern_samples)


def aggregate_patterns(
    pattern_samples: Dict[Tuple[int, int, str], List[float]],
) -> List[Dict]:
    """
    Aggregate pattern samples to create baseline patterns.

    Args:
        pattern_samples: Dict from analyze_project_temporal_patterns()

    Returns:
        List of dicts ready for database insertion
    """
    logger.info("Aggregating patterns into baselines...")

    baselines = []

    for (start_pct, end_pct, team), samples in pattern_samples.items():
        if not samples:
            continue

        # Calculate average work percentage for this bucket
        avg_work_pct = sum(samples) / len(samples)

        baselines.append(
            {
                "timeline_start_pct": start_pct,
                "timeline_end_pct": end_pct,
                "team": team,
                "work_pct": round(avg_work_pct, 2),
                "sample_size": len(samples),
                "last_updated": datetime.now(timezone.utc),
            }
        )

    logger.info(f"Created {len(baselines)} baseline patterns (before normalization)")

    # CRITICAL: Normalize each team's patterns to sum to 100%
    # Without this, patterns can sum to >100% causing budget loss when distributing hours
    baselines_by_team = defaultdict(list)
    for baseline in baselines:
        baselines_by_team[baseline["team"]].append(baseline)

    normalized_baselines = []
    for team, team_baselines in baselines_by_team.items():
        # Calculate current total
        total = sum(b["work_pct"] for b in team_baselines)

        logger.info(f"  {team}: patterns sum to {total:.2f}% (normalizing to 100%)")

        # Normalize to 100%
        if total > 0:
            for baseline in team_baselines:
                original_pct = baseline["work_pct"]
                normalized_pct = (baseline["work_pct"] / total) * 100.0
                baseline["work_pct"] = round(normalized_pct, 2)

        normalized_baselines.extend(team_baselines)

    logger.info(
        f"Normalized {len(normalized_baselines)} baseline patterns to maintain 100% budget"
    )

    return normalized_baselines


def display_pattern_summary(baselines: List[Dict]):
    """Display learned patterns in a human-readable format."""
    logger.info("\n" + "=" * 80)
    logger.info("LEARNED TEMPORAL PATTERNS")
    logger.info("=" * 80)

    # Group by timeline bucket
    buckets = defaultdict(list)
    for baseline in baselines:
        bucket = (baseline["timeline_start_pct"], baseline["timeline_end_pct"])
        buckets[bucket].append(baseline)

    for start, end in TIMELINE_BUCKETS:
        if (start, end) not in buckets:
            continue

        logger.info(f"\nTimeline {start}-{end}% of project:")
        patterns = buckets[(start, end)]
        patterns.sort(key=lambda x: x["work_pct"], reverse=True)

        for pattern in patterns:
            logger.info(
                f"  {pattern['team']:15s}: {pattern['work_pct']:5.1f}% "
                f"of their total work (n={pattern['sample_size']})"
            )

    logger.info("\n" + "=" * 80)


def save_patterns(session, baselines: List[Dict]):
    """Save learned patterns to database."""
    logger.info(f"Saving {len(baselines)} patterns to database...")

    # Delete existing patterns
    session.query(TemporalPatternBaseline).delete()

    # Insert new patterns
    for baseline in baselines:
        pattern = TemporalPatternBaseline(**baseline)
        session.add(pattern)

    session.commit()
    logger.info("✅ Patterns saved successfully")


def main(dry_run=False):
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("TEMPORAL PATTERN LEARNING")
    logger.info("=" * 80)

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No database changes will be made\n")
    else:
        logger.info("💾 LIVE MODE - Patterns will be saved to database\n")

    session = get_session()

    try:
        # Step 1: Get project data
        project_data = get_project_timeline_data(session)

        if not project_data:
            logger.error("❌ No project data found in epic_hours table")
            return

        # Step 2: Analyze temporal patterns
        pattern_samples = analyze_project_temporal_patterns(project_data)

        # Step 3: Aggregate into baselines
        baselines = aggregate_patterns(pattern_samples)

        # Step 4: Display summary
        display_pattern_summary(baselines)

        # Step 5: Save to database (if not dry run)
        if not dry_run:
            save_patterns(session, baselines)
        else:
            logger.info("\n🔍 Dry run complete - no changes made to database")

        logger.info("\n" + "=" * 80)
        logger.info("LEARNING COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error during pattern learning: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Learn temporal patterns from historical project data"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without saving to database"
    )

    args = parser.parse_args()
    main(dry_run=args.dry_run)
