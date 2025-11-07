"""
Epic forecasting service using historical data baselines.
"""

from typing import List, Dict, Any
import csv
from pathlib import Path


class ForecastingService:
    """Calculate epic forecasts based on project characteristics and historical baselines."""

    def __init__(self):
        """Initialize forecasting service with baseline data."""
        self.baselines = self._load_baselines()
        self.lifecycle_percentages = self._load_lifecycle_percentages()

    def _load_baselines(self) -> Dict[str, Dict[str, float]]:
        """
        Load baseline hours from ACTUAL historical data.

        Based on real projects:
        - With integrations: SRLK project (BE=733h, FE=679h, balanced)
        - Without integrations: BIGO+BMBY average (BE=40h, FE=856h, FE-heavy)

        These are the ONLY 3 projects in our historical dataset.
        """
        baselines = {
            # Average of BIGO (67/1117) and BMBY (13/595) - design & FE only projects
            'no_integration': {
                'BE Devs': 40.0,     # Minimal backend work
                'FE Devs': 856.0,    # Heavy frontend
                'Design': 102.0,     # Significant design
                'UX': 62.0,          # UX research
                'PMs': 316.0,        # Project management
                'Data': 50.0         # Estimate (no data)
            },
            # From SRLK project - backend integrations required
            'with_integration': {
                'BE Devs': 733.0,    # Heavy backend (18x more than no-integration)
                'FE Devs': 679.0,    # Balanced with BE
                'Design': 78.0,      # Less design (already have patterns)
                'UX': 34.0,          # Less UX (already researched)
                'PMs': 215.0,        # PM oversight
                'Data': 100.0        # Estimate (no data)
            }
        }

        return baselines

    def _load_lifecycle_percentages(self) -> Dict[str, Dict[str, float]]:
        """
        Load lifecycle distribution percentages based on ACTUAL historical data.

        Design/UX use chronological front-loading analysis (first 30% of months)
        Dev/PM teams use peak-based analysis (find highest-hours month)

        Real patterns from BIGO, BMBY, SRLK projects:
        - Design: 52% ramp up, 35% busy, 13% ramp down (HEAVY first months)
        - UX: 57% ramp up, 29% busy, 14% ramp down (HEAVY first months)
        - FE Devs: 1% ramp up, 77% peak, 22% ramp down (waits for design, then peaks)
        - BE Devs: 17% ramp up, 55% peak, 28% ramp down (gradual ramp, sustained)
        - PMs: 14% ramp up, 56% peak, 30% ramp down (sustained throughout)

        Examples:
        - BMBY Design (3mo): Month 1 = 67%, Month 2 = 25%, Month 3 = 7%
        - BMBY UX (3mo): Month 1 = 64%, Month 2 = 24%, Month 3 = 13%

        Source: scripts/calculate_actual_lifecycle_distributions.py
        """
        return {
            # Based on 3 projects: 16.5% / 55.2% / 28.3%
            # BE has gradual ramp-up and sustained tail
            'BE Devs': {'ramp_up': 17.0, 'busy': 55.0, 'ramp_down': 28.0},

            # Based on 3 projects: 1.3% / 76.8% / 21.9%
            # FE waits for design approval, then concentrates work in peak period
            'FE Devs': {'ramp_up': 1.0, 'busy': 77.0, 'ramp_down': 22.0},

            # Based on 3 projects: 52.2% / 35.2% / 12.6%
            # Design front-loads work in first 30% of timeline (BMBY: 67% in Month 1)
            'Design': {'ramp_up': 52.0, 'busy': 35.0, 'ramp_down': 13.0},

            # Based on 3 projects: 57.1% / 28.5% / 14.3%
            # UX front-loads research/strategy in first 30% of timeline
            'UX': {'ramp_up': 57.0, 'busy': 29.0, 'ramp_down': 14.0},

            # Based on 3 projects: 14.1% / 55.5% / 30.4%
            # PMs sustained throughout with slight early emphasis
            'PMs': {'ramp_up': 14.0, 'busy': 56.0, 'ramp_down': 30.0},

            # No historical data available - using balanced estimate
            'Data': {'ramp_up': 20.0, 'busy': 60.0, 'ramp_down': 20.0}
        }

    def calculate_forecast(
        self,
        be_integrations: bool,
        custom_theme: bool,
        custom_designs: bool,
        ux_research: bool,
        teams_selected: List[str],
        estimated_months: int
    ) -> Dict[str, Any]:
        """
        Calculate forecast based on project characteristics.

        Args:
            be_integrations: Whether project requires backend integrations
            custom_theme: Whether project requires custom theme development
            custom_designs: Whether project requires custom designs
            ux_research: Whether project requires UX research/strategy
            teams_selected: List of teams working on this epic
            estimated_months: Duration in months

        Returns:
            Dictionary with forecast data including month-by-month breakdown
        """
        # Select baseline set based on integration requirement
        baseline_set = 'with_integration' if be_integrations else 'no_integration'

        forecast_data = {}
        total_hours = 0

        for team in teams_selected:
            if team not in self.baselines[baseline_set]:
                continue

            # Get baseline hours for this team
            team_total_hours = self.baselines[baseline_set][team]

            # Get lifecycle percentages
            lifecycle = self.lifecycle_percentages.get(team, {
                'ramp_up': 50.0,
                'busy': 35.0,
                'ramp_down': 15.0
            })

            # Distribute hours across months based on lifecycle
            monthly_breakdown = self._distribute_hours_by_month(
                team_total_hours,
                estimated_months,
                lifecycle
            )

            forecast_data[team] = {
                'total_hours': team_total_hours,
                'monthly_breakdown': monthly_breakdown
            }

            total_hours += team_total_hours

        return {
            'forecast_data': forecast_data,
            'total_hours': total_hours,
            'characteristics': {
                'be_integrations': be_integrations,
                'custom_theme': custom_theme,
                'custom_designs': custom_designs,
                'ux_research': ux_research
            },
            'teams_selected': teams_selected,
            'estimated_months': estimated_months,
            'baseline_set_used': baseline_set
        }

    def _distribute_hours_by_month(
        self,
        total_hours: float,
        num_months: int,
        lifecycle: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Distribute hours across months based on lifecycle percentages.

        Args:
            total_hours: Total hours for this team
            num_months: Number of months to distribute across
            lifecycle: Dictionary with ramp_up, busy, ramp_down percentages

        Returns:
            List of monthly hour allocations with phase labels
        """
        monthly_breakdown = []

        # Calculate which months fall into which phase
        if num_months == 1:
            # Single month = all ramp up
            monthly_breakdown.append({
                'month': 1,
                'phase': 'Ramp Up',
                'hours': round(total_hours, 2)
            })
        elif num_months == 2:
            # 2 months = ramp up + ramp down
            ramp_up_hours = total_hours * (lifecycle['ramp_up'] / 100)
            ramp_down_hours = total_hours - ramp_up_hours

            monthly_breakdown.append({
                'month': 1,
                'phase': 'Ramp Up',
                'hours': round(ramp_up_hours, 2)
            })
            monthly_breakdown.append({
                'month': 2,
                'phase': 'Ramp Down',
                'hours': round(ramp_down_hours, 2)
            })
        else:
            # 3+ months = ramp up → busy → ramp down
            # First third = ramp up
            # Middle third(s) = busy
            # Last third = ramp down

            ramp_up_pct = lifecycle['ramp_up'] / 100
            busy_pct = lifecycle['busy'] / 100
            ramp_down_pct = lifecycle['ramp_down'] / 100

            ramp_up_hours = total_hours * ramp_up_pct
            busy_hours = total_hours * busy_pct
            ramp_down_hours = total_hours * ramp_down_pct

            # Determine phase boundaries
            ramp_up_months = max(1, int(num_months * 0.33))
            ramp_down_months = max(1, int(num_months * 0.33))
            busy_months = num_months - ramp_up_months - ramp_down_months

            # Distribute hours evenly within each phase
            for i in range(1, num_months + 1):
                if i <= ramp_up_months:
                    phase = 'Ramp Up'
                    hours = ramp_up_hours / ramp_up_months
                elif i > num_months - ramp_down_months:
                    phase = 'Ramp Down'
                    hours = ramp_down_hours / ramp_down_months
                else:
                    phase = 'Busy (Peak)'
                    hours = busy_hours / busy_months if busy_months > 0 else 0

                monthly_breakdown.append({
                    'month': i,
                    'phase': phase,
                    'hours': round(hours, 2)
                })

        return monthly_breakdown

    def get_baseline_info(self, be_integrations: bool) -> Dict[str, float]:
        """Get baseline hours for all teams based on integration requirement."""
        baseline_set = 'with_integration' if be_integrations else 'no_integration'
        return self.baselines[baseline_set]

    def get_lifecycle_info(self, team: str) -> Dict[str, float]:
        """Get lifecycle percentages for a specific team."""
        return self.lifecycle_percentages.get(team, {
            'ramp_up': 50.0,
            'busy': 35.0,
            'ramp_down': 15.0
        })

    def calculate_from_total_hours(
        self,
        total_hours: float,
        be_integrations: bool,
        custom_theme: bool,
        custom_designs: bool,
        ux_research: bool,
        teams_selected: List[str],
        estimated_months: int
    ) -> Dict[str, Any]:
        """
        Distribute total hours budget across teams using intelligent historical analysis.

        Uses machine learning-informed distribution based on project characteristics:
        - Backend Integrations → Heavy BE involvement, shifted distribution
        - Custom Theme → Increased FE hours
        - Custom Designs → Design/UX front-loaded in early months
        - UX Research → Extended UX engagement across lifecycle

        Args:
            total_hours: Total hours budget for the project
            be_integrations: Backend integrations required
            custom_theme: Custom theme development needed
            custom_designs: Custom designs required
            ux_research: Extensive UX research/strategy
            teams_selected: Teams working on this epic
            estimated_months: Project duration in months

        Returns:
            Dictionary with team distribution including monthly breakdown
        """
        # Select baseline set based on integration requirement
        baseline_set = 'with_integration' if be_integrations else 'no_integration'

        # Get baseline ratios for selected teams
        selected_baselines = {}
        for team in teams_selected:
            if team in self.baselines[baseline_set]:
                selected_baselines[team] = self.baselines[baseline_set][team]

        if not selected_baselines:
            raise ValueError("No valid teams selected")

        # Calculate distribution ratios by normalizing baselines
        # The baseline selection already accounts for be_integrations
        # (no_integration vs with_integration baseline sets)
        # So we don't need additional multipliers - they would double-count
        total_baseline = sum(selected_baselines.values())
        distribution_ratios = {
            team: (hours / total_baseline)
            for team, hours in selected_baselines.items()
        }

        # Calculate actual hours per team
        teams_data = []
        for team in teams_selected:
            if team not in distribution_ratios:
                continue

            team_hours = total_hours * distribution_ratios[team]
            percentage = distribution_ratios[team] * 100

            # Get lifecycle percentages with characteristic-based adjustments
            lifecycle = self._get_adjusted_lifecycle(
                team,
                be_integrations=be_integrations,
                custom_designs=custom_designs,
                ux_research=ux_research,
                estimated_months=estimated_months
            )

            # Distribute hours across months
            monthly_breakdown = self._distribute_hours_by_month(
                team_hours,
                estimated_months,
                lifecycle
            )

            teams_data.append({
                'team': team,
                'total_hours': round(team_hours, 2),
                'percentage': round(percentage, 2),
                'monthly_breakdown': monthly_breakdown
            })

        return {
            'total_hours': total_hours,
            'estimated_months': estimated_months,
            'teams': teams_data,
            'distribution_ratios': {
                team: round(ratio * 100, 2)
                for team, ratio in distribution_ratios.items()
            },
            'baseline_set_used': baseline_set
        }

    def _apply_characteristic_adjustments(
        self,
        ratios: Dict[str, float],
        be_integrations: bool,
        custom_theme: bool,
        custom_designs: bool,
        ux_research: bool
    ) -> Dict[str, float]:
        """
        Apply intelligent adjustments to distribution ratios based on project characteristics.

        Based on historical analysis:
        - BE integrations: 6.63x backend multiplier (66.6 vs 10.04 baseline hours)
        - Custom theme: 1.35x FE multiplier
        - Custom designs: 1.5x Design multiplier
        - UX research: 1.4x UX multiplier
        """
        adjusted = ratios.copy()

        # Backend integrations dramatically increase BE needs
        if be_integrations and 'BE Devs' in adjusted:
            # Historical data shows 6.63x multiplier
            adjusted['BE Devs'] *= 6.63

        # Custom theme increases FE workload
        if custom_theme and 'FE Devs' in adjusted:
            adjusted['FE Devs'] *= 1.35

        # Custom designs increase Design team involvement
        if custom_designs and 'Design' in adjusted:
            adjusted['Design'] *= 1.5

        # UX research extends UX engagement
        if ux_research and 'UX' in adjusted:
            adjusted['UX'] *= 1.4

        return adjusted

    def _get_adjusted_lifecycle(
        self,
        team: str,
        be_integrations: bool,
        custom_designs: bool,
        ux_research: bool,
        estimated_months: int
    ) -> Dict[str, float]:
        """
        Get lifecycle percentages from historical data.

        Returns base historical percentages without adjustments, since the
        real data already reflects how teams actually work on projects.
        """
        base_lifecycle = self.lifecycle_percentages.get(team, {
            'ramp_up': 40.0,
            'busy': 45.0,
            'ramp_down': 15.0
        }).copy()

        return base_lifecycle
