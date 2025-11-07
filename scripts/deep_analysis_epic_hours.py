#!/usr/bin/env python3
"""
Deep analysis of epic hours data with team tracking.

Generates strategic insights for resource planning and forecasting.

Usage:
    python scripts/deep_analysis_epic_hours.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import csv

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, func, and_, distinct
from sqlalchemy.orm import sessionmaker
from src.models import EpicHours

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Create output directory
output_dir = Path(__file__).parent.parent / 'analysis_results' / 'deep_insights'
output_dir.mkdir(parents=True, exist_ok=True)


def analyze_team_allocation():
    """Team allocation matrix - which teams spend time on which projects."""
    print("\n" + "="*80)
    print("📊 TEAM ALLOCATION MATRIX")
    print("="*80)

    results = session.query(
        EpicHours.project_key,
        EpicHours.team,
        func.sum(EpicHours.hours).label('total_hours'),
        func.count(distinct(EpicHours.epic_key)).label('num_epics')
    ).group_by(
        EpicHours.project_key,
        EpicHours.team
    ).order_by(
        EpicHours.project_key,
        func.sum(EpicHours.hours).desc()
    ).all()

    # Write to CSV
    csv_path = output_dir / '1_team_allocation_matrix.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Project', 'Team', 'Total_Hours', 'Num_Epics', 'Avg_Hours_Per_Epic', 'Utilization_%'])

        project_totals = defaultdict(float)
        for row in results:
            project_totals[row.project_key] += row.total_hours

        for row in results:
            avg_hours = row.total_hours / row.num_epics if row.num_epics > 0 else 0
            utilization = (row.total_hours / project_totals[row.project_key] * 100) if project_totals[row.project_key] > 0 else 0
            writer.writerow([
                row.project_key,
                row.team,
                f"{row.total_hours:.2f}",
                row.num_epics,
                f"{avg_hours:.2f}",
                f"{utilization:.1f}"
            ])
            print(f"  {row.project_key:10} | {row.team:15} | {row.total_hours:8.2f}h | {row.num_epics:3} epics | {utilization:5.1f}%")

    print(f"\n✅ Saved to: {csv_path}")


def analyze_epic_complexity():
    """Analyze epic complexity based on team diversity and total hours."""
    print("\n" + "="*80)
    print("🧩 EPIC COMPLEXITY ANALYSIS")
    print("="*80)

    # Get all epics with team counts
    epic_data = session.query(
        EpicHours.project_key,
        EpicHours.epic_key,
        EpicHours.epic_summary,
        func.count(distinct(EpicHours.team)).label('num_teams'),
        func.sum(EpicHours.hours).label('total_hours')
    ).group_by(
        EpicHours.project_key,
        EpicHours.epic_key,
        EpicHours.epic_summary
    ).having(
        func.sum(EpicHours.hours) > 0
    ).all()

    # Calculate complexity score (num_teams * log(total_hours))
    import math
    complexity_scores = []
    for epic in epic_data:
        score = epic.num_teams * math.log(epic.total_hours + 1)  # +1 to avoid log(0)
        complexity_scores.append({
            'project': epic.project_key,
            'epic': epic.epic_key,
            'summary': epic.epic_summary,
            'num_teams': epic.num_teams,
            'total_hours': epic.total_hours,
            'complexity_score': score
        })

    # Sort by complexity score
    complexity_scores.sort(key=lambda x: x['complexity_score'], reverse=True)

    # Write to CSV
    csv_path = output_dir / '2_epic_complexity_scores.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Project', 'Epic', 'Epic_Summary', 'Num_Teams', 'Total_Hours', 'Complexity_Score', 'Complexity_Level'])

        for item in complexity_scores:
            # Classify complexity
            if item['complexity_score'] > 30:
                level = 'Very High'
            elif item['complexity_score'] > 20:
                level = 'High'
            elif item['complexity_score'] > 10:
                level = 'Medium'
            else:
                level = 'Low'

            writer.writerow([
                item['project'],
                item['epic'],
                item['summary'],
                item['num_teams'],
                f"{item['total_hours']:.2f}",
                f"{item['complexity_score']:.2f}",
                level
            ])

    # Print top 10 most complex
    print("\n📈 Top 10 Most Complex Epics:")
    for i, item in enumerate(complexity_scores[:10], 1):
        print(f"  {i:2}. {item['project']}-{item['epic']:10} | {item['num_teams']} teams | {item['total_hours']:7.2f}h | Score: {item['complexity_score']:.2f}")
        print(f"      {item['summary'][:70]}")

    print(f"\n✅ Saved to: {csv_path}")


def analyze_team_collaboration():
    """Analyze which teams work together most frequently."""
    print("\n" + "="*80)
    print("🤝 TEAM COLLABORATION PATTERNS")
    print("="*80)

    # Get epics and their teams
    epic_teams = defaultdict(set)
    epic_query = session.query(
        EpicHours.project_key,
        EpicHours.epic_key,
        EpicHours.team
    ).all()

    for row in epic_query:
        epic_id = f"{row.project_key}:{row.epic_key}"
        epic_teams[epic_id].add(row.team)

    # Count team pairs
    team_pairs = defaultdict(int)
    for epic_id, teams in epic_teams.items():
        teams_list = sorted(list(teams))
        for i, team1 in enumerate(teams_list):
            for team2 in teams_list[i+1:]:
                pair = f"{team1} + {team2}"
                team_pairs[pair] += 1

    # Sort by frequency
    sorted_pairs = sorted(team_pairs.items(), key=lambda x: x[1], reverse=True)

    # Write to CSV
    csv_path = output_dir / '3_team_collaboration_matrix.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Team_Pair', 'Num_Shared_Epics', 'Collaboration_Frequency'])

        for pair, count in sorted_pairs:
            writer.writerow([pair, count, 'High' if count > 50 else 'Medium' if count > 20 else 'Low'])

    # Print top collaborations
    print("\n🔝 Top 10 Team Collaborations:")
    for i, (pair, count) in enumerate(sorted_pairs[:10], 1):
        print(f"  {i:2}. {pair:30} | {count:3} shared epics")

    print(f"\n✅ Saved to: {csv_path}")


def analyze_baseline_estimates():
    """Generate baseline estimates for different epic/team combinations."""
    print("\n" + "="*80)
    print("📊 BASELINE ESTIMATES FOR FORECASTING")
    print("="*80)

    # Calculate average hours per team per epic
    baselines = session.query(
        EpicHours.project_key,
        EpicHours.team,
        func.avg(EpicHours.hours).label('avg_hours'),
        func.min(EpicHours.hours).label('min_hours'),
        func.max(EpicHours.hours).label('max_hours'),
        func.count(EpicHours.id).label('sample_size')
    ).group_by(
        EpicHours.project_key,
        EpicHours.team
    ).having(
        func.count(EpicHours.id) >= 3  # At least 3 samples
    ).order_by(
        EpicHours.project_key,
        EpicHours.team
    ).all()

    # Write to CSV
    csv_path = output_dir / '4_baseline_estimates.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Project', 'Team', 'Avg_Hours', 'Min_Hours', 'Max_Hours', 'Sample_Size', 'Confidence'])

        for row in baselines:
            confidence = 'High' if row.sample_size > 20 else 'Medium' if row.sample_size > 10 else 'Low'
            writer.writerow([
                row.project_key,
                row.team,
                f"{row.avg_hours:.2f}",
                f"{row.min_hours:.2f}",
                f"{row.max_hours:.2f}",
                row.sample_size,
                confidence
            ])
            print(f"  {row.project_key:10} | {row.team:15} | Avg: {row.avg_hours:6.2f}h | Range: {row.min_hours:.2f}-{row.max_hours:.2f}h | n={row.sample_size}")

    print(f"\n✅ Saved to: {csv_path}")


def analyze_monthly_trends():
    """Analyze how team allocation changes over time."""
    print("\n" + "="*80)
    print("📈 MONTHLY TREND ANALYSIS")
    print("="*80)

    trends = session.query(
        EpicHours.project_key,
        EpicHours.month,
        EpicHours.team,
        func.sum(EpicHours.hours).label('total_hours')
    ).group_by(
        EpicHours.project_key,
        EpicHours.month,
        EpicHours.team
    ).order_by(
        EpicHours.project_key,
        EpicHours.month,
        func.sum(EpicHours.hours).desc()
    ).all()

    # Write to CSV
    csv_path = output_dir / '5_monthly_trends.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Project', 'Month', 'Team', 'Hours', 'Year', 'Month_Name'])

        for row in trends:
            year = row.month.year
            month_name = row.month.strftime('%B')
            writer.writerow([
                row.project_key,
                row.month.strftime('%Y-%m'),
                row.team,
                f"{row.total_hours:.2f}",
                year,
                month_name
            ])

    print(f"✅ Saved to: {csv_path}")
    print(f"   📊 Use this for time-series analysis and trend visualization")


def analyze_epic_types():
    """Categorize epics by team composition patterns."""
    print("\n" + "="*80)
    print("🏷️  EPIC TYPE CATEGORIZATION")
    print("="*80)

    # Get epics with their team composition
    epic_compositions = defaultdict(lambda: {'teams': set(), 'hours': 0, 'summary': ''})

    all_epics = session.query(
        EpicHours.project_key,
        EpicHours.epic_key,
        EpicHours.epic_summary,
        EpicHours.team,
        EpicHours.hours
    ).all()

    for row in all_epics:
        epic_id = f"{row.project_key}:{row.epic_key}"
        epic_compositions[epic_id]['teams'].add(row.team)
        epic_compositions[epic_id]['hours'] += row.hours
        epic_compositions[epic_id]['summary'] = row.epic_summary

    # Categorize epics
    categories = defaultdict(list)
    for epic_id, data in epic_compositions.items():
        teams = data['teams']

        # Determine category
        if teams == {'FE Devs'}:
            category = 'Frontend-Only'
        elif teams == {'BE Devs'}:
            category = 'Backend-Only'
        elif teams == {'Design'} or teams == {'UX'} or teams == {'Design', 'UX'}:
            category = 'Design-Only'
        elif teams == {'PMs'}:
            category = 'PM-Coordination'
        elif 'FE Devs' in teams and 'BE Devs' in teams and len(teams) == 2:
            category = 'Full-Stack'
        elif len(teams) >= 4:
            category = 'Cross-Functional (Complex)'
        elif len(teams) == 3:
            category = 'Multi-Discipline'
        else:
            category = 'Mixed'

        categories[category].append({
            'epic_id': epic_id,
            'teams': ', '.join(sorted(teams)),
            'hours': data['hours'],
            'summary': data['summary']
        })

    # Write to CSV
    csv_path = output_dir / '6_epic_categorization.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Category', 'Epic', 'Teams_Involved', 'Total_Hours', 'Epic_Summary'])

        for category in sorted(categories.keys()):
            epics = sorted(categories[category], key=lambda x: x['hours'], reverse=True)
            for epic in epics:
                project, epic_key = epic['epic_id'].split(':')
                writer.writerow([
                    category,
                    f"{project}-{epic_key}",
                    epic['teams'],
                    f"{epic['hours']:.2f}",
                    epic['summary']
                ])

    # Print summary
    print("\n📊 Epic Distribution by Category:")
    for category in sorted(categories.keys()):
        count = len(categories[category])
        total_hours = sum(e['hours'] for e in categories[category])
        avg_hours = total_hours / count if count > 0 else 0
        print(f"  {category:30} | {count:3} epics | {total_hours:8.2f}h total | {avg_hours:6.2f}h avg")

    print(f"\n✅ Saved to: {csv_path}")


def generate_forecasting_guide():
    """Generate a forecasting guide for new epics."""
    print("\n" + "="*80)
    print("🔮 FORECASTING GUIDE")
    print("="*80)

    # Calculate statistics for different epic types
    # This will help estimate new epics

    guide_data = []

    # Get epic type patterns (sum per epic, not nested avg)
    epic_stats = session.query(
        EpicHours.project_key,
        EpicHours.epic_key,
        func.count(distinct(EpicHours.team)).label('num_teams'),
        func.sum(EpicHours.hours).label('total_hours')
    ).group_by(
        EpicHours.project_key,
        EpicHours.epic_key
    ).all()

    # Aggregate by team count
    team_count_stats = defaultdict(list)
    for stat in epic_stats:
        team_count_stats[stat.num_teams].append(stat.total_hours)

    # Write to CSV
    csv_path = output_dir / '7_forecasting_guide.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Num_Teams_Involved',
            'Avg_Total_Hours',
            'Min_Hours',
            'Max_Hours',
            'Sample_Count',
            'Estimate_Range_Low',
            'Estimate_Range_High'
        ])

        for num_teams in sorted(team_count_stats.keys()):
            hours_list = team_count_stats[num_teams]
            avg_hours = sum(hours_list) / len(hours_list)
            min_hours = min(hours_list)
            max_hours = max(hours_list)

            # Conservative estimate range (25th-75th percentile approximation)
            sorted_hours = sorted(hours_list)
            p25_idx = len(sorted_hours) // 4
            p75_idx = 3 * len(sorted_hours) // 4
            low_estimate = sorted_hours[p25_idx] if len(sorted_hours) > 4 else min_hours
            high_estimate = sorted_hours[p75_idx] if len(sorted_hours) > 4 else max_hours

            writer.writerow([
                num_teams,
                f"{avg_hours:.2f}",
                f"{min_hours:.2f}",
                f"{max_hours:.2f}",
                len(hours_list),
                f"{low_estimate:.2f}",
                f"{high_estimate:.2f}"
            ])

            print(f"  {num_teams} teams | Avg: {avg_hours:6.2f}h | Range: {min_hours:.2f}-{max_hours:.2f}h | Estimate: {low_estimate:.2f}-{high_estimate:.2f}h (n={len(hours_list)})")

    print(f"\n✅ Saved to: {csv_path}")
    print("\n💡 Use this guide to estimate new epics based on team involvement")


def main():
    """Run all deep analyses."""
    print("="*80)
    print("🔍 DEEP INSIGHTS ANALYSIS - EPIC HOURS WITH TEAM TRACKING")
    print("="*80)
    print(f"\nOutput directory: {output_dir}")

    analyze_team_allocation()
    analyze_epic_complexity()
    analyze_team_collaboration()
    analyze_baseline_estimates()
    analyze_monthly_trends()
    analyze_epic_types()
    generate_forecasting_guide()

    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)
    print(f"\n📁 All insights saved to: {output_dir}")
    print("\n📊 Generated Files:")
    print("  1. team_allocation_matrix.csv - Team utilization by project")
    print("  2. epic_complexity_scores.csv - Epic complexity rankings")
    print("  3. team_collaboration_matrix.csv - Team collaboration patterns")
    print("  4. baseline_estimates.csv - Historical averages for forecasting")
    print("  5. monthly_trends.csv - Time-series data for trend analysis")
    print("  6. epic_categorization.csv - Epic types by team composition")
    print("  7. forecasting_guide.csv - Estimation guide for new epics")

    session.close()


if __name__ == "__main__":
    main()
