"""Weekly hours tracking report agent for project forecasting."""

import logging
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class HoursReportAgent:
    """Agent for generating weekly project hours tracking reports."""

    def __init__(self, jira_client, notification_manager, database_url: str):
        """Initialize the hours report agent."""
        self.jira_client = jira_client
        self.notification_manager = notification_manager
        self.database_url = database_url

    def calculate_month_progress(self, current_date: datetime = None) -> float:
        """Calculate how much of the current month has passed (0.0 to 1.0)."""
        if current_date is None:
            current_date = datetime.now()

        year = current_date.year
        month = current_date.month
        day = current_date.day

        # Get the total number of days in the month
        _, total_days = monthrange(year, month)

        # Calculate progress
        return min(day / total_days, 1.0)

    def get_active_projects(self) -> List[Dict]:
        """Get all active projects with forecasted hours."""
        from sqlalchemy import create_engine, text

        engine = create_engine(self.database_url)
        projects = []

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT p.key, p.name, pmf.forecasted_hours, p.is_active
                FROM projects p
                INNER JOIN project_monthly_forecast pmf
                    ON p.key = pmf.project_key
                    AND pmf.month_year = DATE_TRUNC('month', CURRENT_DATE)
                WHERE p.is_active = 1 AND pmf.forecasted_hours > 0
            """))

            for row in result:
                projects.append({
                    'key': row[0],
                    'name': row[1],
                    'forecasted_hours': float(row[2]),
                    'is_active': bool(row[3])
                })

        return projects

    async def get_project_hours_this_month(self, project_key: str) -> float:
        """Get total hours logged for a project in the current month."""
        current_date = datetime.now()
        start_of_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = current_date

        logger.info(f"Getting hours for project {project_key} from {start_of_month.strftime('%Y-%m-%d')} to {end_of_month.strftime('%Y-%m-%d')}")

        try:
            # Use Tempo MCP for accurate time tracking data
            logger.info(f"Using Tempo MCP API for project {project_key}")
            return await self._get_hours_via_tempo_mcp(project_key, start_of_month, end_of_month)

        except Exception as e:
            logger.error(f"Error getting hours for project {project_key}: {e}")
            # Fallback to Jira search if Tempo fails
            logger.info(f"Falling back to Jira search API for project {project_key}")
            return await self._get_hours_via_jira_search(project_key, start_of_month, end_of_month)

    async def _get_hours_via_jira_search(self, project_key: str, start_date: datetime, end_date: datetime) -> float:
        """Fallback method to get hours via Jira issue search."""
        try:
            # Search for issues updated in the current month
            jql = f"project = {project_key} AND worklogDate >= '{start_date.strftime('%Y-%m-%d')}' AND worklogDate <= '{end_date.strftime('%Y-%m-%d')}'"
            logger.info(f"Jira search fallback for {project_key} with JQL: {jql}")

            issues = await self.jira_client.search_tickets(jql, max_results=1000)
            logger.info(f"Jira search returned {len(issues)} issues for project {project_key}")

            total_hours = 0
            worklog_count = 0
            for issue in issues:
                issue_key = issue.get('key', 'Unknown')
                worklog = issue.get('fields', {}).get('worklog', {})
                for log_entry in worklog.get('worklogs', []):
                    log_date = datetime.strptime(log_entry['started'][:10], '%Y-%m-%d')
                    if start_date <= log_date <= end_date:
                        hours = log_entry.get('timeSpentSeconds', 0) / 3600
                        total_hours += hours
                        worklog_count += 1
                        # Log first few worklogs for debugging
                        if worklog_count <= 5:
                            logger.info(f"Sample worklog in {issue_key}: {log_entry.get('timeSpentSeconds', 0)} seconds = {hours} hours on {log_date.strftime('%Y-%m-%d')} by {log_entry.get('author', {}).get('displayName', 'Unknown')}")
                        else:
                            logger.debug(f"Found worklog in {issue_key}: {log_entry.get('timeSpentSeconds', 0)} seconds = {hours} hours on {log_date.strftime('%Y-%m-%d')}")

            logger.info(f"Jira search fallback for {project_key}: found {worklog_count} worklogs totaling {total_hours} hours")
            return total_hours

        except Exception as e:
            logger.error(f"Error in fallback hours calculation for {project_key}: {e}")
            return 0.0

    async def _get_hours_via_tempo_mcp(self, project_key: str, start_date: datetime, end_date: datetime) -> float:
        """Get hours using Tempo MCP API for accurate time tracking."""
        try:
            # We'll need to call the MCP function directly from the web interface layer
            # For now, raise an exception to trigger the fallback while we implement this properly
            raise NotImplementedError("Tempo MCP integration needs to be called from the web interface layer")

        except Exception as e:
            logger.error(f"Error in Tempo MCP hours calculation for {project_key}: {e}")
            raise  # Re-raise to trigger fallback

    def calculate_usage_percentage(self, actual_hours: float, forecasted_hours: float, month_progress: float) -> float:
        """Calculate the percentage of forecasted hours used."""
        if forecasted_hours <= 0:
            return 0.0

        expected_hours = forecasted_hours * month_progress
        if expected_hours <= 0:
            return 0.0

        return (actual_hours / expected_hours) * 100

    def get_project_subscribers(self, project_key: str) -> List[str]:
        """Get list of email addresses subscribed to project updates."""
        from sqlalchemy import create_engine, text

        engine = create_engine(self.database_url)
        subscribers = []

        with engine.connect() as conn:
            # Get users who have selected this project
            result = conn.execute(text("""
                SELECT email FROM user_preferences
                WHERE json_extract(selected_projects, '$') LIKE :project_search
            """), {"project_search": f'%"{project_key}"%'})

            for row in result:
                subscribers.append(row[0])

        return subscribers

    async def generate_project_report(self, project: Dict) -> Dict:
        """Generate a report for a single project."""
        project_key = project['key']
        project_name = project['name']
        forecasted_hours = project['forecasted_hours']

        # Get actual hours for this month
        actual_hours = await self.get_project_hours_this_month(project_key)

        # Calculate month progress
        month_progress = self.calculate_month_progress()

        # Calculate usage percentage
        usage_percentage = self.calculate_usage_percentage(actual_hours, forecasted_hours, month_progress)

        # Calculate expected hours based on time passed
        expected_hours = forecasted_hours * month_progress

        # Determine status
        status = "on_track"
        if usage_percentage > 110:
            status = "over_budget"
        elif usage_percentage < 80 and month_progress > 0.5:
            status = "under_utilized"

        return {
            'project_key': project_key,
            'project_name': project_name,
            'forecasted_hours': forecasted_hours,
            'actual_hours': actual_hours,
            'expected_hours': expected_hours,
            'usage_percentage': usage_percentage,
            'month_progress': month_progress * 100,
            'status': status,
            'subscribers': self.get_project_subscribers(project_key)
        }

    async def generate_weekly_reports(self) -> List[Dict]:
        """Generate weekly reports for all active projects."""
        logger.info("Starting weekly hours tracking report generation")

        active_projects = self.get_active_projects()
        reports = []

        for project in active_projects:
            try:
                report = await self.generate_project_report(project)
                reports.append(report)
                logger.info(f"Generated report for project {project['key']}: {report['usage_percentage']:.1f}% usage")
            except Exception as e:
                logger.error(f"Error generating report for project {project['key']}: {e}")

        return reports

    def format_report_email(self, report: Dict) -> str:
        """Format a project report as an email body."""
        project_name = report['project_name']
        project_key = report['project_key']
        usage_percentage = report['usage_percentage']
        actual_hours = report['actual_hours']
        forecasted_hours = report['forecasted_hours']
        expected_hours = report['expected_hours']
        month_progress = report['month_progress']
        status = report['status']

        # Status emoji and message
        status_info = {
            'on_track': {'emoji': '✅', 'message': 'On Track'},
            'over_budget': {'emoji': '⚠️', 'message': 'Over Budget'},
            'under_utilized': {'emoji': '📉', 'message': 'Under Utilized'}
        }

        status_display = status_info.get(status, {'emoji': '📊', 'message': 'Unknown'})

        email_body = f"""
