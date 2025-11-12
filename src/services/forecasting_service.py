"""
Epic forecasting service using historical data baselines.
"""

from typing import List, Dict, Any
import csv
import warnings
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
            "no_integration": {
                "BE Devs": 40.0,  # Minimal backend work
                "FE Devs": 856.0,  # Heavy frontend
                "Design": 102.0,  # Significant design
                "UX": 62.0,  # UX research
                "PMs": 316.0,  # Project management
                "Data": 50.0,  # Estimate (no data)
            },
            # From SRLK project - backend integrations required
            "with_integration": {
                "BE Devs": 733.0,  # Heavy backend (18x more than no-integration)
                "FE Devs": 679.0,  # Balanced with BE
                "Design": 78.0,  # Less design (already have patterns)
                "UX": 34.0,  # Less UX (already researched)
                "PMs": 215.0,  # PM oversight
                "Data": 100.0,  # Estimate (no data)
            },
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
            "BE Devs": {"ramp_up": 17.0, "busy": 55.0, "ramp_down": 28.0},
            # Based on 3 projects: 1.3% / 76.8% / 21.9%
            # FE waits for design approval, then concentrates work in peak period
            "FE Devs": {"ramp_up": 1.0, "busy": 77.0, "ramp_down": 22.0},
            # Based on real data: 70-80% of ALL Design work done in first 2 months
            # Heavily front-loaded - most design completed early, minimal work later
            "Design": {"ramp_up": 80.0, "busy": 15.0, "ramp_down": 5.0},
            # Based on 3 projects: 57.1% / 28.5% / 14.3%
            # UX front-loads research/strategy in first 30% of timeline
            "UX": {"ramp_up": 57.0, "busy": 29.0, "ramp_down": 14.0},
            # Based on 3 projects: 14.1% / 55.5% / 30.4%
            # PMs sustained throughout with slight early emphasis
            "PMs": {"ramp_up": 14.0, "busy": 56.0, "ramp_down": 30.0},
            # No historical data available - using balanced estimate
            "Data": {"ramp_up": 20.0, "busy": 60.0, "ramp_down": 20.0},
        }

    def calculate_forecast(
        self,
        be_integrations: bool,
        custom_theme: bool,
        custom_designs: bool,
        ux_research: bool,
        teams_selected: List[str],
        estimated_months: int,
    ) -> Dict[str, Any]:
        """
        Calculate forecast based on project characteristics.

        .. deprecated::
            This method uses boolean characteristics and is deprecated.
            Use calculate_from_total_hours() instead, which supports full 1-5 scale
            granularity and provides more accurate forecasts.

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
        warnings.warn(
            "calculate_forecast() with boolean characteristics is deprecated. "
            "Use calculate_from_total_hours() with 1-5 scale characteristics for better accuracy.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Select baseline set based on integration requirement
        baseline_set = "with_integration" if be_integrations else "no_integration"

        forecast_data = {}
        total_hours = 0

        for team in teams_selected:
            if team not in self.baselines[baseline_set]:
                continue

            # Get baseline hours for this team
            team_total_hours = self.baselines[baseline_set][team]

            # Get lifecycle percentages
            lifecycle = self.lifecycle_percentages.get(
                team, {"ramp_up": 50.0, "busy": 35.0, "ramp_down": 15.0}
            )

            # Distribute hours across months based on lifecycle
            monthly_breakdown = self._distribute_hours_by_month(
                team_total_hours,
                estimated_months,
                lifecycle,
                team,  # Pass team name for Design/UX front-loading
            )

            forecast_data[team] = {
                "total_hours": team_total_hours,
                "monthly_breakdown": monthly_breakdown,
            }

            total_hours += team_total_hours

        return {
            "forecast_data": forecast_data,
            "total_hours": total_hours,
            "characteristics": {
                "be_integrations": be_integrations,
                "custom_theme": custom_theme,
                "custom_designs": custom_designs,
                "ux_research": ux_research,
            },
            "teams_selected": teams_selected,
            "estimated_months": estimated_months,
            "baseline_set_used": baseline_set,
        }

    def _distribute_hours_by_month(
        self,
        total_hours: float,
        num_months: int,
        lifecycle: Dict[str, float],
        team_name: str = "",
        start_date: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Distribute hours across months based on lifecycle percentages.

        For Design/UX teams with high ramp_up percentages (52%/57%), uses
        exponential front-loading to concentrate hours in first 1-2 months,
        matching real data patterns (BMBY: 67% Month 1, 25% Month 2, 7% Month 3).

        Args:
            total_hours: Total hours for this team
            num_months: Number of months to distribute across
            lifecycle: Dictionary with ramp_up, busy, ramp_down percentages
            team_name: Team name for special front-loading logic
            start_date: Optional start date (YYYY-MM-DD) for proration

        Returns:
            List of monthly hour allocations with phase labels
        """
        from datetime import datetime
        from calendar import monthrange

        # Calculate proration factors for first and last months
        first_month_factor = 1.0
        last_month_factor = 1.0

        if start_date and num_months > 1:
            try:
                start_dt = datetime.fromisoformat(start_date)
                start_day = start_dt.day

                # Calculate days available in first month
                days_in_start_month = monthrange(start_dt.year, start_dt.month)[1]
                days_available_first = days_in_start_month - start_day + 1
                first_month_factor = days_available_first / days_in_start_month

                # Calculate days available in last month
                # Last month ends when we run out of the project duration
                last_month = start_dt
                for _ in range(num_months - 1):
                    if last_month.month == 12:
                        last_month = last_month.replace(
                            year=last_month.year + 1, month=1
                        )
                    else:
                        last_month = last_month.replace(month=last_month.month + 1)

                # Last month ends on the same day as start (e.g., Jan 15 -> Jun 15)
                # So we need days from day 1 to start_day
                last_month_factor = (
                    start_day / monthrange(last_month.year, last_month.month)[1]
                )

            except (ValueError, AttributeError):
                # If date parsing fails, use full months
                pass

        monthly_breakdown = []

        # Calculate which months fall into which phase
        if num_months == 1:
            # Single month = all ramp up
            monthly_breakdown.append(
                {"month": 1, "phase": "Ramp Up", "hours": round(total_hours, 2)}
            )
        elif num_months == 2:
            # 2 months = ramp up + ramp down
            ramp_up_hours = total_hours * (lifecycle["ramp_up"] / 100)
            ramp_down_hours = total_hours - ramp_up_hours

            monthly_breakdown.append(
                {"month": 1, "phase": "Ramp Up", "hours": round(ramp_up_hours, 2)}
            )
            monthly_breakdown.append(
                {"month": 2, "phase": "Ramp Down", "hours": round(ramp_down_hours, 2)}
            )
        else:
            # 3+ months = ramp up → busy → ramp down
            ramp_up_pct = lifecycle["ramp_up"] / 100
            busy_pct = lifecycle["busy"] / 100
            ramp_down_pct = lifecycle["ramp_down"] / 100

            ramp_up_hours = total_hours * ramp_up_pct
            busy_hours = total_hours * busy_pct
            ramp_down_hours = total_hours * ramp_down_pct

            # DATA-DRIVEN TEMPORAL PATTERNS (based on real project analysis)
            # Design: 70-80% of ALL hours in first 2 months (EXTREMELY FRONT-LOADED)
            # UX: 47% first third (FRONT-LOADED)
            # FE Devs: 55% middle third (MID-PEAKED)
            # BE Devs: 45% middle, even distribution (EVEN)
            # PMs: 41% middle, even distribution (EVEN)

            # Determine temporal pattern for this team
            temporal_pattern = None
            if team_name == "Design":
                # Design is heavily front-loaded: 54% in first third
                temporal_pattern = "front_heavy"  # ~85-90% in first 2 months
            elif team_name == "UX":
                # UX is front-loaded: 47% in first third
                temporal_pattern = "front"  # ~70-75% in first third
            elif team_name == "FE Devs":
                # FE is mid-peaked: 55% in middle third
                temporal_pattern = "mid_peak"
            else:
                # BE Devs, PMs, Others: relatively even
                temporal_pattern = "even"

            # Determine phase boundaries
            ramp_up_months = max(1, int(num_months * 0.33))
            ramp_down_months = max(1, int(num_months * 0.33))
            busy_months = num_months - ramp_up_months - ramp_down_months

            # Distribute hours within each phase based on temporal pattern
            for i in range(1, num_months + 1):
                # Special Design handling: 64% in M1, 14.4% in M2 (total 78.4%)
                # This overrides phase boundaries to ensure extreme front-loading
                if temporal_pattern == "front_heavy":
                    if i == 1:
                        hours = total_hours * 0.64  # 64% of ALL hours in month 1
                        phase = "Ramp Up"
                    elif i == 2:
                        hours = total_hours * 0.144  # 14.4% of ALL hours in month 2
                        phase = "Ramp Up" if i <= ramp_up_months else "Busy (Peak)"
                    else:
                        # Remaining 21.6% distributed evenly across other months
                        remaining_hours = total_hours * 0.216
                        remaining_months = num_months - 2
                        hours = (
                            remaining_hours / remaining_months
                            if remaining_months > 0
                            else 0
                        )

                        if i <= ramp_up_months:
                            phase = "Ramp Up"
                        elif i > num_months - ramp_down_months:
                            phase = "Ramp Down"
                        else:
                            phase = "Busy (Peak)"

                elif i <= ramp_up_months:
                    phase = "Ramp Up"

                    if temporal_pattern == "front":
                        # UX: Strong front-loading (75% in first third)
                        if i == 1:
                            hours = ramp_up_hours * 0.55  # 55% in month 1
                        elif i == 2 and ramp_up_months >= 2:
                            hours = ramp_up_hours * 0.30  # 30% in month 2
                        else:
                            # Remaining 15% split across other ramp-up months
                            remaining_months = max(1, ramp_up_months - 2)
                            hours = (ramp_up_hours * 0.15) / remaining_months
                    else:
                        # Even distribution for BE Devs, PMs
                        hours = ramp_up_hours / ramp_up_months

                elif i > num_months - ramp_down_months:
                    phase = "Ramp Down"
                    hours = ramp_down_hours / ramp_down_months
                else:
                    phase = "Busy (Peak)"
                    if temporal_pattern == "mid_peak":
                        # FE Devs: Peak in middle months
                        middle_position = (
                            (i - ramp_up_months) / busy_months
                            if busy_months > 0
                            else 0.5
                        )
                        # Bell curve: peak at 1.5x average, edges at 0.7x average
                        peak_multiplier = 1.5 - 0.8 * abs(middle_position - 0.5)
                        hours = (
                            (busy_hours / busy_months) * peak_multiplier
                            if busy_months > 0
                            else 0
                        )
                    else:
                        hours = busy_hours / busy_months if busy_months > 0 else 0

                # Apply proration for first and last months
                if i == 1 and first_month_factor != 1.0:
                    hours = hours * first_month_factor
                elif i == num_months and last_month_factor != 1.0:
                    hours = hours * last_month_factor

                monthly_breakdown.append(
                    {"month": i, "phase": phase, "hours": round(hours, 2)}
                )

        return monthly_breakdown

    def get_baseline_info(self, be_integrations: bool) -> Dict[str, float]:
        """Get baseline hours for all teams based on integration requirement."""
        baseline_set = "with_integration" if be_integrations else "no_integration"
        return self.baselines[baseline_set]

    def get_lifecycle_info(self, team: str) -> Dict[str, float]:
        """Get lifecycle percentages for a specific team."""
        return self.lifecycle_percentages.get(
            team, {"ramp_up": 50.0, "busy": 35.0, "ramp_down": 15.0}
        )

    def calculate_from_total_hours(
        self,
        total_hours: float,
        be_integrations: int,  # Now accepts 1-5 slider value
        custom_theme: int,  # Now accepts 1-5 slider value
        custom_designs: int,  # Now accepts 1-5 slider value
        ux_research: int,  # Now accepts 1-5 slider value
        teams_selected: List[str],
        estimated_months: int,
        extensive_customizations: int = 1,  # NEW: 1-5 slider value (default: 1 = standard)
        project_oversight: int = 3,  # NEW: 1-5 slider value (default: 3 = typical)
        start_date: str = None,  # Optional start date (YYYY-MM-DD) for proration
    ) -> Dict[str, Any]:
        """
        Distribute total hours budget across teams using intelligent historical analysis.

        Uses smooth interpolation across full 1-5 scale for accurate forecasting:
        - Backend Integrations: Smooth blend between no_integration (1) and with_integration (5)
          baselines using formula: blend_factor = (value - 1) / 4.0
        - Extensive Customizations: Smooth BE Dev boost from 0% (1-2) to +30% (5)
          using formula: multiplier = 1.0 + max(0, (value - 2)) * 0.1
        - Custom Theme: FE hours scale smoothly from 1.0x (1) to 3.0x (5)
        - Custom Designs: Design/UX multiplier scales from 1.0x (1) to 4.0x (5)
        - UX Research: UX multiplier scales from 1.0x (1) to 4.0x (5)
        - Project Oversight: PM allocation adjusts around baseline (1=less, 3=typical, 5=high)

        All characteristics use continuous interpolation for nuanced forecasting.

        Args:
            total_hours: Total hours budget for the project
            be_integrations: Backend integrations complexity (1-5 slider)
            custom_theme: Custom theme development complexity (1-5 slider)
            custom_designs: Custom designs complexity (1-5 slider)
            ux_research: UX research/strategy complexity (1-5 slider)
            extensive_customizations: Extensive customizations complexity (1-5 slider)
            project_oversight: Project oversight needs (1-5 slider)
            teams_selected: Teams working on this epic
            estimated_months: Project duration in months

        Returns:
            Dictionary with team distribution including monthly breakdown
        """
        # NEW APPROACH: Blend between baseline sets based on slider values
        # Instead of binary threshold (≥3), use gradual interpolation (1-5 scale)

        # Calculate blend factor (0.0 = no_integration, 1.0 = with_integration)
        # Use the maximum of be_integrations and extensive_customizations
        max_integration_factor = max(be_integrations, extensive_customizations)
        # Map 1-5 slider to 0-1 blend: 1→0.0, 2→0.25, 3→0.5, 4→0.75, 5→1.0
        blend_factor = (max_integration_factor - 1) / 4.0

        # Get blended baseline hours for selected teams
        selected_baselines = {}
        for team in teams_selected:
            if (
                team in self.baselines["no_integration"]
                and team in self.baselines["with_integration"]
            ):
                no_int_hours = self.baselines["no_integration"][team]
                with_int_hours = self.baselines["with_integration"][team]
                # Linear interpolation between baselines
                blended_hours = (
                    no_int_hours + (with_int_hours - no_int_hours) * blend_factor
                )
                selected_baselines[team] = blended_hours
            elif team in self.baselines["no_integration"]:
                selected_baselines[team] = self.baselines["no_integration"][team]
            elif team in self.baselines["with_integration"]:
                selected_baselines[team] = self.baselines["with_integration"][team]

        if not selected_baselines:
            raise ValueError("No valid teams selected")

        # Apply AGGRESSIVE characteristic multipliers for visible redistribution
        # Since we're working with a fixed total_hours budget, these multipliers
        # dramatically shift the distribution percentages
        adjusted_baselines = selected_baselines.copy()

        # Custom Designs: DRAMATICALLY increase Design allocation (1→1.0x, 5→4.0x)
        # This ensures Design gets a much larger SHARE of the total budget
        if "Design" in adjusted_baselines:
            # Exponential scaling: 1→1.0x, 2→1.5x, 3→2.0x, 4→3.0x, 5→4.0x
            design_multiplier = 1.0 + (custom_designs - 1) * 0.75
            adjusted_baselines["Design"] *= design_multiplier

        # UX Research: DRAMATICALLY increase UX allocation (1→1.0x, 5→4.0x)
        if "UX" in adjusted_baselines:
            ux_multiplier = 1.0 + (ux_research - 1) * 0.75
            adjusted_baselines["UX"] *= ux_multiplier

        # Custom Theme: SIGNIFICANTLY increase FE allocation (1→1.0x, 5→3.0x)
        if "FE Devs" in adjusted_baselines:
            fe_multiplier = 1.0 + (custom_theme - 1) * 0.5
            adjusted_baselines["FE Devs"] *= fe_multiplier

        # Project Oversight: Adjust PM allocation (1→0.5x less, 3→1.0x baseline, 5→1.5x more)
        # Uses linear interpolation centered at value 3 (typical oversight)
        if "PMs" in adjusted_baselines:
            # Map slider: 1→0.5x, 2→0.75x, 3→1.0x, 4→1.25x, 5→1.5x
            # Formula: 1.0 + (value - 3) * 0.25
            pm_multiplier = 1.0 + (project_oversight - 3) * 0.25
            adjusted_baselines["PMs"] *= pm_multiplier

        # Calculate distribution ratios by normalizing adjusted baselines
        # NOTE: After normalization, these become PROPORTIONS that sum to 1.0
        # The actual hours will be: team_hours = total_hours * ratio
        # So the multipliers change the DISTRIBUTION, not the absolute hours
        total_baseline = sum(adjusted_baselines.values())
        distribution_ratios = {
            team: (hours / total_baseline) for team, hours in adjusted_baselines.items()
        }

        # Apply BE Dev boost for extensive customizations
        # User requirement: "extensive customization also generally means more BE Dev support is needed"
        if "BE Devs" in distribution_ratios:
            # Determine multiplier using smooth interpolation across full 1-5 scale
            # Formula: 1.0 + max(0, (value - 2)) * 0.1
            # Value 1-2: no boost (1.0x), Value 3: +10% (1.1x), Value 4: +20% (1.2x), Value 5: +30% (1.3x)
            multiplier = 1.0 + max(0, (extensive_customizations - 2)) * 0.1

            # Calculate boosted BE hours
            baseline_be_ratio = distribution_ratios["BE Devs"]
            boosted_be_ratio = baseline_be_ratio * multiplier
            extra_ratio = boosted_be_ratio - baseline_be_ratio

            # Reduce other teams proportionally to absorb the extra BE allocation
            # Calculate total ratio of non-BE teams
            other_teams_total_ratio = sum(
                ratio
                for team, ratio in distribution_ratios.items()
                if team != "BE Devs"
            )

            if other_teams_total_ratio > 0:
                # Reduce each non-BE team proportionally
                reduction_factor = (1.0 - extra_ratio) / (1.0 - baseline_be_ratio)

                adjusted_ratios = {}
                for team, ratio in distribution_ratios.items():
                    if team == "BE Devs":
                        adjusted_ratios[team] = boosted_be_ratio
                    else:
                        adjusted_ratios[team] = ratio * reduction_factor

                distribution_ratios = adjusted_ratios

        # IMPORTANT: Final normalization to ensure ratios sum to exactly 1.0
        # This prevents rounding errors from causing total hours mismatch
        ratio_sum = sum(distribution_ratios.values())
        if ratio_sum != 1.0:
            distribution_ratios = {
                team: ratio / ratio_sum for team, ratio in distribution_ratios.items()
            }

        # Calculate actual hours per team
        teams_data = []
        for team in teams_selected:
            if team not in distribution_ratios:
                continue

            team_hours = total_hours * distribution_ratios[team]
            percentage = distribution_ratios[team] * 100

            # Get lifecycle percentages (historical data-based, no adjustments needed)
            lifecycle = self._get_adjusted_lifecycle(
                team,
                be_integrations=be_integrations >= 3,
                custom_designs=custom_designs >= 3,
                ux_research=ux_research >= 3,
                estimated_months=estimated_months,
            )

            # Distribute hours across months
            monthly_breakdown = self._distribute_hours_by_month(
                team_hours,
                estimated_months,
                lifecycle,
                team,  # Pass team name for Design/UX front-loading
                start_date,  # Pass start date for proration
            )

            teams_data.append(
                {
                    "team": team,
                    "total_hours": round(team_hours, 2),
                    "percentage": round(percentage, 2),
                    "monthly_breakdown": monthly_breakdown,
                }
            )

        # CRITICAL FIX: Ensure team hours sum exactly to total_hours
        # Rounding can cause small discrepancies, so adjust the largest team
        actual_sum = sum(team["total_hours"] for team in teams_data)
        if actual_sum != total_hours:
            # Find largest team and adjust its hours to make total exact
            largest_team = max(teams_data, key=lambda t: t["total_hours"])
            adjustment = total_hours - actual_sum
            largest_team["total_hours"] = round(
                largest_team["total_hours"] + adjustment, 2
            )

        # Report baseline as blend percentage
        baseline_description = (
            f"Blended ({int(blend_factor * 100)}% integration baseline)"
        )

        return {
            "total_hours": total_hours,
            "estimated_months": estimated_months,
            "teams": teams_data,
            "distribution_ratios": {
                team: round(ratio * 100, 2)
                for team, ratio in distribution_ratios.items()
            },
            "baseline_set_used": baseline_description,
            "characteristics": {
                "be_integrations": be_integrations,
                "custom_theme": custom_theme,
                "custom_designs": custom_designs,
                "ux_research": ux_research,
                "extensive_customizations": extensive_customizations,
            },
        }

    def _apply_characteristic_adjustments(
        self,
        ratios: Dict[str, float],
        be_integrations: bool,
        custom_theme: bool,
        custom_designs: bool,
        ux_research: bool,
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
        if be_integrations and "BE Devs" in adjusted:
            # Historical data shows 6.63x multiplier
            adjusted["BE Devs"] *= 6.63

        # Custom theme increases FE workload
        if custom_theme and "FE Devs" in adjusted:
            adjusted["FE Devs"] *= 1.35

        # Custom designs increase Design team involvement
        if custom_designs and "Design" in adjusted:
            adjusted["Design"] *= 1.5

        # UX research extends UX engagement
        if ux_research and "UX" in adjusted:
            adjusted["UX"] *= 1.4

        return adjusted

    def _get_adjusted_lifecycle(
        self,
        team: str,
        be_integrations: bool,
        custom_designs: bool,
        ux_research: bool,
        estimated_months: int,
    ) -> Dict[str, float]:
        """
        Get lifecycle percentages from historical data.

        Returns base historical percentages without adjustments, since the
        real data already reflects how teams actually work on projects.
        """
        base_lifecycle = self.lifecycle_percentages.get(
            team, {"ramp_up": 40.0, "busy": 45.0, "ramp_down": 15.0}
        ).copy()

        return base_lifecycle

    def get_epic_monthly_breakdown(
        self, epics: List[Dict[str, Any]], project_start_date: str = None
    ) -> Dict[str, Any]:
        """
        Calculate epic-by-epic monthly hour breakdown for project forecasting.

        Args:
            epics: List of epic dictionaries with:
                - name: Epic name
                - estimated_hours: Total hours for epic
                - estimated_months: Duration in months
                - teams_selected: List of team names
                - be_integrations: Backend integrations slider value (1-5)
                - custom_theme: Custom theme slider value (1-5)
                - custom_designs: Custom designs slider value (1-5)
                - ux_research: UX research slider value (1-5)
                - extensive_customizations: Customizations slider value (1-5)
                - project_oversight: Oversight slider value (1-5)
                - start_date: Optional start date for this epic (YYYY-MM-DD)
            project_start_date: Optional project start date (YYYY-MM-DD) for all epics

        Returns:
            Dictionary with:
                - epics: List of epic breakdowns with monthly hours per team
                - months: List of month labels
                - totals_by_month: Total hours per month across all epics
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # Calculate forecast for each epic
        epic_breakdowns = []
        all_months = set()
        month_totals = {}

        for epic in epics:
            # Use epic-specific start date or project start date
            epic_start_date = epic.get("start_date", project_start_date)

            # Calculate team distribution for this epic
            forecast = self.calculate_from_total_hours(
                total_hours=epic["estimated_hours"],
                be_integrations=epic.get("be_integrations", 3),
                custom_theme=epic.get("custom_theme", 3),
                custom_designs=epic.get("custom_designs", 3),
                ux_research=epic.get("ux_research", 3),
                extensive_customizations=epic.get("extensive_customizations", 1),
                project_oversight=epic.get("project_oversight", 3),
                teams_selected=epic["teams_selected"],
                estimated_months=epic["estimated_months"],
                start_date=epic_start_date,
            )

            # Build monthly breakdown for this epic
            epic_monthly = {
                "epic_name": epic["name"],
                "total_hours": epic["estimated_hours"],
                "estimated_months": epic["estimated_months"],
                "start_date": epic_start_date,
                "teams": [],
                "months": [],
            }

            # If we have a start date, calculate actual month labels
            if epic_start_date:
                try:
                    start_dt = datetime.fromisoformat(epic_start_date)
                    for i in range(epic["estimated_months"]):
                        month_dt = start_dt + relativedelta(months=i)
                        month_label = month_dt.strftime("%Y-%m")
                        epic_monthly["months"].append(month_label)
                        all_months.add(month_label)

                        # Initialize month total if not exists
                        if month_label not in month_totals:
                            month_totals[month_label] = 0.0
                except (ValueError, AttributeError):
                    # If date parsing fails, use generic month numbers
                    for i in range(epic["estimated_months"]):
                        month_label = f"Month {i + 1}"
                        epic_monthly["months"].append(month_label)
                        all_months.add(month_label)

                        if month_label not in month_totals:
                            month_totals[month_label] = 0.0
            else:
                # No date provided, use generic month numbers
                for i in range(epic["estimated_months"]):
                    month_label = f"Month {i + 1}"
                    epic_monthly["months"].append(month_label)
                    all_months.add(month_label)

                    if month_label not in month_totals:
                        month_totals[month_label] = 0.0

            # Process each team's breakdown
            for team_data in forecast["teams"]:
                team_monthly = {
                    "team": team_data["team"],
                    "total_hours": team_data["total_hours"],
                    "monthly_hours": [],
                }

                # Add monthly hours and aggregate to month totals
                for month_idx, month_breakdown in enumerate(
                    team_data["monthly_breakdown"]
                ):
                    hours = month_breakdown["hours"]
                    team_monthly["monthly_hours"].append(
                        {
                            "month": epic_monthly["months"][month_idx],
                            "hours": hours,
                            "phase": month_breakdown["phase"],
                        }
                    )

                    # Add to month total
                    month_label = epic_monthly["months"][month_idx]
                    month_totals[month_label] += hours

                epic_monthly["teams"].append(team_monthly)

            epic_breakdowns.append(epic_monthly)

        # Sort months chronologically
        sorted_months = sorted(list(all_months))

        # Build totals by month in sorted order
        totals_list = [
            {"month": month, "total_hours": round(month_totals.get(month, 0.0), 2)}
            for month in sorted_months
        ]

        return {
            "epics": epic_breakdowns,
            "months": sorted_months,
            "totals_by_month": totals_list,
        }
