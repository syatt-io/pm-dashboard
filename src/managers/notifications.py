"""Notification system for sending updates via Slack, Email, and Teams."""

import logging
import smtplib
import asyncio
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

        self._setup_channels()

    def _setup_channels(self):
        """Set up notification channels based on configuration."""
        # Setup Slack
        if self.config.slack_bot_token:
            self.slack_client = WebClient(token=self.config.slack_bot_token)
            logger.info("Slack notification channel configured")

        # Setup Email
        if all([self.config.smtp_host, self.config.smtp_user, self.config.smtp_password]):
            self.smtp_config = {
                "host": self.config.smtp_host,
                "port": self.config.smtp_port,
                "user": self.config.smtp_user,
                "password": self.config.smtp_password
            }
            logger.info("Email notification channel configured")

        # Setup Teams
        if self.config.teams_webhook_url:
            self.teams_webhook = self.config.teams_webhook_url
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
        try:
            # Determine channel based on priority
            channel_name = self.config.slack_urgent_channel if content.priority == "urgent" else self.config.slack_channel

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

    async def _send_email(self, content: NotificationContent) -> Dict[str, Any]:
        """Send notification via email."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[PM Agent] {content.title}"
            msg["From"] = self.smtp_config["user"]
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