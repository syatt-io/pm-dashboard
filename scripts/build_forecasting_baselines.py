#!/usr/bin/env python3
"""
Build forecasting baselines based on project characteristics.

Analyzes historical data to create forecasting baselines based on:
1. Backend integrations required
2. Custom theme development (FE)
3. Custom designs required
4. Extensive UX research/strategy
"""

import sys
import os
from pathlib import Path
from collections import defaultdict
import csv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.models import EpicHours, ProjectCharacteristics

load_dotenv()

# Initialize database
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()


def load_project_characteristics():
    """
    Load project characteristics from database.

    Converts 1-5 scale to boolean categories:
    - High (4-5) = True
    - Low/Medium (1-3) = False

    This allows historical analysis to group projects by characteristic levels.
    """
    characteristics_records = session.query(ProjectCharacteristics).all()

    project_chars = {}
    for record in characteristics_records:
        project_chars[record.project_key] = {
            "be_integrations": record.be_integrations >= 4,
            "custom_theme": record.custom_theme >= 4,
            "custom_designs": record.custom_designs >= 4,
            "ux_research": record.ux_research >= 4,
            "extensive_customizations": record.extensive_customizations >= 4,
            "project_oversight": record.project_oversight >= 4,
        }

    print(
        f"\n📊 Loaded characteristics for {len(project_chars)} projects from database"
    )
    for proj_key, chars in sorted(project_chars.items()):
        high_chars = [k for k, v in chars.items() if v]
        print(
            f"   • {proj_key}: High complexity in {', '.join(high_chars) if high_chars else 'none'}"
        )

    return project_chars


# Load project characteristics from database
PROJECT_CHARACTERISTICS = load_project_characteristics()

# Output directory
output_dir = Path(__file__).parent.parent / "analysis_results" / "forecasting_baselines"
output_dir.mkdir(parents=True, exist_ok=True)


