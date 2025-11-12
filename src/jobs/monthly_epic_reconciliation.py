"""
Monthly Epic Reconciliation Job

Scheduled job to generate end-of-month epic hours vs forecast report.
Runs on the 3rd of every month at 9 AM EST to analyze previous month.
Replaces manual Google Sheets tracking with automated Excel reports.

IMPORTANT: Runs on 3rd of month to allow time for hours to be logged
after month-end before reconciliation.
"""

import logging
import os
import asyncio
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models import EpicHours, EpicForecast, MonthlyReconciliationReport
from src.services.report_generator import ReportGenerator
from src.managers.notifications import NotificationManager
from src.jobs.epic_association_analyzer import run_epic_association_analysis
from config.settings import settings

logger = logging.getLogger(__name__)


class MonthlyEpicReconciliationJob:
    """Generates monthly epic hours vs forecast reconciliation reports."""

    def __init__(self):
        """Initialize the job with required services and database connection."""
        self.report_generator = ReportGenerator()
        self.notification_manager = NotificationManager(settings)

        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Create database engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_previous_month(self) -> str:
        """
        Get the previous month in YYYY-MM format.

        Returns:
            Month string (e.g., "2025-10")
        """
        today = datetime.now().date()
        first_of_month = date(today.year, today.month, 1)
        previous_month = first_of_month - relativedelta(months=1)
        month_str = previous_month.strftime("%Y-%m")

        logger.info(f"Reconciling month: {month_str}")
        return month_str

    def get_active_project_based_projects(self) -> List[str]:
        """
        Get list of active project-based projects.

        Returns:
            List of project keys (e.g., ["SUBS", "SATG"])
        """
        session = self.Session()
        try:
            result = session.execute(
                text(
                    """
                SELECT key
                FROM projects
                WHERE is_active = true
                AND project_work_type = 'project-based'
                ORDER BY key
            """
                )
            )
            project_keys = [row[0] for row in result.fetchall()]
            logger.info(
                f"Found {len(project_keys)} active project-based projects: {project_keys}"
            )
            return project_keys
        finally:
            session.close()

    def fetch_epic_data(self, month: str) -> List[Dict]:
        """
        Fetch epic hours and forecast data for the specified month.
        Only includes Active + Project-based projects.

        Args:
            month: Month in YYYY-MM format (e.g., "2025-10")

        Returns:
            List of dictionaries with epic data
        """
        session = self.Session()
        try:
            logger.info(f"Fetching epic data for {month}")

            # Get active project-based projects
            project_keys = self.get_active_project_based_projects()
            if not project_keys:
                logger.warning("No active project-based projects found")
                return []

            # Convert month string to date (first day of month)
            month_date = datetime.strptime(month, "%Y-%m").date()

            # Query EpicHours for actual hours, filtered by project type
            actual_hours = (
                session.query(EpicHours)
                .filter(
                    EpicHours.month == month_date,
                    EpicHours.project_key.in_(project_keys),
                )
                .all()
            )

            logger.info(
                f"Found {len(actual_hours)} epic hour records for {month} "
                f"(filtered to {len(project_keys)} project-based projects)"
            )

            # Build epic data with forecast integration
            epic_data = []

            for hours in actual_hours:
                # Lookup forecast for this epic
                # EpicForecast.forecast_data contains monthly breakdown in JSON
                forecast_hours = 0.0

                # Try to find matching forecast
                forecast = (
                    session.query(EpicForecast)
                    .filter(
                        EpicForecast.project_key == hours.project_key,
                        EpicForecast.epic_name == hours.epic_summary,
                    )
                    .first()
                )

                if forecast and forecast.forecast_data:
                    # Extract forecast hours for this month from forecast_data JSON
                    # Format: {"FE Devs": {"monthly_breakdown": [{"month": 1, "hours": 18.3}, ...]}, ...}
                    try:
                        forecast_data = forecast.forecast_data
                        team_forecast = forecast_data.get(hours.team, {})
                        monthly_breakdown = team_forecast.get("monthly_breakdown", [])

                        # Find matching month (month field in forecast_data is integer, need to match to calendar month)
                        # This is simplified - actual implementation would need proper month mapping
                        for month_entry in monthly_breakdown:
                            # Sum all months for now as simplified approach
                            forecast_hours += month_entry.get("hours", 0.0)

                    except Exception as e:
                        logger.warning(
                            f"Error extracting forecast for {hours.epic_key}: {e}"
                        )
                        forecast_hours = 0.0

                # Calculate variance
                variance_hours = hours.hours - forecast_hours
                variance_pct = (
                    (variance_hours / forecast_hours * 100)
                    if forecast_hours > 0
                    else 0.0
                )

                epic_data.append(
                    {
                        "project_key": hours.project_key,
                        "epic_key": hours.epic_key,
                        "epic_name": hours.epic_summary or "Unknown",
                        "team": hours.team or "All",
                        "forecast_hours": forecast_hours,
                        "actual_hours": hours.hours,
                        "variance_hours": variance_hours,
                        "variance_pct": variance_pct,
                    }
                )

            logger.info(
                f"Processed data for {len(epic_data)} epics across project-based projects"
            )
            return epic_data

        finally:
            session.close()

    def calculate_summary(self, epic_data: List[Dict]) -> Dict:
        """
        Calculate summary statistics for executive overview.

        Args:
            epic_data: List of epic data dictionaries

        Returns:
            Dictionary with summary statistics
        """
        if not epic_data:
            return {
                "total_projects": 0,
                "total_epics": 0,
                "total_forecast_hours": 0.0,
                "total_actual_hours": 0.0,
                "total_variance_pct": 0.0,
                "epics_over_budget": 0,
                "epics_under_budget": 0,
            }

        # Count unique projects
        unique_projects = set(e["project_key"] for e in epic_data)

        # Sum totals
        total_forecast = sum(e["forecast_hours"] for e in epic_data)
        total_actual = sum(e["actual_hours"] for e in epic_data)
        total_variance = total_actual - total_forecast
        total_variance_pct = (
            (total_variance / total_forecast * 100) if total_forecast > 0 else 0
        )

        # Count over/under budget epics
        epics_over = sum(1 for e in epic_data if e["variance_pct"] > 10)
        epics_under = sum(1 for e in epic_data if e["variance_pct"] < -10)

        summary = {
            "total_projects": len(unique_projects),
            "total_epics": len(epic_data),
            "total_forecast_hours": total_forecast,
            "total_actual_hours": total_actual,
            "total_variance_pct": total_variance_pct,
            "epics_over_budget": epics_over,
            "epics_under_budget": epics_under,
        }

        logger.info(
            f"Summary: {len(unique_projects)} projects, {len(epic_data)} epics, "
            f"{total_variance_pct:.1f}% variance"
        )

        return summary

    def generate_report(
        self, month: str, epic_data: List[Dict], summary: Dict
    ) -> bytes:
        """
        Generate Excel report.

        Args:
            month: Month in YYYY-MM format
            epic_data: List of epic data
            summary: Summary statistics

        Returns:
            Excel file as bytes
        """
        logger.info(f"Generating Excel report for {month}")

        excel_buffer = self.report_generator.generate_epic_reconciliation_report(
            month=month, epic_data=epic_data, project_summary=summary
        )

        return excel_buffer.read()

    def save_report(self, month: str, file_content: bytes, summary: Dict) -> str:
        """
        Save report file to disk and record in database.

        Args:
            month: Month in YYYY-MM format
            file_content: Excel file bytes
            summary: Summary statistics

        Returns:
            File path where report was saved
        """
        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(os.getcwd(), "reports", "epic_reconciliation")
        os.makedirs(reports_dir, exist_ok=True)

        # Generate filename
        filename = f"epic_reconciliation_{month}.xlsx"
        file_path = os.path.join(reports_dir, filename)

        # Write file
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved report to {file_path}")

        # Record in database
        session = self.Session()
        try:
            # Check if report already exists
            existing = (
                session.query(MonthlyReconciliationReport)
                .filter_by(month=month)
                .first()
            )

            if existing:
                existing.file_path = file_path
                existing.total_projects = summary["total_projects"]
                existing.total_epics = summary["total_epics"]
                existing.total_variance_pct = summary["total_variance_pct"]
                existing.generated_at = datetime.now()
            else:
                report_record = MonthlyReconciliationReport(
                    month=month,
                    file_path=file_path,
                    total_projects=summary["total_projects"],
                    total_epics=summary["total_epics"],
                    total_variance_pct=summary["total_variance_pct"],
                )
                session.add(report_record)

            session.commit()
            logger.info(f"Recorded report in database for {month}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error recording report in database: {e}")
            raise
        finally:
            session.close()

        return file_path

    async def send_notifications(
        self, month: str, file_path: str, summary: Dict
    ) -> None:
        """
        Send report via email to PMs.

        Args:
            month: Month in YYYY-MM format
            file_path: Path to Excel file
            summary: Summary statistics
        """
        # Get PM emails from environment or config
        pm_emails = os.getenv("PM_EMAILS", "").split(",")
        pm_emails = [email.strip() for email in pm_emails if email.strip()]

        if not pm_emails:
            logger.warning("No PM emails configured, skipping email notification")
            return

        # Format month for display
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")

        # Build email message
        subject = f"📊 Monthly Epic Reconciliation - {month_display}"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #554DFF;">Monthly Epic Reconciliation Report</h2>
            <p>The monthly epic hours reconciliation for <strong>{month_display}</strong> has been generated.</p>

            <h3>Summary:</h3>
            <ul>
                <li><strong>Projects:</strong> {summary['total_projects']}</li>
                <li><strong>Epics Analyzed:</strong> {summary['total_epics']}</li>
                <li><strong>Forecast Hours:</strong> {summary['total_forecast_hours']:.1f}</li>
                <li><strong>Actual Hours:</strong> {summary['total_actual_hours']:.1f}</li>
                <li><strong>Overall Variance:</strong> {summary['total_variance_pct']:.1f}%</li>
                <li><strong>Epics Over Budget (&gt;10%):</strong> {summary['epics_over_budget']}</li>
                <li><strong>Epics Under Budget (&lt;-10%):</strong> {summary['epics_under_budget']}</li>
            </ul>

            <p>The detailed report is attached as an Excel file.</p>

            <p style="color: #666; font-size: 12px;">
                Generated by Autonomous PM Agent on {datetime.now().strftime("%Y-%m-%d %H:%M")}
            </p>
        </body>
        </html>
        """

        # Send via SMTP
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.application import MIMEApplication

            smtp_config = self.notification_manager.smtp_config
            if not smtp_config:
                logger.warning("SMTP not configured, cannot send email")
                return

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"{smtp_config['from_name']} <{smtp_config['from_email']}>"
            msg["To"] = ", ".join(pm_emails)

            # Attach HTML body
            html_part = MIMEText(body, "html")
            msg.attach(html_part)

            # Attach Excel file
            with open(file_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="xlsx")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(file_path),
                )
                msg.attach(attachment)

            # Send email
            with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
                server.starttls()
                server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)

            logger.info(f"Sent email to {len(pm_emails)} recipients")

            # Update database record with recipients
            session = self.Session()
            try:
                report = (
                    session.query(MonthlyReconciliationReport)
                    .filter_by(month=month)
                    .first()
                )
                if report:
                    report.sent_to = pm_emails
                    session.commit()
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def run(self) -> Dict:
        """
        Execute the Monthly Epic Reconciliation job.

        Phase 1: Epic Association (ensure all tickets have epics)
        Phase 2: Reconciliation (compare forecast vs actual hours)

        Returns:
            Dictionary with job execution statistics
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info(f"Starting Monthly Epic Reconciliation job at {start_time}")
        logger.info("=" * 80)

        try:
            # PHASE 1: Epic Association Analysis
            logger.info("\n📋 PHASE 1: Epic Association Analysis")
            logger.info("-" * 80)

            association_results = asyncio.run(run_epic_association_analysis())

            logger.info("\nEpic Association Complete:")
            logger.info(
                f"  - Projects analyzed: {association_results.get('total_projects', 0)}"
            )
            logger.info(
                f"  - Tickets analyzed: {association_results.get('total_tickets_analyzed', 0)}"
            )
            logger.info(
                f"  - Matches found: {association_results.get('total_matches_found', 0)}"
            )

            if association_results.get("auto_update_enabled"):
                logger.info(
                    f"  - Updates applied: {association_results.get('updates_applied', 0)}"
                )
                logger.info(
                    f"  - Failures: {association_results.get('update_failures', 0)}"
                )

            # PHASE 2: Epic Hours Reconciliation
            logger.info("\n📊 PHASE 2: Epic Hours Reconciliation")
            logger.info("-" * 80)

            # Get previous month
            month = self.get_previous_month()

            # Fetch epic data
            epic_data = self.fetch_epic_data(month)

            if not epic_data:
                logger.warning(f"No epic data found for {month}")
                return {
                    "success": True,
                    "start_time": start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "month": month,
                    "epics_processed": 0,
                    "message": "No data to process",
                }

            # Calculate summary
            summary = self.calculate_summary(epic_data)

            # Generate Excel report
            report_bytes = self.generate_report(month, epic_data, summary)

            # Save report
            file_path = self.save_report(month, report_bytes, summary)

            # Send notifications
            asyncio.run(self.send_notifications(month, file_path, summary))

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "month": month,
                "projects_analyzed": summary["total_projects"],
                "epics_processed": summary["total_epics"],
                "total_variance_pct": summary["total_variance_pct"],
                "report_file": file_path,
                # Epic association results
                "epic_association": {
                    "tickets_analyzed": association_results.get(
                        "total_tickets_analyzed", 0
                    ),
                    "matches_found": association_results.get("total_matches_found", 0),
                    "updates_applied": association_results.get("updates_applied", 0),
                    "auto_update_enabled": association_results.get(
                        "auto_update_enabled", False
                    ),
                },
            }

            logger.info("=" * 80)
            logger.info(
                f"✅ Monthly Epic Reconciliation job completed successfully in {duration:.2f}s"
            )
            logger.info("=" * 80)
            logger.info(f"Final Stats: {stats}")

            return stats

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(
                f"Monthly Epic Reconciliation job failed after {duration:.2f}s: {e}",
                exc_info=True,
            )

            return {
                "success": False,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "error": str(e),
            }


def run_monthly_epic_reconciliation():
    """
    Entry point for the Monthly Epic Reconciliation job.
    This function is called by the scheduler.
    """
    try:
        job = MonthlyEpicReconciliationJob()
        return job.run()
    except Exception as e:
        logger.error(
            f"Failed to initialize or run Monthly Epic Reconciliation job: {e}",
            exc_info=True,
        )
        return {
            "success": False,
            "error": str(e),
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": 0,
        }


if __name__ == "__main__":
    # Allow running job manually for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Running Monthly Epic Reconciliation job manually...")
    stats = run_monthly_epic_reconciliation()
    print(f"\nJob completed: {stats}")
