"""Monthly epic reconciliation report model."""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.sql import func
from src.models import Base


class MonthlyReconciliationReport(Base):
    """Tracks monthly epic hours reconciliation reports.

    Generated at the end of each month to compare forecasted vs actual epic hours.
    Replaces manual Google Sheets tracking with automated reports.

    Attributes:
        id: Auto-incrementing primary key
        month: Month in YYYY-MM format (e.g., '2025-10')
        generated_at: When the report was generated
        file_path: S3/Spaces URL or local path to Excel file
        total_projects: Number of projects included in report
        total_epics: Number of epics analyzed
        total_variance_pct: Portfolio-wide variance percentage
        sent_to: JSON list of email addresses report was sent to
        report_metadata: JSON with additional report details (projects analyzed, etc.)
    """

    __tablename__ = "monthly_reconciliation_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String(7), nullable=False, unique=True, index=True)  # YYYY-MM
    generated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    file_path = Column(String(500), nullable=True)  # URL or path to report file
    total_projects = Column(Integer, nullable=False, default=0)
    total_epics = Column(Integer, nullable=False, default=0)
    total_variance_pct = Column(Float, nullable=True)  # Overall portfolio variance
    sent_to = Column(JSON, nullable=True)  # List of recipients
    report_metadata = Column(JSON, nullable=True)  # Additional report details

    def __repr__(self):
        return f"<MonthlyReconciliationReport(month={self.month}, projects={self.total_projects}, variance={self.total_variance_pct}%)>"

    @property
    def is_variance_high(self) -> bool:
        """Check if portfolio variance exceeds threshold (20%)."""
        return self.total_variance_pct and abs(self.total_variance_pct) > 20.0
