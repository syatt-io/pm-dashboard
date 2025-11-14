"""Service for querying and applying learned characteristic impacts.

This service provides data-driven team allocation patterns based on project
characteristics, replacing hardcoded multipliers with learned patterns from
historical projects.
"""

from typing import Dict, Optional
from collections import defaultdict
import logging

from sqlalchemy import func
from src.models import CharacteristicImpactBaseline
from src.utils.database import get_session

logger = logging.getLogger(__name__)


class CharacteristicImpactService:
    """Service for querying and applying learned characteristic impacts."""

    def __init__(self):
        """Initialize the service."""
        self.session = get_session()
        self._impact_cache = None

    def _load_impacts(self) -> Dict:
        """
        Load all characteristic impacts from database into memory cache.

        Returns:
            Dict mapping (characteristic_name, characteristic_value, team) to impact data
        """
        if self._impact_cache is not None:
            return self._impact_cache

        logger.info("Loading characteristic impacts from database...")

        impacts = self.session.query(CharacteristicImpactBaseline).all()

        if not impacts:
            logger.warning(
                "No characteristic impacts found in database. "
                "Run scripts/learn_characteristic_impacts.py to generate patterns."
            )
            return {}

        # Build cache
        cache = {}
        for impact in impacts:
            key = (impact.characteristic_name, impact.characteristic_value, impact.team)
            cache[key] = {
                "avg_allocation_pct": impact.avg_allocation_pct,
                "std_dev": impact.std_dev,
                "sample_size": impact.sample_size,
            }

        logger.info(f"Loaded {len(cache)} characteristic impact entries")
        self._impact_cache = cache
        return cache

    def get_allocation_for_characteristic(
        self, characteristic_name: str, characteristic_value: int, team: str
    ) -> Optional[float]:
        """
        Get the expected team allocation percentage for a characteristic value.

        Args:
            characteristic_name: Name of characteristic (e.g., "custom_designs")
            characteristic_value: Value of characteristic (1-5 scale)
            team: Team name (e.g., "Design", "FE Devs")

        Returns:
            Expected allocation percentage, or None if no pattern found

        Example:
            >>> service.get_allocation_for_characteristic("custom_designs", 5, "Design")
            18.5  # Design team averages 18.5% for projects with custom_designs=5
        """
        impacts = self._load_impacts()

        key = (characteristic_name, characteristic_value, team)
        impact = impacts.get(key)

        if impact:
            return impact["avg_allocation_pct"]

        return None

    def get_allocation_with_fallback(
        self,
        characteristic_name: str,
        characteristic_value: int,
        team: str,
        fallback_pct: float,
    ) -> float:
        """
        Get allocation with fallback to a default if no learned pattern exists.

        Args:
            characteristic_name: Name of characteristic
            characteristic_value: Value of characteristic (1-5)
            team: Team name
            fallback_pct: Fallback percentage if no pattern found

        Returns:
            Learned allocation percentage or fallback
        """
        allocation = self.get_allocation_for_characteristic(
            characteristic_name, characteristic_value, team
        )

        if allocation is not None:
            logger.debug(
                f"Using learned allocation for {characteristic_name}={characteristic_value}, "
                f"{team}: {allocation:.1f}%"
            )
            return allocation

        logger.debug(
            f"No learned pattern for {characteristic_name}={characteristic_value}, "
            f"{team}. Using fallback: {fallback_pct:.1f}%"
        )
        return fallback_pct

    def get_team_allocations_for_project(
        self, project_characteristics: Dict[str, int]
    ) -> Dict[str, Dict[str, float]]:
        """
        Get learned allocations for all relevant teams based on project characteristics.

        Args:
            project_characteristics: Dict of characteristic_name -> value
                e.g., {"custom_designs": 5, "be_integrations": 3, ...}

        Returns:
            Dict mapping characteristic_name to {team: allocation_pct}

        Example:
            >>> characteristics = {"custom_designs": 5, "be_integrations": 2}
            >>> service.get_team_allocations_for_project(characteristics)
            {
                "custom_designs": {"Design": 18.5},
                "be_integrations": {"BE Devs": 8.2}
            }
        """
        impacts = self._load_impacts()

        result = defaultdict(dict)

        for char_name, char_value in project_characteristics.items():
            # Find all teams with learned impacts for this characteristic value
            for (cached_char, cached_value, team), impact_data in impacts.items():
                if cached_char == char_name and cached_value == char_value:
                    result[char_name][team] = impact_data["avg_allocation_pct"]

        return dict(result)

    def get_all_impacts_for_characteristic(
        self, characteristic_name: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Get all learned impacts for a specific characteristic across all values.

        Args:
            characteristic_name: Name of characteristic (e.g., "custom_designs")

        Returns:
            Dict mapping characteristic_value to {team: allocation_pct}

        Example:
            >>> service.get_all_impacts_for_characteristic("custom_designs")
            {
                1: {"Design": 6.2},
                2: {"Design": 9.5},
                3: {"Design": 12.3},
                4: {"Design": 15.8},
                5: {"Design": 18.5}
            }
        """
        impacts = self._load_impacts()

        result = defaultdict(dict)

        for (char_name, char_value, team), impact_data in impacts.items():
            if char_name == characteristic_name:
                result[char_value][team] = impact_data["avg_allocation_pct"]

        return dict(result)

    def get_impact_summary(self) -> Dict[str, Dict[str, any]]:
        """
        Get a summary of all learned characteristic impacts.

        Returns:
            Dict mapping characteristic_name to summary data

        Example:
            {
                "custom_designs": {
                    "teams_impacted": ["Design"],
                    "value_range": (1, 5),
                    "patterns": {
                        1: {"Design": 6.2},
                        5: {"Design": 18.5}
                    }
                }
            }
        """
        impacts = self._load_impacts()

        summary = defaultdict(
            lambda: {
                "teams_impacted": set(),
                "value_range": [999, -999],
                "patterns": defaultdict(dict),
            }
        )

        for (char_name, char_value, team), impact_data in impacts.items():
            summary[char_name]["teams_impacted"].add(team)
            summary[char_name]["value_range"][0] = min(
                summary[char_name]["value_range"][0], char_value
            )
            summary[char_name]["value_range"][1] = max(
                summary[char_name]["value_range"][1], char_value
            )
            summary[char_name]["patterns"][char_value][team] = impact_data[
                "avg_allocation_pct"
            ]

        # Convert sets to lists for JSON serialization
        for char_name in summary:
            summary[char_name]["teams_impacted"] = list(
                summary[char_name]["teams_impacted"]
            )
            summary[char_name]["value_range"] = tuple(summary[char_name]["value_range"])
            summary[char_name]["patterns"] = dict(summary[char_name]["patterns"])

        return dict(summary)

    def refresh_cache(self):
        """Refresh the in-memory impact cache from database."""
        self._impact_cache = None
        self._load_impacts()
        logger.info("Characteristic impact cache refreshed")

    def has_learned_data(self) -> bool:
        """Check if any learned characteristic impacts exist."""
        impacts = self._load_impacts()
        return len(impacts) > 0

    def get_sample_size(
        self, characteristic_name: str, characteristic_value: int, team: str
    ) -> Optional[int]:
        """
        Get the sample size (number of projects) for a learned pattern.

        Useful for determining confidence in the learned allocation.

        Args:
            characteristic_name: Name of characteristic
            characteristic_value: Value of characteristic (1-5)
            team: Team name

        Returns:
            Number of projects in sample, or None if no pattern found
        """
        impacts = self._load_impacts()

        key = (characteristic_name, characteristic_value, team)
        impact = impacts.get(key)

        if impact:
            return impact["sample_size"]

        return None
