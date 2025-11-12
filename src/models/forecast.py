"""
Epic forecast models for storing project estimates.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from src.models import Base


class EpicForecast(Base):
    """Stores epic forecasts with project characteristics and team hour estimates."""

    __tablename__ = "epic_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Epic info
    project_key = Column(String(50), nullable=False, index=True)
    epic_name = Column(String(200), nullable=False)
    epic_description = Column(Text, nullable=True)

    # Project characteristics (user inputs)
    be_integrations = Column(Boolean, default=False, nullable=False)
    custom_theme = Column(Boolean, default=False, nullable=False)
    custom_designs = Column(Boolean, default=False, nullable=False)
    ux_research = Column(Boolean, default=False, nullable=False)

    # Duration
    estimated_months = Column(Integer, nullable=False)

    # Team selections (which teams are needed)
    teams_selected = Column(
        JSON, nullable=False
    )  # e.g., ["FE Devs", "BE Devs", "Design"]

    # Forecast results (JSON structure with month-by-month breakdown)
    forecast_data = Column(JSON, nullable=False)
    # Example structure:
    # {
    #     "FE Devs": {
    #         "total_hours": 39.82,
    #         "monthly_breakdown": [
    #             {"month": 1, "phase": "Ramp Up", "hours": 18.3},
    #             {"month": 2, "phase": "Busy", "hours": 16.3},
    #             {"month": 3, "phase": "Ramp Down", "hours": 5.2}
    #         ]
    #     }
    # }

    # Total hours across all teams
    total_hours = Column(Float, nullable=False)

    # Metadata
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<EpicForecast(id={self.id}, project={self.project_key}, epic={self.epic_name}, total={self.total_hours}h)>"