def analyze_by_characteristics():
    """Analyze hours by project characteristics."""
    print("\n" + "=" * 80)
    print("📊 FORECASTING BASELINES BY PROJECT CHARACTERISTICS")
    print("=" * 80)

    # Get all epic data
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

    # Organize by characteristics
    characteristic_stats = {
        "be_integrations": {True: defaultdict(list), False: defaultdict(list)},
        "custom_theme": {True: defaultdict(list), False: defaultdict(list)},
        "custom_designs": {True: defaultdict(list), False: defaultdict(list)},
        "ux_research": {True: defaultdict(list), False: defaultdict(list)},
    }

    for row in epic_data:
        project_key = row.project_key
        team = row.team
        hours = row.total_hours

        if project_key not in PROJECT_CHARACTERISTICS:
            continue

        chars = PROJECT_CHARACTERISTICS[project_key]

        # Add to each characteristic bucket
        characteristic_stats["be_integrations"][chars["be_integrations"]][team].append(
            hours
        )
        characteristic_stats["custom_theme"][chars["custom_theme"]][team].append(hours)
        characteristic_stats["custom_designs"][chars["custom_designs"]][team].append(
            hours
        )
        characteristic_stats["ux_research"][chars["ux_research"]][team].append(hours)

    # Write results to CSV
    csv_path = output_dir / "baselines_by_characteristics.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Characteristic",
                "Value",
                "Team",
                "Avg_Hours",
                "Min_Hours",
                "Max_Hours",
                "Sample_Size",
                "Median_Hours",
            ]
        )

        print("\n📋 BASELINE HOURS BY CHARACTERISTIC:")
        print("=" * 80)

        for char_name, char_data in characteristic_stats.items():
            print(f"\n{'='*80}")
            print(f"📌 {char_name.replace('_', ' ').upper()}")
            print(f"{'='*80}")

            for value in [True, False]:
                value_label = "YES" if value else "NO"
                print(f"\n{value_label}:")
                print(
                    f"  {'Team':15} | {'Avg Hours':10} | {'Range':20} | {'Samples':8}"
                )
                print(f"  {'-'*60}")

                for team in sorted(char_data[value].keys()):
                    hours_list = char_data[value][team]
                    if not hours_list:
                        continue

                    avg_hours = sum(hours_list) / len(hours_list)
                    min_hours = min(hours_list)
                    max_hours = max(hours_list)
                    sample_size = len(hours_list)
                    median_hours = sorted(hours_list)[len(hours_list) // 2]

                    writer.writerow(
                        [
                            char_name,
                            value_label,
                            team,
                            f"{avg_hours:.2f}",
                            f"{min_hours:.2f}",
                            f"{max_hours:.2f}",
                            sample_size,
                            f"{median_hours:.2f}",
                        ]
                    )

                    print(
                        f"  {team:15} | {avg_hours:10.2f}h | {min_hours:6.2f}-{max_hours:6.2f}h | {sample_size:3} epics"
                    )

    print(f"\n✅ Saved to: {csv_path}")


def build_multiplier_matrix():
    """Build multiplier matrix for forecasting based on characteristic combinations."""
    print("\n" + "=" * 80)
    print("🔢 CHARACTERISTIC MULTIPLIER MATRIX")
    print("=" * 80)

    # Get baseline (no characteristics) - use non-integration projects
    baseline_hours = defaultdict(list)
    non_integration_data = (
        session.query(
            EpicHours.project_key,
            EpicHours.epic_key,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .filter(EpicHours.project_key.in_(["BIGO", "BMBY", "IRIS", "BEVS"]))
        .group_by(EpicHours.project_key, EpicHours.epic_key, EpicHours.team)
        .all()
    )

    for row in non_integration_data:
        baseline_hours[row.team].append(row.total_hours)

    baseline_avg = {
        team: sum(hours) / len(hours) if hours else 0
        for team, hours in baseline_hours.items()
    }

    # Get integration project hours
    integration_hours = defaultdict(list)
    integration_data = (
        session.query(
            EpicHours.project_key,
            EpicHours.epic_key,
            EpicHours.team,
            func.sum(EpicHours.hours).label("total_hours"),
        )
        .filter(EpicHours.project_key.in_(["SRLK", "COOP", "CAR"]))
        .group_by(EpicHours.project_key, EpicHours.epic_key, EpicHours.team)
        .all()
    )

    for row in integration_data:
        integration_hours[row.team].append(row.total_hours)

    integration_avg = {
        team: sum(hours) / len(hours) if hours else 0
        for team, hours in integration_hours.items()
    }

    # Calculate multipliers
    csv_path = output_dir / "characteristic_multipliers.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Characteristic",
                "Team",
                "Baseline_Avg_Hours",
                "With_Characteristic_Avg_Hours",
                "Multiplier",
                "Hours_Increase",
            ]
        )

        print("\n📊 MULTIPLIERS BY CHARACTERISTIC:")
        print(
            "\n{'Team':15} | {'Baseline':10} | {'With BE Int':12} | {'Multiplier':10} | {'Increase':10}"
        )
        print("-" * 70)

        for team in sorted(baseline_avg.keys()):
            base = baseline_avg[team]
            with_integration = integration_avg.get(team, 0)

            if base > 0 and with_integration > 0:
                multiplier = with_integration / base
                increase = with_integration - base

                writer.writerow(
                    [
                        "be_integrations",
                        team,
                        f"{base:.2f}",
                        f"{with_integration:.2f}",
                        f"{multiplier:.2f}",
                        f"{increase:.2f}",
                    ]
                )

                print(
                    f"{team:15} | {base:10.2f}h | {with_integration:12.2f}h | {multiplier:10.2f}x | +{increase:8.2f}h"
                )

    print(f"\n✅ Saved to: {csv_path}")

    print("\n💡 KEY MULTIPLIERS:")
    be_multiplier = integration_avg.get("BE Devs", 0) / baseline_avg.get("BE Devs", 1)
    print(f"   • BE Integrations → BE Devs: {be_multiplier:.2f}x multiplier")


