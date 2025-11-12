#!/usr/bin/env python3
"""
Analyze temporal patterns in project work distribution.

This script analyzes how hours are distributed across a project's lifecycle,
identifies early vs late phase patterns, and calculates burn rates.

Usage:
    python scripts/analyze_temporal_patterns.py
    python scripts/analyze_temporal_patterns.py --project COOP
"""

import sys
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemporalPatternAnalyzer:
    """Analyze temporal patterns in project work."""

    def __init__(self):
        self.session = get_session()

    def get_project_timeline(self, project_key: str) -> Dict:
        """Get project timeline and month-by-month breakdown."""
        results = (
            self.session.query(
                EpicHours.month,
                EpicHours.epic_summary,
                func.sum(EpicHours.hours).label("hours"),
            )
            .filter(EpicHours.project_key == project_key)
            .group_by(EpicHours.month, EpicHours.epic_summary)
            .order_by(EpicHours.month)
            .all()
        )

        if not results:
            return None

        # Build timeline
        months = sorted(set(r.month for r in results))
        total_months = len(months)

        # Calculate phases
        early_cutoff = int(total_months * 0.33)
        late_cutoff = int(total_months * 0.67)

        month_data = []
        monthly_hours = defaultdict(float)
        phase_data = {
            "early": defaultdict(float),
            "mid": defaultdict(float),
            "late": defaultdict(float),
        }

        for month_idx, month in enumerate(months, 1):
            month_epics = [r for r in results if r.month == month]
            month_total = sum(r.hours for r in month_epics)
            monthly_hours[month] = month_total

            # Determine phase
            if month_idx <= early_cutoff:
                phase = "early"
            elif month_idx <= late_cutoff:
                phase = "mid"
            else:
                phase = "late"

            # Track epic hours by phase
            for epic_result in month_epics:
                if epic_result.epic_summary:
                    phase_data[phase][epic_result.epic_summary] += epic_result.hours

            month_data.append(
                {
                    "month": month.strftime("%Y-%m"),
                    "month_num": month_idx,
                    "hours": round(month_total, 1),
                    "phase": phase,
                    "top_epics": sorted(
                        [
                            (r.epic_summary, r.hours)
                            for r in month_epics
                            if r.epic_summary
                        ],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3],
                }
            )

        # Calculate statistics
        total_hours = sum(monthly_hours.values())
        avg_burn_rate = total_hours / total_months if total_months > 0 else 0

        # Phase summaries
        phase_summaries = {}
        for phase, epics in phase_data.items():
            phase_hours = sum(epics.values())
            phase_percentage = (
                (phase_hours / total_hours * 100) if total_hours > 0 else 0
            )

            top_epics = sorted(epics.items(), key=lambda x: x[1], reverse=True)[:5]

            phase_summaries[phase] = {
                "hours": round(phase_hours, 1),
                "percentage": round(phase_percentage, 1),
                "top_epics": [
                    (
                        epic,
                        round(hours, 1),
                        round(hours / phase_hours * 100, 1) if phase_hours > 0 else 0,
                    )
                    for epic, hours in top_epics
                ],
            }

        return {
            "project_key": project_key,
            "start_month": months[0].strftime("%Y-%m"),
            "end_month": months[-1].strftime("%Y-%m"),
            "total_months": total_months,
            "total_hours": round(total_hours, 1),
            "avg_burn_rate": round(avg_burn_rate, 1),
            "min_month_hours": round(min(monthly_hours.values()), 1),
            "max_month_hours": round(max(monthly_hours.values()), 1),
            "month_data": month_data,
            "phase_summaries": phase_summaries,
        }

    def analyze_all_projects(self) -> List[Dict]:
        """Analyze temporal patterns for all projects."""
        projects = self.session.query(EpicHours.project_key).distinct().all()
        results = []

        for (project_key,) in projects:
            timeline = self.get_project_timeline(project_key)
            if timeline:
                results.append(timeline)

        return sorted(results, key=lambda x: x["total_hours"], reverse=True)

    def classify_project_pattern(self, timeline: Dict) -> str:
        """
        Classify project temporal pattern:
        - front-loaded: >40% hours in early phase
        - back-loaded: >40% hours in late phase
        - balanced: hours distributed evenly
        """
        early_pct = timeline["phase_summaries"]["early"]["percentage"]
        late_pct = timeline["phase_summaries"]["late"]["percentage"]

        if early_pct > 40:
            return "front-loaded"
        elif late_pct > 40:
            return "back-loaded"
        else:
            return "balanced"

    def print_analysis(self, analysis: List[Dict], project_filter: str = None):
        """Pretty print temporal analysis."""
        if project_filter:
            analysis = [a for a in analysis if a["project_key"] == project_filter]

        print("\n" + "=" * 100)
        print("TEMPORAL PATTERNS ANALYSIS")
        print("=" * 100)

        # Overall summary
        total_projects = len(analysis)
        avg_duration = (
            sum(a["total_months"] for a in analysis) / total_projects
            if total_projects > 0
            else 0
        )
        avg_burn = (
            sum(a["avg_burn_rate"] for a in analysis) / total_projects
            if total_projects > 0
            else 0
        )

        pattern_counts = defaultdict(int)
        for a in analysis:
            pattern = self.classify_project_pattern(a)
            pattern_counts[pattern] += 1

        print(f"\n{'SUMMARY':<40} {'Value'}")
        print("-" * 100)
        print(f"{'Total Projects Analyzed:':<40} {total_projects}")
        print(f"{'Average Project Duration:':<40} {avg_duration:.1f} months")
        print(f"{'Average Burn Rate:':<40} {avg_burn:.1f}h/month")
        print(f"{'Front-loaded Projects:':<40} {pattern_counts['front-loaded']}")
        print(f"{'Balanced Projects:':<40} {pattern_counts['balanced']}")
        print(f"{'Back-loaded Projects:':<40} {pattern_counts['back-loaded']}")

        # Per-project details
        for timeline in analysis:
            pattern = self.classify_project_pattern(timeline)

            print(f"\n{'=' * 100}")
            print(f"PROJECT: {timeline['project_key']} (Pattern: {pattern.upper()})")
            print(f"{'=' * 100}")
            print(
                f"{'Timeline:':<40} {timeline['start_month']} to {timeline['end_month']} ({timeline['total_months']} months)"
            )
            print(f"{'Total Hours:':<40} {timeline['total_hours']:.1f}h")
            print(f"{'Average Burn Rate:':<40} {timeline['avg_burn_rate']:.1f}h/month")
            print(f"{'Peak Month:':<40} {timeline['max_month_hours']:.1f}h")
            print(f"{'Slowest Month:':<40} {timeline['min_month_hours']:.1f}h")

            # Phase breakdown
            print(
                f"\n{'PHASE BREAKDOWN':<15} {'Hours':<15} {'% of Total':<15} {'Top Epics'}"
            )
            print("-" * 100)

            for phase in ["early", "mid", "late"]:
                phase_info = timeline["phase_summaries"][phase]
                phase_label = f"{phase.upper()} ({timeline['total_months']//3 if phase != 'mid' else timeline['total_months'] - 2*(timeline['total_months']//3)} months)"

                print(
                    f"{phase_label:<15} {phase_info['hours']:<15.1f} {phase_info['percentage']:<15.1f}%"
                )

                for epic, hours, pct in phase_info["top_epics"][:3]:
                    print(f"{'':15} {'':<15} {'':<15} {epic[:50]} ({pct:.1f}%)")

            # Monthly timeline
            print(
                f"\n{'MONTHLY TIMELINE':<12} {'Hours':<10} {'Phase':<10} {'Top Epics'}"
            )
            print("-" * 100)

            for month in timeline["month_data"]:
                top_epic = (
                    month["top_epics"][0][0][:40] if month["top_epics"] else "N/A"
                )
                print(
                    f"{month['month']:<12} {month['hours']:<10.1f} {month['phase']:<10} {top_epic}"
                )

        print("=" * 100 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze temporal patterns in project work"
    )
    parser.add_argument("--project", type=str, help="Filter to specific project")

    args = parser.parse_args()

    analyzer = TemporalPatternAnalyzer()
    logger.info("Analyzing temporal patterns across all projects...")

    analysis = analyzer.analyze_all_projects()
    analyzer.print_analysis(analysis, project_filter=args.project)

    logger.info("Analysis complete!")


if __name__ == "__main__":
    main()
