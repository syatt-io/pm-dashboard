#!/usr/bin/env python3
"""
Analyze custom features and calculate project complexity scores.

This script identifies project-specific epics (appearing in only 1 project) and
calculates a custom complexity score to help with risk assessment during scoping.

Usage:
    python scripts/analyze_custom_features.py
    python scripts/analyze_custom_features.py --project COOP
"""

import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours, EpicBaseline
from src.utils.database import get_session
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CustomFeatureAnalyzer:
    """Analyze custom features and project complexity."""

    HIGH_RISK_THRESHOLD = 50  # Hours per epic
    CUSTOM_COMPLEXITY_THRESHOLDS = {
        "low": 0.20,  # < 20% custom work
        "medium": 0.40,  # 20-40% custom work
        "high": 0.40,  # > 40% custom work
    }

    def __init__(self):
        self.session = get_session()
        self.baseline_categories = self._load_baseline_categories()

    def _load_baseline_categories(self) -> set:
        """Load all baseline epic categories."""
        baselines = self.session.query(EpicBaseline.epic_category).all()
        return {b.epic_category for b in baselines}

    def normalize_epic_name(self, epic_summary: str) -> str:
        """Normalize epic names for comparison."""
        return epic_summary.strip().lower()

    def is_custom_epic(self, epic_summary: str) -> bool:
        """Check if an epic is custom (not in baseline library)."""
        normalized = self.normalize_epic_name(epic_summary)
        return normalized not in self.baseline_categories

    def get_custom_epics_by_project(self) -> Dict[str, List[Dict]]:
        """Get all custom epics grouped by project."""
        # Get all epics with their total hours by project
        results = (
            self.session.query(
                EpicHours.project_key,
                EpicHours.epic_key,
                EpicHours.epic_summary,
                func.sum(EpicHours.hours).label("total_hours"),
                func.count(EpicHours.id).label("occurrence_count"),
            )
            .group_by(EpicHours.project_key, EpicHours.epic_key, EpicHours.epic_summary)
            .all()
        )

        # Group by epic to find which appear in multiple projects
        epic_projects = defaultdict(set)
        epic_data = {}

        for result in results:
            if not result.epic_summary:
                continue

            epic_key = result.epic_key
            epic_projects[epic_key].add(result.project_key)

            if epic_key not in epic_data:
                epic_data[epic_key] = {
                    "epic_key": epic_key,
                    "epic_summary": result.epic_summary,
                    "total_hours": 0,
                    "projects": [],
                }

            epic_data[epic_key]["total_hours"] += result.total_hours
            epic_data[epic_key]["projects"].append(
                {
                    "project_key": result.project_key,
                    "hours": result.total_hours,
                    "occurrences": result.occurrence_count,
                }
            )

        # Filter to custom epics (only 1 project OR not in baseline library)
        custom_epics_by_project = defaultdict(list)

        for epic_key, data in epic_data.items():
            project_count = len(epic_projects[epic_key])
            is_in_baseline = not self.is_custom_epic(data["epic_summary"])

            # Custom if: (1) appears in only 1 project, OR (2) not in baseline library
            if project_count == 1 or not is_in_baseline:
                for project_info in data["projects"]:
                    custom_epics_by_project[project_info["project_key"]].append(
                        {
                            "epic_key": data["epic_key"],
                            "epic_summary": data["epic_summary"],
                            "hours": project_info["hours"],
                            "occurrences": project_info["occurrences"],
                            "avg_hours_per_occurrence": project_info["hours"]
                            / project_info["occurrences"],
                            "is_high_risk": project_info["hours"]
                            > self.HIGH_RISK_THRESHOLD,
                            "reason": (
                                "unique_to_project"
                                if project_count == 1
                                else "not_in_baseline"
                            ),
                        }
                    )

        return dict(custom_epics_by_project)

    def calculate_complexity_score(self, project_key: str) -> Dict:
        """Calculate custom complexity score for a project."""
        # Get total hours for project
        total_hours = (
            self.session.query(func.sum(EpicHours.hours))
            .filter(EpicHours.project_key == project_key)
            .scalar()
            or 0
        )

        # Get custom epic hours
        custom_epics = self.get_custom_epics_by_project().get(project_key, [])
        custom_hours = sum(e["hours"] for e in custom_epics)
        custom_percentage = (custom_hours / total_hours * 100) if total_hours > 0 else 0

        # Count high-risk custom epics (> 50h)
        high_risk_epics = [e for e in custom_epics if e["is_high_risk"]]
        high_risk_hours = sum(e["hours"] for e in high_risk_epics)

        # Classify complexity
        if custom_percentage < self.CUSTOM_COMPLEXITY_THRESHOLDS["low"] * 100:
            complexity_level = "low"
        elif custom_percentage < self.CUSTOM_COMPLEXITY_THRESHOLDS["medium"] * 100:
            complexity_level = "medium"
        else:
            complexity_level = "high"

        return {
            "project_key": project_key,
            "total_hours": round(total_hours, 1),
            "custom_hours": round(custom_hours, 1),
            "custom_percentage": round(custom_percentage, 1),
            "complexity_level": complexity_level,
            "custom_epic_count": len(custom_epics),
            "high_risk_epic_count": len(high_risk_epics),
            "high_risk_hours": round(high_risk_hours, 1),
            "custom_epics": sorted(
                custom_epics, key=lambda x: x["hours"], reverse=True
            ),
        }

    def analyze_all_projects(self) -> List[Dict]:
        """Analyze complexity for all projects."""
        projects = self.session.query(EpicHours.project_key).distinct().all()
        results = []

        for (project_key,) in projects:
            results.append(self.calculate_complexity_score(project_key))

        return sorted(results, key=lambda x: x["custom_percentage"], reverse=True)

    def print_analysis(self, analysis: List[Dict], project_filter: str = None):
        """Pretty print analysis results."""
        if project_filter:
            analysis = [a for a in analysis if a["project_key"] == project_filter]

        print("\n" + "=" * 100)
        print("CUSTOM FEATURES & COMPLEXITY ANALYSIS")
        print("=" * 100)

        # Overall summary
        total_projects = len(analysis)
        avg_custom_pct = (
            sum(a["custom_percentage"] for a in analysis) / total_projects
            if total_projects > 0
            else 0
        )

        print(f"\n{'SUMMARY':<40} {'Value'}")
        print("-" * 100)
        print(f"{'Total Projects Analyzed:':<40} {total_projects}")
        print(f"{'Average Custom Work:':<40} {avg_custom_pct:.1f}%")

        by_complexity = defaultdict(int)
        for a in analysis:
            by_complexity[a["complexity_level"]] += 1

        print(f"{'Low Complexity Projects:':<40} {by_complexity['low']}")
        print(f"{'Medium Complexity Projects:':<40} {by_complexity['medium']}")
        print(f"{'High Complexity Projects:':<40} {by_complexity['high']}")

        # Per-project details
        for project in analysis:
            print(f"\n{'=' * 100}")
            print(
                f"PROJECT: {project['project_key']} (Complexity: {project['complexity_level'].upper()})"
            )
            print(f"{'=' * 100}")
            print(f"{'Total Hours:':<40} {project['total_hours']:.1f}h")
            print(
                f"{'Custom Hours:':<40} {project['custom_hours']:.1f}h ({project['custom_percentage']:.1f}%)"
            )
            print(f"{'Custom Epics:':<40} {project['custom_epic_count']}")
            print(
                f"{'High-Risk Custom Epics (>50h):':<40} {project['high_risk_epic_count']} ({project['high_risk_hours']:.1f}h)"
            )

            if project["custom_epics"]:
                print(
                    f"\n{'CUSTOM EPIC BREAKDOWN':<50} {'Hours':<10} {'Risk':<10} {'Reason'}"
                )
                print("-" * 100)

                for epic in project["custom_epics"][:10]:  # Top 10
                    risk = "HIGH RISK" if epic["is_high_risk"] else "Normal"
                    reason = (
                        "Unique"
                        if epic["reason"] == "unique_to_project"
                        else "Not in baseline"
                    )
                    print(
                        f"{epic['epic_summary'][:48]:<50} {epic['hours']:<10.1f} {risk:<10} {reason}"
                    )

                if len(project["custom_epics"]) > 10:
                    print(
                        f"\n... and {len(project['custom_epics']) - 10} more custom epics"
                    )

        print("=" * 100 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze custom features and project complexity"
    )
    parser.add_argument("--project", type=str, help="Filter to specific project")

    args = parser.parse_args()

    analyzer = CustomFeatureAnalyzer()
    logger.info("Analyzing custom features across all projects...")

    analysis = analyzer.analyze_all_projects()
    analyzer.print_analysis(analysis, project_filter=args.project)

    logger.info("Analysis complete!")


if __name__ == "__main__":
    main()
