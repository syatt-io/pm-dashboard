#!/usr/bin/env python3
"""
Analyze epic lifecycle patterns to build temporal forecasting models.

This script analyzes how hours are distributed across an epic's lifecycle
(ramp up, busy, ramp down) and provides discipline-specific patterns.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
import csv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import EpicHours

load_dotenv()

# Initialize database
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Project categorization by integration requirements
PROJECT_CATEGORIES = {
    "integration": ["SRLK", "COOP", "CAR"],  # Projects requiring backend integrations
    "no_integration": ["BIGO", "BMBY", "IRIS", "BEVS"],  # Frontend-focused projects
}

# Output directory
output_dir = Path(__file__).parent.parent / "analysis_results" / "lifecycle_analysis"
output_dir.mkdir(parents=True, exist_ok=True)


def categorize_project(project_key: str) -> str:
    """Categorize project by integration requirements."""
    if project_key in PROJECT_CATEGORIES["integration"]:
        return "Integration Required"
    elif project_key in PROJECT_CATEGORIES["no_integration"]:
        return "No Integration"
    else:
        return "Unknown"


def analyze_integration_impact():
    """Compare team allocation patterns between integration vs non-integration projects."""
    print("\n" + "=" * 80)
    print("🔌 INTEGRATION REQUIREMENT IMPACT ANALYSIS")
    print("=" * 80)

    # Get data grouped by project category and team
    integration_stats = defaultdict(
        lambda: defaultdict(lambda: {"hours": 0, "epics": set()})
    )

    all_data = (
        session.query(
            EpicHours.project_key,
            EpicHours.epic_key,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .group_by(EpicHours.project_key, EpicHours.epic_key, EpicHours.team)
        .all()
    )

    for row in all_data:
        category = categorize_project(row.project_key)
        integration_stats[category][row.team]["hours"] += row.total_hours
        integration_stats[category][row.team]["epics"].add(
            f"{row.project_key}-{row.epic_key}"
        )

    # Calculate percentages and write to CSV
    csv_path = output_dir / "1_integration_impact.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Project_Category",
                "Team",
                "Total_Hours",
                "Num_Epics",
                "Avg_Hours_Per_Epic",
                "Percent_Of_Total",
            ]
        )

        print("\n📊 Team Allocation by Project Type:")
        print(
            "\n{:25} | {:15} | {:10} | {:8} | {:12}".format(
                "Project Category", "Team", "Hours", "Epics", "% of Total"
            )
        )
        print("-" * 80)

        for category in sorted(integration_stats.keys()):
            if category == "Unknown":
                continue

            total_hours = sum(
                data["hours"] for data in integration_stats[category].values()
            )

            print(f"\n{category}")
            for team in sorted(integration_stats[category].keys()):
                data = integration_stats[category][team]
                hours = data["hours"]
                num_epics = len(data["epics"])
                avg_hours = hours / num_epics if num_epics > 0 else 0
                percent = (hours / total_hours * 100) if total_hours > 0 else 0

                writer.writerow(
                    [
                        category,
                        team,
                        f"{hours:.2f}",
                        num_epics,
                        f"{avg_hours:.2f}",
                        f"{percent:.1f}",
                    ]
                )

                print(
                    f"  {team:15} | {hours:10.2f}h | {num_epics:3} epics | {percent:5.1f}%"
                )

    print(f"\n✅ Saved to: {csv_path}")

    # Key insights
    print("\n💡 KEY INSIGHTS:")
    integration_be_pct = (
        integration_stats["Integration Required"]["BE Devs"]["hours"]
        / sum(d["hours"] for d in integration_stats["Integration Required"].values())
        * 100
    )
    no_integration_be_pct = (
        integration_stats["No Integration"]["BE Devs"]["hours"]
        / sum(d["hours"] for d in integration_stats["No Integration"].values())
        * 100
        if "BE Devs" in integration_stats["No Integration"]
        else 0
    )

    print(f"   • Integration projects: {integration_be_pct:.1f}% Backend")
    print(f"   • Non-integration projects: {no_integration_be_pct:.1f}% Backend")
    print(
        f"   • Backend multiplier: {integration_be_pct / no_integration_be_pct if no_integration_be_pct > 0 else 'N/A'}x more backend work with integrations"
    )


def analyze_epic_lifecycle_patterns():
    """Analyze how hours are distributed across epic lifecycle (ramp up, busy, ramp down)."""
    print("\n" + "=" * 80)
    print("📅 EPIC LIFECYCLE PATTERN ANALYSIS")
    print("=" * 80)

    # Get all epics with their monthly hours
    epic_timelines = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    all_records = session.query(EpicHours).all()

    for record in all_records:
        epic_id = f"{record.project_key}-{record.epic_key}"
        month_key = record.month.strftime("%Y-%m")
        epic_timelines[epic_id][month_key][record.team] += record.hours

    # Analyze lifecycle patterns for multi-month epics
    lifecycle_patterns = []

    for epic_id, months in epic_timelines.items():
        if len(months) < 3:  # Only analyze epics spanning 3+ months
            continue

        # Sort months chronologically
        sorted_months = sorted(months.keys())
        total_months = len(sorted_months)

        # Calculate total hours per team across all months
        team_totals = defaultdict(float)
        for month_data in months.values():
            for team, hours in month_data.items():
                team_totals[team] += hours

        # Calculate percentage distribution by lifecycle phase for each team
        for team, total_team_hours in team_totals.items():
            if total_team_hours == 0:
                continue

            monthly_percentages = []
            for i, month in enumerate(sorted_months):
                hours = months[month].get(team, 0)
                pct = (hours / total_team_hours * 100) if total_team_hours > 0 else 0

                # Determine phase
                if total_months <= 3:
                    phase = ["Early", "Mid", "Late"][i]
                elif total_months <= 6:
                    if i < total_months * 0.25:
                        phase = "Ramp Up"
                    elif i > total_months * 0.75:
                        phase = "Ramp Down"
                    else:
                        phase = "Busy"
                else:
                    if i < 2:
                        phase = "Ramp Up"
                    elif i >= total_months - 2:
                        phase = "Ramp Down"
                    else:
                        phase = "Busy"

                monthly_percentages.append(
                    {"month_num": i + 1, "phase": phase, "pct": pct}
                )

            lifecycle_patterns.append(
                {
                    "epic_id": epic_id,
                    "team": team,
                    "total_months": total_months,
                    "total_hours": total_team_hours,
                    "monthly_pcts": monthly_percentages,
                }
            )

    # Write detailed lifecycle data to CSV
    csv_path = output_dir / "2_epic_lifecycle_details.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Epic",
                "Team",
                "Total_Months",
                "Total_Hours",
                "Month_Num",
                "Phase",
                "Percent_Of_Total",
            ]
        )

        for pattern in lifecycle_patterns:
            for month_data in pattern["monthly_pcts"]:
                writer.writerow(
                    [
                        pattern["epic_id"],
                        pattern["team"],
                        pattern["total_months"],
                        f"{pattern['total_hours']:.2f}",
                        month_data["month_num"],
                        month_data["phase"],
                        f"{month_data['pct']:.1f}",
                    ]
                )

    print(f"✅ Saved detailed lifecycle data to: {csv_path}")
    print(f"   📊 Analyzed {len(lifecycle_patterns)} epic-team combinations")


def build_lifecycle_model_by_team():
    """Build aggregated lifecycle model showing average % of hours by phase and team."""
    print("\n" + "=" * 80)
    print("🎯 LIFECYCLE FORECASTING MODEL BY DISCIPLINE")
    print("=" * 80)

    # Get all epics with their monthly hours
    epic_timelines = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    all_records = session.query(EpicHours).all()

    for record in all_records:
        epic_id = f"{record.project_key}-{record.epic_key}"
        month_key = record.month.strftime("%Y-%m")
        epic_timelines[epic_id][month_key][record.team] += record.hours

    # Aggregate patterns by team and phase
    team_phase_patterns = defaultdict(lambda: defaultdict(list))

    for epic_id, months in epic_timelines.items():
        if len(months) < 3:  # Only multi-month epics
            continue

        sorted_months = sorted(months.keys())
        total_months = len(sorted_months)

        # Calculate team totals
        team_totals = defaultdict(float)
        for month_data in months.values():
            for team, hours in month_data.items():
                team_totals[team] += hours

        # Categorize each month into phases
        for team, total_team_hours in team_totals.items():
            if total_team_hours < 5:  # Skip very small contributions
                continue

            phase_hours = defaultdict(float)

            for i, month in enumerate(sorted_months):
                hours = months[month].get(team, 0)

                # Determine phase based on position in epic timeline
                progress = i / (total_months - 1) if total_months > 1 else 0

                if progress < 0.33:
                    phase = "Ramp Up"
                elif progress > 0.67:
                    phase = "Ramp Down"
                else:
                    phase = "Busy (Peak)"

                phase_hours[phase] += hours

            # Convert to percentages
            for phase, hours in phase_hours.items():
                pct = (hours / total_team_hours * 100) if total_team_hours > 0 else 0
                team_phase_patterns[team][phase].append(pct)

    # Calculate averages
    csv_path = output_dir / "3_lifecycle_model_by_discipline.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Team",
                "Phase",
                "Avg_Percent_Of_Total",
                "Min_Percent",
                "Max_Percent",
                "Sample_Size",
                "Use_For_Forecasting",
            ]
        )

        print("\n📊 AVERAGE HOUR DISTRIBUTION BY LIFECYCLE PHASE:")
        print(
            "\n{:15} | {:15} | {:10} | {:20}".format("Team", "Phase", "Avg %", "Range")
        )
        print("-" * 70)

        for team in sorted(team_phase_patterns.keys()):
            print(f"\n{team}")

            # Ensure all phases are present
            for phase in ["Ramp Up", "Busy (Peak)", "Ramp Down"]:
                pcts = team_phase_patterns[team].get(phase, [])

                if pcts:
                    avg_pct = sum(pcts) / len(pcts)
                    min_pct = min(pcts)
                    max_pct = max(pcts)
                    sample_size = len(pcts)

                    # Recommendation for forecasting
                    if sample_size >= 10:
                        forecast_value = f"{avg_pct:.1f}%"
                    elif sample_size >= 5:
                        forecast_value = f"{avg_pct:.1f}% (use with caution)"
                    else:
                        forecast_value = "Insufficient data"

                    writer.writerow(
                        [
                            team,
                            phase,
                            f"{avg_pct:.1f}",
                            f"{min_pct:.1f}",
                            f"{max_pct:.1f}",
                            sample_size,
                            forecast_value,
                        ]
                    )

                    print(
                        f"  {phase:15} | {avg_pct:6.1f}% | {min_pct:.1f}%-{max_pct:.1f}% (n={sample_size})"
                    )

    print(f"\n✅ Saved to: {csv_path}")


def build_integrated_forecasting_guide():
    """Build comprehensive forecasting guide incorporating integration requirements and lifecycle."""
    print("\n" + "=" * 80)
    print("🔮 INTEGRATED FORECASTING GUIDE")
    print("=" * 80)

    # Get baseline hours by project category and team
    baseline_data = defaultdict(lambda: defaultdict(lambda: {"hours": [], "epics": 0}))

    epic_data = (
        session.query(
            EpicHours.project_key,
            EpicHours.epic_key,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .group_by(EpicHours.project_key, EpicHours.epic_key, EpicHours.team)
        .all()
    )

    for row in epic_data:
        category = categorize_project(row.project_key)
        if category != "Unknown":
            baseline_data[category][row.team]["hours"].append(row.total_hours)
            baseline_data[category][row.team]["epics"] += 1

    # Write integrated guide
    csv_path = output_dir / "4_integrated_forecasting_guide.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Project_Type",
                "Team",
                "Avg_Hours_Per_Epic",
                "Min_Hours",
                "Max_Hours",
                "Sample_Size",
                "Confidence",
                "Ramp_Up_Pct",
                "Busy_Peak_Pct",
                "Ramp_Down_Pct",
            ]
        )

        print("\n📋 FORECASTING GUIDE WITH INTEGRATION & LIFECYCLE:")
        print(
            "\n{:25} | {:15} | {:10} | {:8} | {:30}".format(
                "Project Type", "Team", "Avg Hours", "Samples", "Lifecycle Pattern"
            )
        )
        print("-" * 95)

        for category in ["Integration Required", "No Integration"]:
            print(f"\n{category}")

            for team in sorted(baseline_data[category].keys()):
                data = baseline_data[category][team]
                hours_list = data["hours"]

                if not hours_list:
                    continue

                avg_hours = sum(hours_list) / len(hours_list)
                min_hours = min(hours_list)
                max_hours = max(hours_list)
                sample_size = len(hours_list)

                confidence = (
                    "High"
                    if sample_size > 20
                    else "Medium" if sample_size > 10 else "Low"
                )

                # Placeholder for lifecycle (will be filled from previous analysis)
                lifecycle = "See lifecycle model"

                writer.writerow(
                    [
                        category,
                        team,
                        f"{avg_hours:.2f}",
                        f"{min_hours:.2f}",
                        f"{max_hours:.2f}",
                        sample_size,
                        confidence,
                        "",
                        "",
                        "",  # To be filled with lifecycle data
                    ]
                )

                print(
                    f"  {team:15} | {avg_hours:8.2f}h | {sample_size:3} epics | {lifecycle}"
                )

    print(f"\n✅ Saved to: {csv_path}")

    # Print key takeaways
    print("\n💡 HOW TO USE THIS FORECASTING GUIDE:")
    print("   1. Determine if project requires integrations (backend work)")
    print("   2. Select appropriate baseline hours for each team from guide")
    print("   3. Apply lifecycle model percentages to distribute hours over time")
    print("   4. Adjust based on epic complexity (use complexity scores)")


def main():
    """Run all lifecycle analyses."""
    print("\n" + "=" * 80)
    print("🔄 EPIC LIFECYCLE & INTEGRATION IMPACT ANALYSIS")
    print("=" * 80)
    print(f"\nOutput directory: {output_dir}")

    # Run analyses
    analyze_integration_impact()
    analyze_epic_lifecycle_patterns()
    build_lifecycle_model_by_team()
    build_integrated_forecasting_guide()

    print("\n" + "=" * 80)
    print("✅ LIFECYCLE ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\n📁 All results saved to: {output_dir}")
    print("\n📊 Generated Files:")
    print("  1. integration_impact.csv - Team allocation by project type")
    print("  2. epic_lifecycle_details.csv - Detailed month-by-month patterns")
    print("  3. lifecycle_model_by_discipline.csv - Average % by phase and team")
    print("  4. integrated_forecasting_guide.csv - Complete forecasting tool")

    session.close()


if __name__ == "__main__":
    main()
