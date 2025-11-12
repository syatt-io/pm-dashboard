#!/usr/bin/env python3
"""
Analyze project composition - breakdown by epic category.

This script categorizes epics into types (PM, Design, Development, Integration, etc.)
and shows the hour distribution across categories to identify project composition patterns.

Usage:
    python scripts/analyze_project_composition.py
    python scripts/analyze_project_composition.py --project COOP
"""

import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProjectCompositionAnalyzer:
    """Analyze project composition by epic category."""

    # Category classification rules (keyword matching)
    CATEGORIES = {
        "PM/Oversight": [
            "project oversight",
            "project management",
            "support",
            "oversight",
        ],
        "Design/UX": ["design", "ux", "ui", "prototype", "ideation", "style guide"],
        "Content/Modules": ["content sections", "components", "modules", "sections"],
        "Navigation": ["header", "footer", "mega menu", "menu", "navigation"],
        "Product Pages": ["pdp", "product detail", "plp", "product list", "quick view"],
        "Search/Browse": ["search", "filter", "browse", "catalog"],
        "Cart/Checkout": ["cart", "checkout", "payment", "shipping"],
        "Account/Auth": ["account", "login", "auth", "user", "profile"],
        "Integration": ["integration", "api", "migration", "import", "export", "sync"],
        "Infrastructure": [
            "globals",
            "analytics",
            "seo",
            "ci",
            "deployment",
            "testing",
            "uat",
        ],
        "Custom Features": [
            "scholarship",
            "configurator",
            "academic",
            "bopis",
            "registry",
            "wishlist",
            "donation",
            "bulk",
            "custom",
        ],
    }

    def __init__(self):
        self.session = get_session()

    def categorize_epic(self, epic_summary: str) -> str:
        """Categorize an epic based on its summary."""
        if not epic_summary:
            return "Other"

        normalized = epic_summary.lower()

        # Check each category's keywords
        for category, keywords in self.CATEGORIES.items():
            for keyword in keywords:
                if keyword in normalized:
                    return category

        return "Other"

    def analyze_project_composition(self, project_key: str) -> Dict:
        """Analyze composition of a specific project."""
        results = (
            self.session.query(
                EpicHours.epic_summary, func.sum(EpicHours.hours).label("total_hours")
            )
            .filter(EpicHours.project_key == project_key)
            .group_by(EpicHours.epic_summary)
            .all()
        )

        if not results:
            return None

        # Categorize and sum hours
        category_hours = defaultdict(float)
        category_epics = defaultdict(list)
        total_hours = 0

        for result in results:
            if not result.epic_summary:
                continue

            category = self.categorize_epic(result.epic_summary)
            category_hours[category] += result.total_hours
            category_epics[category].append((result.epic_summary, result.total_hours))
            total_hours += result.total_hours

        # Calculate percentages and sort
        composition = []
        for category in sorted(
            category_hours.keys(), key=lambda x: category_hours[x], reverse=True
        ):
            hours = category_hours[category]
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0

            # Sort epics within category by hours
            epics = sorted(category_epics[category], key=lambda x: x[1], reverse=True)

            composition.append(
                {
                    "category": category,
                    "hours": round(hours, 1),
                    "percentage": round(percentage, 1),
                    "epic_count": len(epics),
                    "top_epics": epics[:5],  # Top 5 epics in this category
                }
            )

        # Calculate PM overhead actual vs typical
        pm_hours = category_hours.get("PM/Oversight", 0)
        pm_percentage = (pm_hours / total_hours * 100) if total_hours > 0 else 0

        return {
            "project_key": project_key,
            "total_hours": round(total_hours, 1),
            "pm_hours": round(pm_hours, 1),
            "pm_percentage": round(pm_percentage, 1),
            "pm_assessment": self._assess_pm_overhead(pm_percentage),
            "composition": composition,
        }

    def _assess_pm_overhead(self, pm_percentage: float) -> str:
        """Assess if PM overhead is typical, high, or low."""
        if pm_percentage < 20:
            return "Low (< 20%)"
        elif pm_percentage < 30:
            return "Typical (20-30%)"
        elif pm_percentage < 40:
            return "High (30-40%)"
        else:
            return "Very High (> 40%)"

    def analyze_all_projects(self) -> List[Dict]:
        """Analyze composition for all projects."""
        projects = self.session.query(EpicHours.project_key).distinct().all()
        results = []

        for (project_key,) in projects:
            composition = self.analyze_project_composition(project_key)
            if composition:
                results.append(composition)

        return sorted(results, key=lambda x: x["total_hours"], reverse=True)

    def calculate_category_averages(self, analyses: List[Dict]) -> Dict[str, float]:
        """Calculate average percentage for each category across all projects."""
        category_totals = defaultdict(float)
        category_counts = defaultdict(int)

        for analysis in analyses:
            for cat_info in analysis["composition"]:
                category_totals[cat_info["category"]] += cat_info["percentage"]
                category_counts[cat_info["category"]] += 1

        averages = {}
        for category in category_totals:
            averages[category] = round(
                category_totals[category] / category_counts[category], 1
            )

        return dict(sorted(averages.items(), key=lambda x: x[1], reverse=True))

    def print_analysis(self, analyses: List[Dict], project_filter: str = None):
        """Pretty print composition analysis."""
        if project_filter:
            analyses = [a for a in analyses if a["project_key"] == project_filter]

        print("\n" + "=" * 100)
        print("PROJECT COMPOSITION ANALYSIS")
        print("=" * 100)

        # Overall statistics
        total_projects = len(analyses)
        avg_pm = (
            sum(a["pm_percentage"] for a in analyses) / total_projects
            if total_projects > 0
            else 0
        )

        print(f"\n{'SUMMARY STATISTICS':<40} {'Value'}")
        print("-" * 100)
        print(f"{'Total Projects Analyzed:':<40} {total_projects}")
        print(f"{'Average PM Overhead:':<40} {avg_pm:.1f}%")

        # Category averages across all projects
        if not project_filter:
            category_averages = self.calculate_category_averages(analyses)

            print(f"\n{'AVERAGE CATEGORY DISTRIBUTION':<40} {'% of Project'}")
            print("-" * 100)
            for category, avg_pct in category_averages.items():
                print(f"{category:<40} {avg_pct:.1f}%")

        # Per-project details
        for analysis in analyses:
            print(f"\n{'=' * 100}")
            print(f"PROJECT: {analysis['project_key']}")
            print(f"{'=' * 100}")
            print(f"{'Total Hours:':<40} {analysis['total_hours']:.1f}h")
            print(
                f"{'PM Overhead:':<40} {analysis['pm_hours']:.1f}h ({analysis['pm_percentage']:.1f}%)"
            )
            print(f"{'PM Assessment:':<40} {analysis['pm_assessment']}")

            print(
                f"\n{'COMPOSITION BREAKDOWN':<30} {'Hours':<12} {'% of Total':<12} {'Epic Count'}"
            )
            print("-" * 100)

            for cat_info in analysis["composition"]:
                print(
                    f"{cat_info['category']:<30} {cat_info['hours']:<12.1f} {cat_info['percentage']:<12.1f}% {cat_info['epic_count']}"
                )

                # Show top epics in each category
                if cat_info["top_epics"]:
                    for epic_name, epic_hours in cat_info["top_epics"][:3]:
                        epic_pct = epic_hours / analysis["total_hours"] * 100
                        print(f"{'':30}   └─ {epic_name[:50]:<50} ({epic_pct:.1f}%)")

        print("=" * 100 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze project composition by epic category"
    )
    parser.add_argument("--project", type=str, help="Filter to specific project")

    args = parser.parse_args()

    analyzer = ProjectCompositionAnalyzer()
    logger.info("Analyzing project composition across all projects...")

    analyses = analyzer.analyze_all_projects()
    analyzer.print_analysis(analyses, project_filter=args.project)

    logger.info("Analysis complete!")


if __name__ == "__main__":
    main()