def build_forecasting_template():
    """Build a forecasting template with all baselines."""
    print("\n" + "=" * 80)
    print("📋 BUILDING FORECASTING TEMPLATE")
    print("=" * 80)

    # Get clean baselines per team
    team_baselines = defaultdict(lambda: {"no_integration": 0, "with_integration": 0})

    # Calculate per-epic averages manually
    epic_hours = defaultdict(lambda: defaultdict(float))
    no_int_records = (
        session.query(EpicHours)
        .filter(EpicHours.project_key.in_(["BIGO", "BMBY", "IRIS", "BEVS"]))
        .all()
    )

    for record in no_int_records:
        epic_id = f"{record.project_key}-{record.epic_key}"
        epic_hours[epic_id][record.team] += record.hours

    # Calculate averages
    team_epic_hours = defaultdict(list)
    for epic_id, teams in epic_hours.items():
        for team, hours in teams.items():
            team_epic_hours[team].append(hours)

    for team, hours_list in team_epic_hours.items():
        team_baselines[team]["no_integration"] = sum(hours_list) / len(hours_list)

    # With integration baseline
    epic_hours_int = defaultdict(lambda: defaultdict(float))
    int_records = (
        session.query(EpicHours)
        .filter(EpicHours.project_key.in_(["SRLK", "COOP", "CAR"]))
        .all()
    )

    for record in int_records:
        epic_id = f"{record.project_key}-{record.epic_key}"
        epic_hours_int[epic_id][record.team] += record.hours

    team_epic_hours_int = defaultdict(list)
    for epic_id, teams in epic_hours_int.items():
        for team, hours in teams.items():
            team_epic_hours_int[team].append(hours)

    for team, hours_list in team_epic_hours_int.items():
        team_baselines[team]["with_integration"] = sum(hours_list) / len(hours_list)

    # Write template
    csv_path = output_dir / "forecasting_template.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Team",
                "Baseline_No_Integration",
                "Baseline_With_Integration",
                "Ramp_Up_Pct",
                "Busy_Peak_Pct",
                "Ramp_Down_Pct",
            ]
        )

        # Lifecycle percentages from previous analysis
        lifecycle_pcts = {
            "BE Devs": {"ramp_up": 45.1, "busy": 40.5, "ramp_down": 14.5},
            "FE Devs": {"ramp_up": 45.9, "busy": 41.0, "ramp_down": 13.1},
            "Design": {"ramp_up": 87.1, "busy": 7.6, "ramp_down": 5.3},
            "UX": {"ramp_up": 82.8, "busy": 13.6, "ramp_down": 3.7},
            "PMs": {"ramp_up": 55.5, "busy": 27.3, "ramp_down": 17.1},
            "Data": {"ramp_up": 50.0, "busy": 35.0, "ramp_down": 15.0},  # Default
        }

        print("\n📊 FORECASTING TEMPLATE:")
        print("\n{'Team':15} | {'No Int':10} | {'With Int':10} | {'Lifecycle':30}")
        print("-" * 75)

        for team in sorted(team_baselines.keys()):
            no_int = team_baselines[team]["no_integration"]
            with_int = team_baselines[team]["with_integration"]

            lifecycle = lifecycle_pcts.get(
                team, {"ramp_up": 50, "busy": 35, "ramp_down": 15}
            )

            writer.writerow(
                [
                    team,
                    f"{no_int:.2f}",
                    f"{with_int:.2f}",
                    f"{lifecycle['ramp_up']:.1f}",
                    f"{lifecycle['busy']:.1f}",
                    f"{lifecycle['ramp_down']:.1f}",
                ]
            )

            print(
                f"{team:15} | {no_int:10.2f}h | {with_int:10.2f}h | {lifecycle['ramp_up']:.1f}% / {lifecycle['busy']:.1f}% / {lifecycle['ramp_down']:.1f}%"
            )

    print(f"\n✅ Saved to: {csv_path}")


def main():
    """Run all forecasting baseline analyses."""
    print("\n" + "=" * 80)
    print("🔮 BUILDING FORECASTING BASELINES")
    print("=" * 80)
    print(f"\nOutput directory: {output_dir}")

    analyze_by_characteristics()
    build_multiplier_matrix()
    build_forecasting_template()

    print("\n" + "=" * 80)
    print("✅ FORECASTING BASELINES COMPLETE")
    print("=" * 80)
    print(f"\n📁 All results saved to: {output_dir}")
    print("\n📊 Generated Files:")
    print("  1. baselines_by_characteristics.csv - Hours by each characteristic")
    print("  2. characteristic_multipliers.csv - Impact multipliers")
    print("  3. forecasting_template.csv - Ready-to-use forecasting baselines")

    session.close()


if __name__ == "__main__":
    main()
