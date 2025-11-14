"""Service for querying and applying learned temporal patterns from historical data.

This service provides data-driven temporal distribution patterns for forecasting,
replacing hardcoded assumptions with learned patterns from historical projects.
"""

from datetime import date
from typing import Dict, List, Optional
from collections import defaultdict
import logging

from sqlalchemy import func
from src.models import TemporalPatternBaseline
from src.utils.database import get_session

logger = logging.getLogger(__name__)


class TemporalPatternService:
    """Service for querying and applying learned temporal patterns."""

    def __init__(self):
        """Initialize the service."""
        self.session = get_session()
        self._pattern_cache = None

    def _load_patterns(self) -> Dict:
        """
        Load all temporal patterns from database into memory cache.

        Returns:
            Dict mapping (timeline_start_pct, timeline_end_pct, team) to work_pct
        """
        if self._pattern_cache is not None:
            return self._pattern_cache

        logger.info("Loading temporal patterns from database...")

        patterns = self.session.query(TemporalPatternBaseline).all()

        if not patterns:
            logger.warning(
                "No temporal patterns found in database. "
                "Run scripts/learn_temporal_patterns.py to generate patterns."
            )
            return {}

        # Build cache
        cache = {}
        for pattern in patterns:
            key = (pattern.timeline_start_pct, pattern.timeline_end_pct, pattern.team)
            cache[key] = {
                "work_pct": pattern.work_pct,
                "sample_size": pattern.sample_size,
            }

        logger.info(f"Loaded {len(cache)} temporal pattern entries")
        self._pattern_cache = cache
        return cache

    def get_pattern_for_team(self, team: str, timeline_pct: float) -> Optional[float]:
        """
        Get the expected work percentage for a team at a given timeline point.

        Args:
            team: Team name (e.g., "FE Devs", "Design")
            timeline_pct: Timeline percentage (0-100)

        Returns:
            Expected work percentage, or None if no pattern found
        """
        patterns = self._load_patterns()

        # Find which bucket this timeline_pct falls into
        for start in range(0, 100, 10):
            end = start + 10
            if start <= timeline_pct < end:
                key = (start, end, team)
                pattern = patterns.get(key)
                if pattern:
                    return pattern["work_pct"]
                break

        return None

    def distribute_hours_by_month(
        self,
        total_hours: float,
        team: str,
        duration_months: int,
        start_date: date,
        prorate_first_month: bool = True,
        prorate_last_month: bool = True,
    ) -> List[Dict]:
        """
        Distribute hours across months using learned temporal patterns.

        Args:
            total_hours: Total hours to distribute
            team: Team name
            duration_months: Project duration in months
            start_date: Project start date
            prorate_first_month: Whether to prorate first partial month
            prorate_last_month: Whether to prorate last partial month

        Returns:
            List of dicts with keys: month (date), hours (float), timeline_pct (float)
        """
        patterns = self._load_patterns()

        if not patterns:
            logger.warning(
                f"No temporal patterns available. "
                f"Distributing {total_hours}h evenly across {duration_months} months for {team}"
            )
            # Fallback to even distribution
            hours_per_month = total_hours / duration_months
            return [
                {
                    "month": self._get_month_start(start_date, i),
                    "hours": round(hours_per_month, 2),
                    "timeline_pct": (i / duration_months) * 100,
                }
                for i in range(duration_months)
            ]

        # Calculate expected distribution based on learned patterns
        month_distributions = []

        for month_idx in range(duration_months):
            # Calculate timeline percentage for this month (midpoint)
            month_pct = 100.0 / duration_months
            start_pct = month_idx * month_pct
            end_pct = (month_idx + 1) * month_pct
            midpoint_pct = (start_pct + end_pct) / 2

            # Get learned pattern for this timeline point
            work_pct = self.get_pattern_for_team(team, midpoint_pct)

            if work_pct is None:
                # No pattern for this team/timeline - use even distribution for this month
                work_pct = 100.0 / duration_months
                logger.debug(
                    f"No pattern for {team} at {midpoint_pct:.1f}%, "
                    f"using even distribution ({work_pct:.1f}%)"
                )

            # Calculate hours for this month
            month_hours = (work_pct / 100.0) * total_hours

            month_distributions.append(
                {
                    "month": self._get_month_start(start_date, month_idx),
                    "hours": round(month_hours, 2),
                    "timeline_pct": midpoint_pct,
                    "learned_work_pct": work_pct,
                }
            )

        # Apply proration if requested
        if prorate_first_month:
            month_distributions = self._prorate_first_month(
                month_distributions, start_date
            )

        if prorate_last_month:
            month_distributions = self._prorate_last_month(
                month_distributions, start_date, duration_months
            )

        # CRITICAL: Normalize distributions to maintain total_hours budget
        # This handles cases where learned patterns don't sum to 100% or proration edge cases
        actual_total = sum(d["hours"] for d in month_distributions)
        if actual_total > 0 and abs(actual_total - total_hours) > 0.01:
            logger.warning(
                f"{team}: Monthly distribution sums to {actual_total:.2f}h "
                f"but expected {total_hours:.2f}h. Normalizing to maintain budget."
            )
            scale_factor = total_hours / actual_total
            for d in month_distributions:
                d["hours"] = round(d["hours"] * scale_factor, 2)

            # Verify after scaling
            final_total = sum(d["hours"] for d in month_distributions)
            logger.info(
                f"{team}: After normalization, total = {final_total:.2f}h (target: {total_hours:.2f}h)"
            )

        return month_distributions

    def _get_month_start(self, start_date: date, month_offset: int) -> date:
        """Get the first day of a month offset from start_date."""
        year = start_date.year
        month = start_date.month + month_offset

        # Handle year rollover
        while month > 12:
            month -= 12
            year += 1
        while month < 1:
            month += 12
            year -= 1

        return date(year, month, 1)

    def _prorate_first_month(
        self, distributions: List[Dict], start_date: date
    ) -> List[Dict]:
        """Prorate first month based on start date."""
        if not distributions:
            return distributions

        first_month = distributions[0]
        month_start = first_month["month"]

        # Calculate what fraction of the month is used
        days_in_month = self._days_in_month(month_start)
        days_used = days_in_month - start_date.day + 1
        proration_factor = days_used / days_in_month

        # Adjust first month hours
        original_hours = first_month["hours"]
        prorated_hours = original_hours * proration_factor
        adjustment = original_hours - prorated_hours

        first_month["hours"] = round(prorated_hours, 2)
        first_month["prorated"] = True
        first_month["proration_factor"] = proration_factor

        # Redistribute the adjustment to remaining months
        if len(distributions) > 1 and adjustment > 0:
            per_month_adjustment = adjustment / (len(distributions) - 1)
            for dist in distributions[1:]:
                dist["hours"] = round(dist["hours"] + per_month_adjustment, 2)

        return distributions

    def _prorate_last_month(
        self, distributions: List[Dict], start_date: date, duration_months: int
    ) -> List[Dict]:
        """Prorate last month if project doesn't end on month boundary."""
        # This is a simplified version - can be enhanced based on actual end dates
        return distributions

    def _days_in_month(self, month_date: date) -> int:
        """Get number of days in a month."""
        if month_date.month == 12:
            next_month = date(month_date.year + 1, 1, 1)
        else:
            next_month = date(month_date.year, month_date.month + 1, 1)

        from datetime import timedelta

        last_day = next_month - timedelta(days=1)
        return last_day.day

    def get_all_patterns_summary(self) -> Dict[str, List[Dict]]:
        """
        Get a summary of all learned patterns organized by timeline bucket.

        Returns:
            Dict mapping timeline ranges to list of team patterns
        """
        patterns = self._load_patterns()

        summary = defaultdict(list)

        for (start_pct, end_pct, team), data in patterns.items():
            key = f"{start_pct}-{end_pct}%"
            summary[key].append(
                {
                    "team": team,
                    "work_pct": data["work_pct"],
                    "sample_size": data["sample_size"],
                }
            )

        # Sort each bucket by work_pct descending
        for key in summary:
            summary[key].sort(key=lambda x: x["work_pct"], reverse=True)

        return dict(summary)

    def refresh_cache(self):
        """Refresh the in-memory pattern cache from database."""
        self._pattern_cache = None
        self._load_patterns()
        logger.info("Temporal pattern cache refreshed")
