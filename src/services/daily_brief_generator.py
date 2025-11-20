"""Daily brief generation service for aggregating and formatting insights."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.models import ProactiveInsight, User, UserNotificationPreferences
from src.managers.notifications import NotificationManager
from src.services.notification_preference_checker import NotificationPreferenceChecker
from src.utils.database import get_db
from config.settings import settings
import asyncio

logger = logging.getLogger(__name__)


class DailyBriefGenerator:
    """Service for generating and delivering daily briefs to users."""

    def __init__(self, db: Session):
        """Initialize the daily brief generator.

        Args:
            db: Database session
        """
        self.db = db
        self.notification_manager = NotificationManager(settings)

    def generate_brief_for_user(
        self, user: User, insights: List[ProactiveInsight]
    ) -> Dict[str, Any]:
        """Generate daily brief for a user.

        Args:
            user: User to generate brief for
            insights: List of insights to include

        Returns:
            Dictionary with brief content in multiple formats
        """
        if not insights:
            return {
                "has_content": False,
                "slack_text": None,
                "email_html": None,
                "email_subject": None,
            }

        # Group insights by severity
        critical = [i for i in insights if i.severity == "critical"]
        warning = [i for i in insights if i.severity == "warning"]
        info = [i for i in insights if i.severity == "info"]

        # Limit to top 5 insights (prevent overwhelm)
        top_insights = (critical + warning + info)[:5]

        # Generate Slack format
        slack_text = self._format_slack_brief(
            user, top_insights, critical, warning, info
        )

        # Generate Email format
        email_html = self._format_email_brief(
            user, top_insights, critical, warning, info
        )
        email_subject = f"🌅 Daily Brief - {len(top_insights)} insight{'s' if len(top_insights) != 1 else ''} for you"

        return {
            "has_content": True,
            "slack_text": slack_text,
            "email_html": email_html,
            "email_subject": email_subject,
            "insight_count": len(top_insights),
        }

    def _format_slack_brief(
        self,
        user: User,
        top_insights: List[ProactiveInsight],
        critical: List[ProactiveInsight],
        warning: List[ProactiveInsight],
        info: List[ProactiveInsight],
    ) -> str:
        """Format brief for Slack delivery.

        Args:
            user: User receiving the brief
            top_insights: Top insights to include
            critical: Critical insights
            warning: Warning insights
            info: Info insights

        Returns:
            Formatted Slack message
        """
        lines = [
            f"🌅 *Good morning, {user.name.split()[0]}!* Here's what you need to know:\n"
        ]

        # Critical section
        if critical:
            lines.append("🔴 *CRITICAL*")
            for insight in critical:
                lines.append(f"• {insight.title}")
                lines.append(f"  _{insight.description}_\n")

        # Warning section
        if warning:
            lines.append("🟡 *WARNING*")
            for insight in warning:
                lines.append(f"• {insight.title}")
                lines.append(f"  _{insight.description}_\n")

        # Info section
        if info:
            lines.append("ℹ️ *INFO*")
            for insight in info:
                lines.append(f"• {insight.title}")
                lines.append(f"  _{insight.description}_\n")

        # Footer
        dashboard_url = (
            f"{settings.web.base_url}/insights"
            if hasattr(settings.web, "base_url")
            else None
        )
        if dashboard_url:
            lines.append(f"\n<{dashboard_url}|View details in dashboard>")

        return "\n".join(lines)

    def _format_email_brief(
        self,
        user: User,
        top_insights: List[ProactiveInsight],
        critical: List[ProactiveInsight],
        warning: List[ProactiveInsight],
        info: List[ProactiveInsight],
    ) -> str:
        """Format brief for email delivery.

        Args:
            user: User receiving the brief
            top_insights: Top insights to include
            critical: Critical insights
            warning: Warning insights
            info: Info insights

        Returns:
            Formatted HTML email
        """
        html_parts = [
            """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background: linear-gradient(135deg, #554DFF 0%, #7D00FF 100%);
                             color: white; padding: 20px; border-radius: 8px 8px 0 0; }
                    .content { background: #f9f9f9; padding: 20px; }
                    .insight { background: white; padding: 15px; margin: 10px 0; border-radius: 6px;
                              border-left: 4px solid #ddd; }
                    .critical { border-left-color: #dc3545; }
                    .warning { border-left-color: #ffc107; }
                    .info { border-left-color: #17a2b8; }
                    .insight-title { font-weight: bold; margin-bottom: 8px; }
                    .insight-desc { color: #666; font-size: 14px; }
                    .footer { background: #333; color: white; padding: 15px;
                             border-radius: 0 0 8px 8px; text-align: center; }
                    .button { display: inline-block; padding: 10px 20px; background: #554DFF;
                             color: white; text-decoration: none; border-radius: 4px; margin-top: 10px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🌅 Good Morning, """
            + user.name.split()[0]
            + """!</h1>
                        <p>Here's what you need to know today</p>
                    </div>
                    <div class="content">
            """
        ]

        # Critical insights
        if critical:
            html_parts.append('<h2 style="color: #dc3545;">🔴 Critical</h2>')
            for insight in critical:
                html_parts.append(
                    f"""
                    <div class="insight critical">
                        <div class="insight-title">{insight.title}</div>
                        <div class="insight-desc">{insight.description}</div>
                    </div>
                """
                )

        # Warning insights
        if warning:
            html_parts.append('<h2 style="color: #ffc107;">🟡 Warning</h2>')
            for insight in warning:
                html_parts.append(
                    f"""
                    <div class="insight warning">
                        <div class="insight-title">{insight.title}</div>
                        <div class="insight-desc">{insight.description}</div>
                    </div>
                """
                )

        # Info insights
        if info:
            html_parts.append('<h2 style="color: #17a2b8;">ℹ️ Info</h2>')
            for insight in info:
                html_parts.append(
                    f"""
                    <div class="insight info">
                        <div class="insight-title">{insight.title}</div>
                        <div class="insight-desc">{insight.description}</div>
                    </div>
                """
                )

        # Footer
        dashboard_url = (
            f"{settings.web.base_url}/insights"
            if hasattr(settings.web, "base_url")
            else "#"
        )
        html_parts.append(
            f"""
                    <div style="text-align: center; margin-top: 20px;">
                        <a href="{dashboard_url}" class="button">View Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>Autonomous PM Agent | Powered by AI</p>
                    <p style="font-size: 12px; color: #999;">
                        You're receiving this because you have daily briefs enabled.
                    </p>
                </div>
            </div>
            </body>
            </html>
        """
        )

        return "".join(html_parts)

    def deliver_brief(self, user: User, brief: Dict[str, Any]) -> Dict[str, bool]:
        """Deliver brief to user via configured channels.

        Args:
            user: User to deliver to
            brief: Brief content

        Returns:
            Dictionary with delivery status per channel
        """
        if not brief["has_content"]:
            return {"slack": False, "email": False}

        results = {"slack": False, "email": False}

        # Check user preferences using NotificationPreferenceChecker
        pref_checker = NotificationPreferenceChecker(self.db)

        # Check both category toggle (enable_budget_alerts) AND channel preferences
        deliver_slack = pref_checker.should_send_notification(
            user, "daily_brief", "slack"
        )
        deliver_email = pref_checker.should_send_notification(
            user, "daily_brief", "email"
        )

        # Deliver via Slack
        if deliver_slack and user.slack_user_id:
            try:
                # Run async method synchronously
                result = asyncio.run(
                    self.notification_manager._send_slack_dm(
                        user.slack_user_id, brief["slack_text"]
                    )
                )
                results["slack"] = result.get("success", False)
                if results["slack"]:
                    logger.info(f"Delivered Slack brief to user {user.id}")
                else:
                    logger.error(
                        f"Failed to deliver Slack brief to user {user.id}: {result.get('error')}"
                    )
            except Exception as e:
                logger.error(f"Error delivering Slack brief to user {user.id}: {e}")

        # Deliver via Email
        if deliver_email:
            try:
                # For email, we need to build the proper format
                # NotificationManager's _send_email expects NotificationContent
                from src.managers.notifications import NotificationContent

                # Use SMTP directly for now (simplified)
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart

                smtp_config = self.notification_manager.smtp_config
                if smtp_config:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = brief["email_subject"]
                    msg["From"] = (
                        f"{smtp_config['from_name']} <{smtp_config['from_email']}>"
                    )
                    msg["To"] = user.email

                    part = MIMEText(brief["email_html"], "html")
                    msg.attach(part)

                    with smtplib.SMTP(
                        smtp_config["host"], smtp_config["port"]
                    ) as server:
                        server.starttls()
                        server.login(smtp_config["user"], smtp_config["password"])
                        server.send_message(msg)

                    results["email"] = True
                    logger.info(f"Delivered email brief to user {user.id}")
                else:
                    logger.warning(
                        f"SMTP not configured, cannot send email to user {user.id}"
                    )
            except Exception as e:
                logger.error(f"Error delivering email brief to user {user.id}: {e}")

        return results

    def mark_insights_delivered(
        self, insights: List[ProactiveInsight], via_slack: bool, via_email: bool
    ):
        """Mark insights as delivered.

        Args:
            insights: List of insights that were delivered
            via_slack: Whether delivered via Slack
            via_email: Whether delivered via Email
        """
        now = datetime.now(timezone.utc)

        for insight in insights:
            if via_slack and not insight.delivered_via_slack:
                insight.delivered_via_slack = now
            if via_email and not insight.delivered_via_email:
                insight.delivered_via_email = now

        self.db.commit()
        logger.info(f"Marked {len(insights)} insights as delivered")


def send_daily_briefs(db=None) -> Dict[str, Any]:
    """Send daily briefs to all users.

    This is the main entry point for the scheduled job.

    Args:
        db: Database session to use (optional, for avoiding session conflicts in Celery tasks)

    Returns:
        Dictionary with delivery statistics
    """
    from src.utils.database import get_db
    from src.services.insight_detector import InsightDetector

    stats = {
        "users_processed": 0,
        "briefs_sent_slack": 0,
        "briefs_sent_email": 0,
        "total_insights_delivered": 0,
        "errors": [],
    }

    # Use provided db session or create a new one
    # This prevents connection pool exhaustion when called from Celery tasks
    if db is None:
        db = next(get_db())
        should_close = True
    else:
        should_close = False

    try:
        # Get all active users
        users = db.query(User).filter(User.is_active == True).all()

        for user in users:
            try:
                # Get undelivered insights (excluding meeting_prep which is handled separately)
                detector = InsightDetector(db)
                insights = detector.get_undelivered_insights(
                    user.id, exclude_types=["meeting_prep"]
                )

                if not insights:
                    logger.debug(f"No undelivered insights for user {user.id}")
                    continue

                # Generate brief
                generator = DailyBriefGenerator(db)
                brief = generator.generate_brief_for_user(user, insights)

                if not brief["has_content"]:
                    continue

                # Deliver brief
                delivery_results = generator.deliver_brief(user, brief)

                # Mark insights as delivered
                generator.mark_insights_delivered(
                    insights,
                    via_slack=delivery_results["slack"],
                    via_email=delivery_results["email"],
                )

                # Update stats
                if delivery_results["slack"]:
                    stats["briefs_sent_slack"] += 1
                if delivery_results["email"]:
                    stats["briefs_sent_email"] += 1
                stats["total_insights_delivered"] += len(insights)
                stats["users_processed"] += 1

            except Exception as e:
                logger.error(
                    f"Error sending brief to user {user.id}: {e}", exc_info=True
                )
                stats["errors"].append(f"User {user.id}: {str(e)}")
                continue

        logger.info(f"Daily brief delivery complete: {stats}")

    except Exception as e:
        logger.error(f"Error in daily brief job: {e}", exc_info=True)
        stats["errors"].append(str(e))
    finally:
        # Only close if we created the session
        if should_close:
            db.close()

    return stats