<h2>{status_display['emoji']} {project_name} ({project_key}) - Weekly Hours Report</h2>

<h3>📊 Summary</h3>
<ul>
    <li><strong>Status:</strong> {status_display['message']}</li>
    <li><strong>Month Progress:</strong> {month_progress:.1f}%</li>
    <li><strong>Usage:</strong> {usage_percentage:.1f}% of expected hours</li>
</ul>

<h3>⏱️ Hours Breakdown</h3>
<ul>
    <li><strong>Actual Hours This Month:</strong> {actual_hours:.1f}h</li>
    <li><strong>Expected Hours (based on {month_progress:.1f}% of month):</strong> {expected_hours:.1f}h</li>
    <li><strong>Total Forecasted for Month:</strong> {forecasted_hours:.1f}h</li>
    <li><strong>Remaining Budget:</strong> {forecasted_hours - actual_hours:.1f}h</li>
</ul>

<h3>💡 Insights</h3>
"""

        if status == 'over_budget':
            email_body += f"""
<p style="color: #ff6b35;">🚨 <strong>Action Required:</strong> This project is using hours faster than expected.
Consider reviewing scope or timeline to stay within budget.</p>
"""
        elif status == 'under_utilized':
            email_body += f"""
<p style="color: #ffa500;">⚠️ <strong>Note:</strong> This project appears to be under-utilized.
Consider reallocating resources or reviewing project priorities.</p>
"""
        else:
            email_body += f"""
<p style="color: #28a745;">✅ This project is tracking well against the forecasted hours.</p>
"""

        email_body += f"""
<hr>
<p><small>This is an automated weekly report from the PM Agent.
Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}.</small></p>
"""

        return email_body

    async def send_weekly_reports(self) -> Dict:
        """Send weekly reports to all project subscribers."""
        reports = await self.generate_weekly_reports()
        sent_count = 0
        error_count = 0

        for report in reports:
            subscribers = report['subscribers']
            if not subscribers:
                logger.info(f"No subscribers for project {report['project_key']}, skipping email")
                continue

            try:
                # Format email
                email_subject = f"Weekly Hours Report: {report['project_name']} ({report['usage_percentage']:.1f}% usage)"
                email_body = self.format_report_email(report)

                # Send to all subscribers
                for email in subscribers:
                    try:
                        await self.notification_manager.send_email(
                            to_email=email,
                            subject=email_subject,
                            body=email_body,
                            is_html=True
                        )
                        sent_count += 1
                        logger.info(f"Sent weekly report for {report['project_key']} to {email}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error sending email to {email} for project {report['project_key']}: {e}")

            except Exception as e:
                error_count += 1
                logger.error(f"Error sending reports for project {report['project_key']}: {e}")

        logger.info(f"Weekly reports completed: {sent_count} sent, {error_count} errors")

        return {
            'total_projects': len(reports),
            'emails_sent': sent_count,
            'errors': error_count,
            'reports': reports
        }