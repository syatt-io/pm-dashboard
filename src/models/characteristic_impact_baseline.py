"""Characteristic impact baseline model for learned team allocation multipliers."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from .base import Base


class CharacteristicImpactBaseline(Base):
    """Learned characteristic impacts on team allocations from historical projects.

    Stores the average team allocation percentages based on project characteristics,
    learned from historical epic_hours data.

    Example:
        For projects with custom_designs=5:
        - Design team averages 18.5% of total project hours
        - Standard deviation: 3.2%
        - Sample size: 15 projects

        For projects with be_integrations=1:
        - BE Devs team averages 8.2% of total project hours
        - Standard deviation: 2.1%
        - Sample size: 12 projects

    This replaces hardcoded multipliers like:
        design_multiplier = 1.0 + (custom_designs - 1) * 0.75  # OLD HARDCODED

    With learned data:
        get_learned_allocation(characteristic='custom_designs', value=5, team='Design')
        -> returns 18.5% (actual historical average)
    """

    __tablename__ = "characteristic_impact_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)

    characteristic_name = Column(
        String(50),
        nullable=False,
        comment="Name of the characteristic (e.g., custom_designs, be_integrations)",
    )

    characteristic_value = Column(
        Integer, nullable=False, comment="Value of the characteristic (1-5 scale)"
    )

    team = Column(
        String(50), nullable=False, comment="Team name (e.g., Design, FE Devs, BE Devs)"
    )

    avg_allocation_pct = Column(
        Float,
        nullable=False,
        comment="Average percentage of total project hours this team used",
    )

    std_dev = Column(
        Float, nullable=True, comment="Standard deviation of allocation percentage"
    )

    sample_size = Column(
        Integer,
        nullable=False,
        comment="Number of historical projects in this category",
    )

    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When this baseline was last recalculated",
    )

    # Indexes defined in migration, but also declared here for ORM awareness
    __table_args__ = (
        Index(
            "ix_characteristic_impact_lookup",
            "characteristic_name",
            "characteristic_value",
            "team",
        ),
        Index("ix_characteristic_impact_name", "characteristic_name"),
        Index("ix_characteristic_impact_team", "team"),
    )

    def __repr__(self):
        return (
            f"<CharacteristicImpactBaseline("
            f"{self.characteristic_name}={self.characteristic_value}, "
            f"team={self.team}, "
            f"avg_allocation={self.avg_allocation_pct:.1f}%, "
            f"sample_size={self.sample_size}"
            f")>"
        )
