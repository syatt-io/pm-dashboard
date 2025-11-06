#!/usr/bin/env python3
"""
Forecast project hours and timeline based on epic list.

This script estimates project hours by matching epics against historical baselines,
applies PM overhead, and generates month-by-month burn rate projections.

Usage:
    python scripts/forecast_project.py --epics "Header,Footer,Cart,PDP,Search"
    python scripts/forecast_project.py --epics-file epics.txt
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicBaseline
from src.utils.database import get_session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProjectForecaster:
    """Project forecasting engine using historical baselines."""

    # Project size tiers (based on historical data)
    SIZE_TIERS = {
        'small': {'threshold': 900, 'burn_rate': 118.65, 'months': 8},
        'medium': {'threshold': 1400, 'burn_rate': 87.52, 'months': 12},
        'large': {'threshold': float('inf'), 'burn_rate': 136.64, 'months': 12}
    }

    PM_OVERHEAD = 0.25  # 25% overhead for project management

    def __init__(self):
        self.session = get_session()
        self.baselines = self._load_baselines()

    def _load_baselines(self) -> Dict[str, EpicBaseline]:
        """Load all epic baselines into memory."""
        baselines = {}
        for baseline in self.session.query(EpicBaseline).all():
            baselines[baseline.epic_category] = baseline
        logger.info(f"Loaded {len(baselines)} epic baselines")
        return baselines

    def normalize_epic_name(self, epic: str) -> str:
        """Normalize epic names for matching."""
        return epic.strip().lower()

    def find_baseline(self, epic_name: str) -> EpicBaseline:
        """Find baseline for an epic (exact or fuzzy match)."""
        normalized = self.normalize_epic_name(epic_name)

        # Try exact match
        if normalized in self.baselines:
            return self.baselines[normalized]

        # Try fuzzy match (contains)
        for key, baseline in self.baselines.items():
            if normalized in key or key in normalized:
                logger.warning(f"Fuzzy matched '{epic_name}' to '{baseline.epic_category}'")
                return baseline

        return None

    def get_epic_estimate(self, epic_name: str) -> Dict:
        """Get estimated hours for an epic with risk assessment."""
        baseline = self.find_baseline(epic_name)

        if not baseline:
            # Custom epic - no baseline available
            return {
                'epic': epic_name,
                'hours': None,
                'variance_level': 'custom',
                'confidence': 'low',
                'note': 'No historical data - requires custom scoping'
            }

        # Use recommended estimate based on variance level
        hours = baseline.get_recommended_estimate()

        return {
            'epic': epic_name,
            'matched_category': baseline.epic_category,
            'hours': hours,
            'variance_level': baseline.variance_level,
            'confidence': 'high' if baseline.variance_level == 'low' else 'medium',
            'range': f"{baseline.min_hours:.1f}-{baseline.max_hours:.1f}h",
            'project_count': baseline.project_count
        }

    def classify_project_size(self, total_hours: float) -> str:
        """Classify project as small/medium/large."""
        if total_hours < self.SIZE_TIERS['small']['threshold']:
            return 'small'
        elif total_hours < self.SIZE_TIERS['medium']['threshold']:
            return 'medium'
        else:
            return 'large'

    def generate_burn_rate_schedule(self, total_hours: float, project_size: str) -> List[Dict]:
        """Generate month-by-month burn rate projection."""
        tier = self.SIZE_TIERS[project_size]
        months = tier['months']

        # Distribution pattern: heavier in early/mid months, lighter at end
        # Early phase: 130%, Mid phase: 100%, Late phase: 70%
        schedule = []
        total_weight = 0
        weights = []

        for month in range(1, months + 1):
            if month <= months * 0.33:  # Early phase
                weight = 1.3
            elif month <= months * 0.67:  # Mid phase
                weight = 1.0
            else:  # Late phase
                weight = 0.7

            weights.append(weight)
            total_weight += weight

        # Distribute hours proportionally
        cumulative = 0
        for month, weight in enumerate(weights, 1):
            month_hours = (weight / total_weight) * total_hours
            cumulative += month_hours

            schedule.append({
                'month': month,
                'hours': round(month_hours, 1),
                'cumulative': round(cumulative, 1)
            })

        return schedule

    def forecast(self, epic_list: List[str]) -> Dict:
        """
        Generate complete project forecast.

        Returns:
            Dict with hours breakdown, timeline, burn rate, and risk assessment
        """
        logger.info(f"Forecasting project with {len(epic_list)} epics...")

        # Get estimates for each epic
        epic_estimates = []
        dev_hours = 0
        custom_epics = []
        high_risk_epics = []

        for epic in epic_list:
            estimate = self.get_epic_estimate(epic)
            epic_estimates.append(estimate)

            if estimate['hours'] is None:
                custom_epics.append(epic)
            else:
                dev_hours += estimate['hours']

                if estimate['variance_level'] == 'high':
                    high_risk_epics.append(epic)

        # Add PM overhead
        pm_hours = dev_hours * self.PM_OVERHEAD
        total_hours = dev_hours + pm_hours

        # Classify project size and get burn rate
        project_size = self.classify_project_size(total_hours)
        burn_schedule = self.generate_burn_rate_schedule(total_hours, project_size)

        # Calculate confidence interval (±20% for medium confidence, ±30% for low)
        if custom_epics or len(high_risk_epics) > len(epic_list) * 0.3:
            confidence = 'low'
            margin = 0.30
        elif high_risk_epics:
            confidence = 'medium'
            margin = 0.20
        else:
            confidence = 'high'
            margin = 0.10

        return {
            'summary': {
                'total_epics': len(epic_list),
                'matched_epics': len(epic_list) - len(custom_epics),
                'custom_epics': len(custom_epics),
                'development_hours': round(dev_hours, 1),
                'pm_overhead_hours': round(pm_hours, 1),
                'total_hours': round(total_hours, 1),
                'confidence': confidence,
                'range_low': round(total_hours * (1 - margin), 1),
                'range_high': round(total_hours * (1 + margin), 1)
            },
            'timeline': {
                'project_size': project_size,
                'estimated_months': self.SIZE_TIERS[project_size]['months'],
                'avg_burn_rate': round(total_hours / self.SIZE_TIERS[project_size]['months'], 1)
            },
            'burn_schedule': burn_schedule,
            'epic_breakdown': epic_estimates,
            'risks': {
                'custom_epics': custom_epics,
                'high_risk_epics': high_risk_epics
            }
        }

    def print_forecast(self, forecast: Dict):
        """Pretty print forecast results."""
        summary = forecast['summary']
        timeline = forecast['timeline']

        print("\n" + "=" * 80)
        print("PROJECT FORECAST")
        print("=" * 80)

        print(f"\n{'HOURS ESTIMATE':<40} {'Value'}")
        print("-" * 80)
        print(f"{'Development Hours:':<40} {summary['development_hours']:.1f}h")
        print(f"{'PM Overhead (25%):':<40} {summary['pm_overhead_hours']:.1f}h")
        print(f"{'TOTAL HOURS:':<40} {summary['total_hours']:.1f}h")
        print(f"{'Confidence Interval:':<40} {summary['range_low']:.1f}h - {summary['range_high']:.1f}h")
        print(f"{'Confidence Level:':<40} {summary['confidence'].upper()}")

        print(f"\n{'TIMELINE':<40} {'Value'}")
        print("-" * 80)
        print(f"{'Project Size:':<40} {timeline['project_size'].upper()}")
        print(f"{'Estimated Duration:':<40} {timeline['estimated_months']} months")
        print(f"{'Average Burn Rate:':<40} {timeline['avg_burn_rate']:.1f}h/month")

        print(f"\n{'EPIC BREAKDOWN':<30} {'Hours':<10} {'Confidence':<12} {'Variance'}")
        print("-" * 80)
        for epic in forecast['epic_breakdown']:
            hours = f"{epic['hours']:.1f}h" if epic['hours'] else "TBD"
            print(f"{epic['epic']:<30} {hours:<10} {epic['confidence']:<12} {epic['variance_level']}")

        if forecast['risks']['custom_epics']:
            print(f"\n⚠️  CUSTOM EPICS (require detailed scoping):")
            for epic in forecast['risks']['custom_epics']:
                print(f"   - {epic}")

        if forecast['risks']['high_risk_epics']:
            print(f"\n⚠️  HIGH RISK EPICS (high variance - add buffer):")
            for epic in forecast['risks']['high_risk_epics']:
                print(f"   - {epic}")

        print(f"\n{'BURN RATE SCHEDULE':<15} {'Hours':<10} {'Cumulative'}")
        print("-" * 80)
        for month in forecast['burn_schedule']:
            print(f"Month {month['month']:<10} {month['hours']:<10.1f} {month['cumulative']:.1f}h")

        print("=" * 80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Forecast project hours and timeline')
    parser.add_argument('--epics', type=str, help='Comma-separated list of epic names')
    parser.add_argument('--epics-file', type=Path, help='File containing epic names (one per line)')

    args = parser.parse_args()

    if not args.epics and not args.epics_file:
        parser.error("Either --epics or --epics-file must be provided")

    # Parse epic list
    if args.epics:
        epic_list = [e.strip() for e in args.epics.split(',')]
    else:
        with open(args.epics_file) as f:
            epic_list = [line.strip() for line in f if line.strip()]

    # Generate forecast
    forecaster = ProjectForecaster()
    forecast = forecaster.forecast(epic_list)
    forecaster.print_forecast(forecast)


if __name__ == "__main__":
    main()
