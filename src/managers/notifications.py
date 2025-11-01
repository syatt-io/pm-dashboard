"""Notification system for sending updates via Slack, Email, and Teams."""

import logging
import smtplib
import asyncio
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


logger = logging.getLogger(__name__)


@dataclass
class NotificationContent:
    """Content for notifications."""
    title: str
    body: str
    priority: str = "normal"  # normal, high, urgent
    items: Optional[List[Dict[str, Any]]] = None
    footer: Optional[str] = None


class NotificationManager:
    """Manages notifications across multiple channels."""

    def __init__(self, config):
        """Initialize with notification configuration."""
        self.config = config
        self.slack_client = None
        self.smtp_config = None
        self.teams_webhook = None

        # Test mode configuration for meeting emails
        self.meeting_email_test_mode = os.getenv("MEETING_EMAIL_TEST_MODE", "false").lower() == "true"
        self.meeting_email_test_recipient = os.getenv("MEETING_EMAIL_TEST_RECIPIENT", "")

        if self.meeting_email_test_mode:
            logger.warning(
                f"⚠️  MEETING EMAIL TEST MODE ENABLED - All meeting analysis emails will be sent ONLY to: {self.meeting_email_test_recipient}"
            )

        self._setup_channels()

    def _setup_channels(self):
        """Set up notification channels based on configuration."""
        # Setup Slack - Read from config if available, otherwise from environment
        slack_token = self.config.slack_bot_token if self.config and hasattr(self.config, 'slack_bot_token') else os.getenv("SLACK_BOT_TOKEN")
        if slack_token:
            self.slack_client = WebClient(token=slack_token)
            logger.info("Slack notification channel configured")

        # Setup Email - Read from config if available, otherwise from environment
        smtp_host = self.config.smtp_host if self.config and hasattr(self.config, 'smtp_host') else os.getenv("SMTP_HOST")
        smtp_user = self.config.smtp_user if self.config and hasattr(self.config, 'smtp_user') else os.getenv("SMTP_USER")
        smtp_password = self.config.smtp_password if self.config and hasattr(self.config, 'smtp_password') else os.getenv("SMTP_PASSWORD")
        smtp_port = self.config.smtp_port if self.config and hasattr(self.config, 'smtp_port') else int(os.getenv("SMTP_PORT", "587"))

        if all([smtp_host, smtp_user, smtp_password]):
            self.smtp_config = {
                "host": smtp_host,
                "port": smtp_port,
                "user": smtp_user,
                "password": smtp_password,
                "from_email": os.getenv("SMTP_FROM_EMAIL", smtp_user),
                "from_name": os.getenv("SMTP_FROM_NAME", "PM Agent")
            }
            logger.info("Email notification channel configured")

        # Setup Teams - Read from config if available, otherwise from environment
        teams_webhook = self.config.teams_webhook_url if self.config and hasattr(self.config, 'teams_webhook_url') else os.getenv("TEAMS_WEBHOOK_URL")
        if teams_webhook:
            self.teams_webhook = teams_webhook
            logger.info("Teams notification channel configured")

    async def send_notification(self, content: NotificationContent, channels: List[str] = None):
        """Send notification to specified channels."""
        channels = channels or ["slack", "email"]
        results = {}

        tasks = []
        if "slack" in channels and self.slack_client:
            tasks.append(self._send_slack(content))

        if "email" in channels and self.smtp_config:
            tasks.append(self._send_email(content))

        if "teams" in channels and self.teams_webhook:
            tasks.append(self._send_teams(content))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def _send_slack(self, content: NotificationContent) -> Dict[str, Any]:
        """Send notification to Slack."""
        def _send_slack_sync():
            """Synchronous Slack sending (runs in executor)."""
            try:
                # Determine channel based on priority - Read from config if available, otherwise from environment
                urgent_channel = self.config.slack_urgent_channel if self.config and hasattr(self.config, 'slack_urgent_channel') else os.getenv("SLACK_URGENT_CHANNEL")
                default_channel = self.config.slack_channel if self.config and hasattr(self.config, 'slack_channel') else os.getenv("SLACK_CHANNEL", "#general")
                channel_name = urgent_channel if content.priority == "urgent" else default_channel

                # Convert channel name to ID if it starts with # (channel name)
                # Slack API requires channel IDs, not names
                if channel_name.startswith('#'):
                    # Try to resolve channel name to ID using conversations.list
                    try:
                        response = self.slack_client.conversations_list(
                            types="public_channel,private_channel",
                            exclude_archived=True
                        )
                        clean_name = channel_name.lstrip('#')
                        for ch in response.get('channels', []):
                            if ch['name'] == clean_name:
                                channel = ch['id']
                                logger.info(f"Resolved Slack channel '{channel_name}' to ID '{channel}'")
                                break
                        else:
                            # Channel not found, use name as-is (will likely fail but with clear error)
                            channel = channel_name
                            logger.warning(f"Could not resolve channel '{channel_name}' to ID, using as-is")
                    except Exception as e:
                        logger.warning(f"Error resolving channel name '{channel_name}': {e}, using as-is")
                        channel = channel_name
                else:
                    # Already a channel ID or no # prefix
                    channel = channel_name

                # Build message blocks
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": content.title
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": content.body
                        }
                    }
                ]

                # Add items if present
                if content.items:
                    items_text = "\n".join([f"• {item.get('title', item)}" for item in content.items[:10]])
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": items_text
                        }
                    })

                # Add footer if present
                if content.footer:
                    blocks.append({
                        "type": "context",
                        "elements": [{
                            "type": "plain_text",
                            "text": content.footer
                        }]
                    })

                response = self.slack_client.chat_postMessage(
                    channel=channel,
                    blocks=blocks,
                    text=content.title  # Fallback text
                )
                return {"success": True, "channel": "slack", "message_id": response["ts"]}

            except SlackApiError as e:
                logger.error(f"Slack API error: {e}")
                return {"success": False, "channel": "slack", "error": str(e)}
            except Exception as e:
                logger.error(f"Error sending Slack notification: {e}")
                return {"success": False, "channel": "slack", "error": str(e)}

        # Run synchronous Slack API calls in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_slack_sync)

    async def _send_email(self, content: NotificationContent) -> Dict[str, Any]:
        """Send notification via email."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[PM Agent] {content.title}"
            msg["From"] = f"{self.smtp_config['from_name']} <{self.smtp_config['from_email']}>"
            msg["To"] = self.smtp_config["user"]  # Send to self by default

            # Create HTML version
            html_body = f"""
            <html>
                <body>
                    <h2>{content.title}</h2>
                    <p>{content.body}</p>
            """

            if content.items:
                html_body += "<ul>"
                for item in content.items[:10]:
                    title = item.get("title", item) if isinstance(item, dict) else str(item)
                    html_body += f"<li>{title}</li>"
                html_body += "</ul>"

            if content.footer:
                html_body += f"<hr><p><small>{content.footer}</small></p>"

            html_body += """
                </body>
            </html>
            """

            part = MIMEText(html_body, "html")
            msg.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"]) as server:
                server.starttls()
                server.login(self.smtp_config["user"], self.smtp_config["password"])
                server.send_message(msg)

            return {"success": True, "channel": "email"}

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {"success": False, "channel": "email", "error": str(e)}

    async def _send_teams(self, content: NotificationContent) -> Dict[str, Any]:
        """Send notification to Microsoft Teams."""
        try:
            # Build Teams message card
            card = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": content.title,
                "themeColor": "0078D4" if content.priority == "normal" else "FF0000",
                "title": content.title,
                "text": content.body,
                "sections": []
            }

            # Add items section if present
            if content.items:
                facts = []
                for item in content.items[:10]:
                    if isinstance(item, dict):
                        facts.append({
                            "name": item.get("title", "Item"),
                            "value": item.get("description", "")[:100]
                        })
                    else:
                        facts.append({"name": "Item", "value": str(item)[:100]})

                card["sections"].append({
                    "title": "Action Items",
                    "facts": facts
                })

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.teams_webhook,
                    json=card,
                    timeout=10
                )
                response.raise_for_status()

            return {"success": True, "channel": "teams"}

        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}")
            return {"success": False, "channel": "teams", "error": str(e)}

    async def send_daily_digest(self, todos: List[Dict], overdue: List[Dict], due_today: List[Dict]):
        """Send daily digest notification."""
        # Build digest content
        body = f"*Daily PM Digest for {datetime.now().strftime('%B %d, %Y')}*\n\n"

        if overdue:
            body += f"🚨 *{len(overdue)} Overdue Items*\n"

        if due_today:
            body += f"📅 *{len(due_today)} Due Today*\n"

        if todos:
            body += f"📝 *{len(todos)} Open TODOs*\n"

        content = NotificationContent(
            title="Daily PM Digest",
            body=body,
            priority="high" if overdue else "normal",
            items=overdue[:5] + due_today[:5] + todos[:5],
            footer=f"Generated at {datetime.now().strftime('%I:%M %p')}"
        )

        await self.send_notification(content, channels=["slack", "email", "teams"])

    async def send_urgent_notification(self, title: str, message: str, ticket_info: Dict = None):
        """Send urgent notification immediately."""
        body = f"⚠️ *URGENT* ⚠️\n\n{message}"

        if ticket_info:
            body += f"\n\n*Ticket*: {ticket_info.get('key', 'Unknown')}"
            body += f"\n*Summary*: {ticket_info.get('summary', 'N/A')}"
            body += f"\n*Assignee*: {ticket_info.get('assignee', 'Unassigned')}"

        content = NotificationContent(
            title=title,
            body=body,
            priority="urgent",
            footer="This is an urgent notification requiring immediate attention"
        )

        await self.send_notification(content, channels=["slack", "email", "teams"])

    async def send_meeting_processed_notification(self, meeting_title: str, action_items_count: int,
                                                 tickets_created: List[str]):
        """Send notification when a meeting has been processed."""
        body = f"Meeting *{meeting_title}* has been processed.\n\n"
        body += f"• {action_items_count} action items identified\n"
        body += f"• {len(tickets_created)} Jira tickets created\n"

        if tickets_created:
            body += "\n*Created Tickets:*\n"
            for ticket in tickets_created[:5]:
                body += f"• {ticket}\n"

        content = NotificationContent(
            title="Meeting Processed",
            body=body,
            priority="normal",
            footer=f"Processed at {datetime.now().strftime('%I:%M %p')}"
        )

        await self.send_notification(content, channels=["slack"])

    async def send_meeting_analysis_email(
        self,
        meeting_title: str,
        meeting_date: datetime,
        recipients: List[str],
        topics: List[Dict],  # New: List of topic sections with title and content_items
        action_items: List[Dict]
    ) -> Dict[str, Any]:
        """
        Send meeting analysis email to participants.

        Args:
            meeting_title: Title of the meeting
            meeting_date: Date when meeting occurred
            recipients: List of email addresses to send to
            topics: List of topic sections (each with title and content_items)
            action_items: List of action items from analysis

        Returns:
            Dict with success status and details
        """
        if not self.smtp_config:
            logger.error("SMTP not configured, cannot send meeting analysis email")
            return {"success": False, "error": "SMTP not configured"}

        if not recipients:
            logger.warning("No recipients provided for meeting analysis email")
            return {"success": False, "error": "No recipients provided"}

        # Apply test mode override if enabled
        original_recipients = recipients.copy()
        if self.meeting_email_test_mode:
            if not self.meeting_email_test_recipient:
                logger.error("Test mode enabled but no test recipient configured")
                return {"success": False, "error": "Test mode enabled but MEETING_EMAIL_TEST_RECIPIENT not set"}

            logger.info(
                f"🧪 Test mode active - Redirecting email from {recipients} to {self.meeting_email_test_recipient}"
            )
            recipients = [self.meeting_email_test_recipient]

        try:
            # Build HTML email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Meeting Analysis: {meeting_title}"
            msg["From"] = f"{self.smtp_config['from_name']} <{self.smtp_config['from_email']}>"
            msg["To"] = ", ".join(recipients)

            # Create HTML body with test mode banner if needed
            test_mode_banner = ""
            if self.meeting_email_test_mode:
                test_mode_banner = f"""
                <div style="background-color: #fff3cd; border: 2px solid #ffc107; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
                    <h3 style="color: #856404; margin: 0 0 10px 0;">🧪 TEST MODE - Email Redirected</h3>
                    <p style="color: #856404; margin: 0;">
                        <strong>Original Recipients:</strong> {", ".join(original_recipients)}<br>
                        <strong>Actual Recipient:</strong> {self.meeting_email_test_recipient}
                    </p>
                </div>
                """

            html_body = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                        h1 {{ color: #554DFF; }}
                        h2 {{ color: #666; border-bottom: 2px solid #554DFF; padding-bottom: 5px; }}
                        h3 {{ color: #777; margin-top: 15px; margin-bottom: 10px; font-size: 1.1em; }}
                        .section {{ margin: 20px 0; }}
                        .topic-section {{ margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #00FFCE; }}
                        .action-item {{ background-color: #f8f9fa; padding: 10px; margin: 10px 0; border-left: 4px solid #554DFF; }}
                        .action-title {{ font-weight: bold; color: #554DFF; }}
                        ul {{ list-style-type: none; padding-left: 0; }}
                        li {{ padding: 5px 0; padding-left: 20px; }}
                        li:before {{ content: "▸ "; color: #554DFF; font-weight: bold; margin-left: -20px; }}
                        .sub-item {{ padding-left: 40px; }}
                        .sub-item:before {{ content: "• "; color: #00FFCE; font-weight: bold; margin-left: -20px; }}
                        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 0.9em; color: #666; }}
                    </style>
                </head>
                <body>
                    {test_mode_banner}

                    <h1>📊 Meeting Analysis: {meeting_title}</h1>
                    <p><strong>Date:</strong> {meeting_date.strftime("%B %d, %Y at %I:%M %p")}</p>

                    <div class="section">
                        <h2>Discussion Topics</h2>
            """

            # Add topics sections
            if topics:
                for topic in topics:
                    topic_title = topic.get("title", "Untitled Topic")
                    content_items = topic.get("content_items", [])

                    html_body += f"""
                        <div class="topic-section">
                            <h3>{topic_title}</h3>
                            <ul>
                    """

                    for item in content_items:
                        # Check if this is a sub-item (starts with "  * ")
                        if item.startswith("  * "):
                            # Sub-bullet point
                            html_body += f'<li class="sub-item">{item[4:]}</li>'
                        else:
                            # Main bullet point
                            html_body += f'<li>{item}</li>'

                    html_body += """
                            </ul>
                        </div>
                    """
            else:
                html_body += "<p>No topics identified.</p>"

            # Add action items
            html_body += f"""
                    </div>
                    <div class="section">
                        <h2>Action Items ({len(action_items)})</h2>
            """
            if action_items:
                for item in action_items:
                    assignee = item.get("assignee", "Unassigned")
                    priority = item.get("priority", "Medium")
                    html_body += f"""
                        <div class="action-item">
                            <div class="action-title">{item.get("title", "Untitled")}</div>
                            <p>{item.get("description", "No description")}</p>
                            <p><strong>Assignee:</strong> {assignee} | <strong>Priority:</strong> {priority}</p>
                        </div>
                    """
            else:
                html_body += "<p>No action items identified.</p>"

            # Add footer
            html_body += f"""
                    </div>
                    <div class="footer">
                        <p>This meeting analysis was automatically generated by the PM Agent.</p>
                        <p>Analysis completed on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
                    </div>
                </body>
            </html>
            """

            part = MIMEText(html_body, "html")
            msg.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"]) as server:
                server.starttls()
                server.login(self.smtp_config["user"], self.smtp_config["password"])
                server.send_message(msg)

            logger.info(
                f"✅ Meeting analysis email sent to {', '.join(recipients)} for meeting: {meeting_title}"
            )

            return {
                "success": True,
                "recipients": recipients,
                "original_recipients": original_recipients if self.meeting_email_test_mode else recipients,
                "test_mode": self.meeting_email_test_mode
            }

        except Exception as e:
            logger.error(f"Error sending meeting analysis email: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def test_channels(self) -> Dict[str, bool]:
        """Test all configured notification channels."""
        content = NotificationContent(
            title="PM Agent Test Notification",
            body="This is a test notification from the PM Agent. If you receive this, the channel is working correctly.",
            priority="normal",
            footer="Test notification - please ignore"
        )

        results = await self.send_notification(content, channels=["slack", "email", "teams"])

        return {
            "slack": results[0]["success"] if len(results) > 0 else False,
            "email": results[1]["success"] if len(results) > 1 else False,
            "teams": results[2]["success"] if len(results) > 2 else False
        }