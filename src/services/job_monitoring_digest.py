"""Job monitoring digest service for daily summary reports.

This service generates comprehensive daily/weekly summaries of job execution
data for email/Slack reporting, replacing individual job notifications.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.models.job_execution import JobExecution
from src.config.job_monitoring_config import (
    get_job_config,
    get_all_categories,
    JOBS,
    ALERT_CONFIG
)

logger = logging.getLogger(__name__)


class JobMonitoringDigestService:
    """Generates daily/weekly digest reports for job monitoring."""

    def __init__(self, db_session: Session):
        """Initialize digest service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def generate_daily_digest(
        self,
        hours_back: int = 24,
        include_successful: bool = True
    ) -> Dict[str, Any]:
        """Generate daily digest report for the last N hours.

        Args:
            hours_back: Number of hours to look back (default: 24)
            include_successful: Include successful jobs in report (default: True)

        Returns:
            Dict with digest data including:
                - summary: Overall statistics
                - by_category: Breakdown by job category
                - failures: List of failed jobs with details
                - slow_jobs: Jobs that exceeded expected duration
                - recommendations: Suggested actions
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        # Query all executions in the time window
        executions = self.db_session.query(JobExecution).filter(
            JobExecution.started_at >= cutoff_time
        ).order_by(JobExecution.started_at.desc()).all()

        logger.info(f"Generating digest for {len(executions)} executions from last {hours_back} hours")

        # Calculate overall statistics
        total_executions = len(executions)
        successful = sum(1 for e in executions if e.status == 'success')
        failed = sum(1 for e in executions if e.status in ('failed', 'timeout', 'cancelled'))
        running = sum(1 for e in executions if e.status == 'running')

        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0

        # Group by category
        by_category = self._group_by_category(executions)

        # Identify failures
        failures = self._get_failures(executions)

        # Identify slow jobs
        slow_jobs = self._get_slow_jobs(executions)

        # Generate recommendations
        recommendations = self._generate_recommendations(failures, slow_jobs, success_rate)

        # Build digest
        digest = {
            'summary': {
                'period_hours': hours_back,
                'period_start': cutoff_time.isoformat(),
                'period_end': datetime.now(timezone.utc).isoformat(),
                'total_executions': total_executions,
                'successful': successful,
                'failed': failed,
                'running': running,
                'success_rate': round(success_rate, 1)
            },
            'by_category': by_category,
            'failures': failures if failures else [],
            'slow_jobs': slow_jobs if slow_jobs else [],
            'recommendations': recommendations
        }

        return digest

    def _group_by_category(self, executions: List[JobExecution]) -> Dict[str, Dict[str, Any]]:
        """Group executions by job category with statistics.

        Args:
            executions: List of JobExecution records

        Returns:
            Dict mapping category name to statistics
        """
        category_stats = defaultdict(lambda: {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'running': 0,
            'jobs': set()
        })

        for execution in executions:
            category = execution.job_category
            stats = category_stats[category]

            stats['total'] += 1
            stats['jobs'].add(execution.job_name)

            if execution.status == 'success':
                stats['successful'] += 1
            elif execution.status in ('failed', 'timeout', 'cancelled'):
                stats['failed'] += 1
            elif execution.status == 'running':
                stats['running'] += 1

        # Convert sets to counts and calculate success rates
        result = {}
        for category, stats in category_stats.items():
            stats['unique_jobs'] = len(stats['jobs'])
            del stats['jobs']  # Remove set before returning

            stats['success_rate'] = (
                round(stats['successful'] / stats['total'] * 100, 1)
                if stats['total'] > 0 else 0
            )

            result[category] = stats

        return result

    def _get_failures(self, executions: List[JobExecution]) -> List[Dict[str, Any]]:
        """Extract failed jobs with details.

        Args:
            executions: List of JobExecution records

        Returns:
            List of failure details sorted by priority
        """
        failures = []

        for execution in executions:
            if execution.status not in ('failed', 'timeout', 'cancelled'):
                continue

            # Get job config for priority
            try:
                job_config = get_job_config(execution.job_name)
                priority = job_config.priority
                alert_on_failure = job_config.alert_on_failure
            except KeyError:
                priority = 'normal'
                alert_on_failure = False

            failure = {
                'job_name': execution.job_name,
                'category': execution.job_category,
                'priority': priority,
                'status': execution.status,
                'started_at': execution.started_at.isoformat(),
                'duration_seconds': execution.duration_seconds,
                'error_message': execution.error_message[:500] if execution.error_message else None,
                'retry_count': execution.retry_count,
                'task_id': execution.task_id,
                'alert_on_failure': alert_on_failure
            }

            failures.append(failure)

        # Sort by priority (critical first) then by time
        priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        failures.sort(key=lambda f: (
            priority_order.get(f['priority'], 4),
            f['started_at']
        ), reverse=True)

        return failures

    def _get_slow_jobs(self, executions: List[JobExecution]) -> List[Dict[str, Any]]:
        """Identify jobs that exceeded expected duration.

        Args:
            executions: List of JobExecution records

        Returns:
            List of slow job details
        """
        slow_jobs = []

        for execution in executions:
            if execution.status != 'success' or not execution.duration_seconds:
                continue

            try:
                job_config = get_job_config(execution.job_name)
                expected_duration = job_config.expected_duration_seconds
            except KeyError:
                continue

            # Check if job took longer than expected
            threshold = ALERT_CONFIG.get('slow_job_threshold', 1.5)
            if execution.duration_seconds > (expected_duration * threshold):
                slow_job = {
                    'job_name': execution.job_name,
                    'category': execution.job_category,
                    'expected_duration': expected_duration,
                    'actual_duration': execution.duration_seconds,
                    'slowdown_factor': round(execution.duration_seconds / expected_duration, 1),
                    'started_at': execution.started_at.isoformat()
                }
                slow_jobs.append(slow_job)

        # Sort by slowdown factor (worst first)
        slow_jobs.sort(key=lambda j: j['slowdown_factor'], reverse=True)

        return slow_jobs

    def _generate_recommendations(
        self,
        failures: List[Dict[str, Any]],
        slow_jobs: List[Dict[str, Any]],
        success_rate: float
    ) -> List[str]:
        """Generate actionable recommendations based on job execution data.

        Args:
            failures: List of failed jobs
            slow_jobs: List of slow jobs
            success_rate: Overall success rate percentage

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Critical failures
        critical_failures = [f for f in failures if f['priority'] == 'critical']
        if critical_failures:
            recommendations.append(
                f"🚨 {len(critical_failures)} CRITICAL job(s) failed - immediate attention required"
            )

        # Overall success rate
        if success_rate < 90:
            recommendations.append(
                f"⚠️ Success rate is {success_rate:.1f}% (below 90% threshold) - review failures"
            )

        # Repeated failures
        failure_counts = defaultdict(int)
        for failure in failures:
            failure_counts[failure['job_name']] += 1

        repeat_offenders = {job: count for job, count in failure_counts.items() if count >= 2}
        if repeat_offenders:
            jobs_list = ', '.join(f"{job} ({count}x)" for job, count in repeat_offenders.items())
            recommendations.append(
                f"🔁 Repeated failures detected: {jobs_list} - may indicate systemic issue"
            )

        # Slow jobs
        if slow_jobs:
            top_slow = slow_jobs[0]
            recommendations.append(
                f"🐌 {len(slow_jobs)} job(s) exceeded expected duration - slowest: "
                f"{top_slow['job_name']} ({top_slow['slowdown_factor']}x slower than expected)"
            )

        # All good
        if not recommendations and success_rate == 100:
            recommendations.append("✅ All jobs executed successfully within expected timeframes")

        return recommendations

    def format_email_body(self, digest: Dict[str, Any]) -> str:
        """Format digest data as HTML email body.

        Args:
            digest: Digest data from generate_daily_digest()

        Returns:
            HTML email body string
        """
        summary = digest['summary']
        by_category = digest['by_category']
        failures = digest['failures']
        slow_jobs = digest['slow_jobs']
        recommendations = digest['recommendations']

        # Build HTML email
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #554DFF 0%, #7D00FF 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .summary {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-size: 32px; font-weight: bold; }}
        .metric-label {{ color: #666; font-size: 12px; text-transform: uppercase; }}
        .success {{ color: #00C853; }}
        .failed {{ color: #D32F2F; }}
        .section {{ margin: 30px 0; }}
        .section-title {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; border-bottom: 2px solid #554DFF; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #554DFF; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .priority-critical {{ background: #FFEBEE; border-left: 4px solid #D32F2F; }}
        .priority-high {{ background: #FFF3E0; border-left: 4px solid #F57C00; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
        .badge-critical {{ background: #D32F2F; color: white; }}
        .badge-high {{ background: #F57C00; color: white; }}
        .badge-normal {{ background: #757575; color: white; }}
        .recommendations {{ background: #E3F2FD; padding: 15px; border-radius: 8px; border-left: 4px solid #2196F3; }}
        .recommendations li {{ margin: 10px 0; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Job Monitoring Daily Digest</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">
            {summary['period_start'][:10]} to {summary['period_end'][:10]} ({summary['period_hours']} hours)
        </p>
    </div>

    <div class="summary">
        <div class="summary-grid">
            <div class="metric">
                <div class="metric-value">{summary['total_executions']}</div>
                <div class="metric-label">Total Executions</div>
            </div>
            <div class="metric">
                <div class="metric-value success">{summary['successful']}</div>
                <div class="metric-label">Successful</div>
            </div>
            <div class="metric">
                <div class="metric-value failed">{summary['failed']}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #554DFF;">{summary['success_rate']}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
        </div>
    </div>
"""

        # Recommendations section
        if recommendations:
            html += """
    <div class="section">
        <div class="section-title">💡 Recommendations</div>
        <div class="recommendations">
            <ul>
"""
            for rec in recommendations:
                html += f"                <li>{rec}</li>\n"
            html += """
            </ul>
        </div>
    </div>
"""

        # Failures section
        if failures:
            html += """
    <div class="section">
        <div class="section-title">❌ Failed Jobs</div>
        <table>
            <thead>
                <tr>
                    <th>Job Name</th>
                    <th>Category</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Error</th>
                    <th>Retries</th>
                </tr>
            </thead>
            <tbody>
"""
            for failure in failures:
                priority_class = f"priority-{failure['priority']}" if failure['priority'] in ['critical', 'high'] else ""
                badge_class = f"badge-{failure['priority']}"
                error_msg = failure['error_message'][:100] if failure['error_message'] else 'N/A'

                html += f"""
                <tr class="{priority_class}">
                    <td><strong>{failure['job_name']}</strong></td>
                    <td>{failure['category']}</td>
                    <td><span class="badge {badge_class}">{failure['priority'].upper()}</span></td>
                    <td>{failure['status']}</td>
                    <td style="font-size: 11px; color: #666;">{error_msg}</td>
                    <td>{failure['retry_count']}</td>
                </tr>
"""
            html += """
            </tbody>
        </table>
    </div>
"""

        # Slow jobs section
        if slow_jobs:
            html += """
    <div class="section">
        <div class="section-title">🐌 Slow Jobs (Exceeded Expected Duration)</div>
        <table>
            <thead>
                <tr>
                    <th>Job Name</th>
                    <th>Category</th>
                    <th>Expected Duration</th>
                    <th>Actual Duration</th>
                    <th>Slowdown Factor</th>
                </tr>
            </thead>
            <tbody>
"""
            for slow_job in slow_jobs:
                html += f"""
                <tr>
                    <td><strong>{slow_job['job_name']}</strong></td>
                    <td>{slow_job['category']}</td>
                    <td>{slow_job['expected_duration']}s</td>
                    <td>{slow_job['actual_duration']}s</td>
                    <td style="color: #F57C00; font-weight: bold;">{slow_job['slowdown_factor']}x</td>
                </tr>
"""
            html += """
            </tbody>
        </table>
    </div>
"""

        # Category breakdown section
        if by_category:
            html += """
    <div class="section">
        <div class="section-title">📁 Breakdown by Category</div>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Total Executions</th>
                    <th>Unique Jobs</th>
                    <th>Successful</th>
                    <th>Failed</th>
                    <th>Success Rate</th>
                </tr>
            </thead>
            <tbody>
"""
            for category, stats in sorted(by_category.items()):
                html += f"""
                <tr>
                    <td><strong>{category}</strong></td>
                    <td>{stats['total']}</td>
                    <td>{stats['unique_jobs']}</td>
                    <td class="success">{stats['successful']}</td>
                    <td class="failed">{stats['failed']}</td>
                    <td>{stats['success_rate']}%</td>
                </tr>
"""
            html += """
            </tbody>
        </table>
    </div>
"""

        # Footer
        html += f"""
    <div class="footer">
        <p>Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p>Agent PM - Job Monitoring System</p>
    </div>
</body>
</html>
"""

        return html

    def format_slack_message(self, digest: Dict[str, Any]) -> str:
        """Format digest data as Slack message (markdown).

        Args:
            digest: Digest data from generate_daily_digest()

        Returns:
            Slack-formatted markdown string
        """
        summary = digest['summary']
        by_category = digest['by_category']
        failures = digest['failures']
        slow_jobs = digest['slow_jobs']
        recommendations = digest['recommendations']

        # Build Slack message
        message = f"""*📊 Job Monitoring Daily Digest*
_{summary['period_start'][:10]} to {summary['period_end'][:10]} ({summary['period_hours']} hours)_

*Summary:*
• Total Executions: {summary['total_executions']}
• Successful: {summary['successful']} ✅
• Failed: {summary['failed']} ❌
• Success Rate: {summary['success_rate']}%

"""

        # Recommendations
        if recommendations:
            message += "*💡 Recommendations:*\n"
            for rec in recommendations:
                message += f"• {rec}\n"
            message += "\n"

        # Failures
        if failures:
            message += f"*❌ Failed Jobs ({len(failures)}):*\n"
            for failure in failures[:5]:  # Show top 5
                priority_emoji = "🚨" if failure['priority'] == 'critical' else "⚠️" if failure['priority'] == 'high' else "ℹ️"
                error_msg = failure['error_message'][:100] if failure['error_message'] else 'N/A'
                message += f"{priority_emoji} `{failure['job_name']}` - {failure['status']}\n"
                message += f"   _{error_msg}_\n"

            if len(failures) > 5:
                message += f"   _...and {len(failures) - 5} more_\n"
            message += "\n"

        # Slow jobs
        if slow_jobs:
            message += f"*🐌 Slow Jobs ({len(slow_jobs)}):*\n"
            for slow_job in slow_jobs[:3]:  # Show top 3
                message += f"• `{slow_job['job_name']}` - {slow_job['slowdown_factor']}x slower than expected\n"
            if len(slow_jobs) > 3:
                message += f"   _...and {len(slow_jobs) - 3} more_\n"
            message += "\n"

        # Category breakdown
        if by_category:
            message += "*📁 By Category:*\n"
            for category, stats in sorted(by_category.items()):
                message += f"• `{category}`: {stats['successful']}/{stats['total']} successful ({stats['success_rate']}%)\n"

        return message
