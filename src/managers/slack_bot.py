"""Slack bot for TODO management commands."""

import logging
import re
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from config.settings import settings
from src.managers.todo_manager import TodoManager
from src.managers.learning_manager import LearningManager
from src.managers.notifications import NotificationContent


logger = logging.getLogger(__name__)


class SlackTodoBot:
    """Slack bot for managing TODOs via commands."""

    def __init__(self, bot_token: str, signing_secret: str):
        """Initialize Slack bot."""
        self.app = App(
            token=bot_token,
            signing_secret=signing_secret
        )
        self.client = WebClient(token=bot_token)
        self.todo_manager = TodoManager()
        self.learning_manager = LearningManager()
        self.handler = SlackRequestHandler(self.app)

        self._register_commands()
        self._register_listeners()

    def _register_commands(self):
        """Register slash commands."""

        @self.app.command("/todos")
        def handle_todos_command(ack, respond, command):
            """Handle /todos slash command."""
            ack()

            try:
                user_id = command.get('user_id')
                text = command.get('text', '').strip()

                if not text or text == 'help':
                    respond(self._get_help_message())
                    return

                # Parse command
                args = text.split()
                subcommand = args[0].lower()

                if subcommand == 'list':
                    assignee = args[1] if len(args) > 1 and args[1] != 'me' else None
                    if args[1:] and args[1] == 'me':
                        assignee = self._get_user_display_name(user_id)
                    respond(self._list_todos(assignee))

                elif subcommand == 'add':
                    title = ' '.join(args[1:])
                    if title:
                        respond(self._create_todo_interactive(user_id, title))
                    else:
                        respond("❌ Please provide a title: `/todos add Fix the login bug`")

                elif subcommand == 'complete':
                    if len(args) > 1:
                        todo_id = args[1]
                        respond(self._complete_todo(user_id, todo_id))
                    else:
                        respond("❌ Please provide TODO ID: `/todos complete abc123`")

                elif subcommand == 'snooze':
                    if len(args) > 1:
                        todo_id = args[1]
                        days = int(args[2]) if len(args) > 2 else 1
                        respond(self._snooze_todo(user_id, todo_id, days))
                    else:
                        respond("❌ Please provide TODO ID: `/todos snooze abc123 [days]`")

                elif subcommand == 'summary':
                    respond(self._get_summary())

                elif subcommand == 'channels':
                    respond(self._list_channels())

                else:
                    respond(f"❌ Unknown command: `{subcommand}`. Use `/todos help` for available commands.")

            except Exception as e:
                logger.error(f"Error handling /todos command: {e}")
                respond(f"❌ Error processing command: {str(e)}")

        @self.app.command("/todo")
        def handle_todo_command(ack, respond, command):
            """Handle /todo slash command (shorthand)."""
            ack()

            user_id = command.get('user_id')
            text = command.get('text', '').strip()

            if text:
                # Quick create TODO
                respond(self._create_todo_quick(user_id, text))
            else:
                respond("❌ Please provide a TODO title: `/todo Fix the login bug`")

        @self.app.command("/agenda")
        def handle_agenda_command(ack, respond, command):
            """Handle /agenda slash command for project digest generation."""
            ack()

            try:
                user_id = command.get('user_id')
                text = command.get('text', '').strip()

                if not text or text == 'help':
                    respond(self._get_agenda_help_message())
                    return

                # Parse command: /agenda PROJECT-KEY [days]
                args = text.split()
                if len(args) < 1:
                    respond("❌ Please provide a project key: `/agenda PROJ-123 [days]`")
                    return

                project_key = args[0].upper()
                days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 7

                # Validate days range
                if days < 1 or days > 30:
                    respond("❌ Days must be between 1 and 30")
                    return

                respond(self._generate_project_agenda(user_id, project_key, days))

            except Exception as e:
                logger.error(f"Error handling /agenda command: {e}")
                respond(f"❌ Error processing agenda command: {str(e)}")

        @self.app.command("/dadjoke")
        def handle_dadjoke_command(ack, respond, command):
            """Handle /dadjoke slash command for generating dad jokes."""
            ack()

            try:
                user_id = command.get('user_id')
                text = command.get('text', '').strip()
                channel_id = command.get('channel_id')
                user_name = command.get('user_name', 'someone')

                # Parse parameters from text
                subject = None
                person_name = None

                if text:
                    # Parse "about <subject> for <person>" or variations
                    parts = text.lower()

                    # Extract subject (after "about")
                    if 'about ' in parts:
                        about_idx = parts.index('about ') + 6
                        for_idx = parts.find(' for ', about_idx)
                        if for_idx > -1:
                            subject = text[about_idx:for_idx].strip()
                        else:
                            subject = text[about_idx:].strip()

                    # Extract person name (after "for")
                    if ' for ' in parts:
                        for_idx = parts.index(' for ') + 5
                        person_name = text[for_idx:].strip()

                    # If no keywords, treat entire text as subject
                    if not subject and not person_name and text:
                        subject = text

                # Generate and post the dad joke
                joke_response = self._generate_dad_joke(subject, person_name, user_name)

                # Log the joke for debugging
                logger.info(f"Generated joke text: {joke_response[:100]}...")

                # Ensure we have text before posting
                if not joke_response:
                    logger.error("Empty joke response generated")
                    respond("❌ Failed to generate joke - got empty response")
                    return

                # Post in channel
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=joke_response
                )

                # Respond to command (only visible to user)
                respond("Dad joke delivered! 🎭")

            except Exception as e:
                logger.error(f"Error handling /dadjoke command: {e}")
                respond(f"❌ Error generating dad joke: {str(e)}")

        @self.app.command("/learning")
        def handle_learning_command(ack, respond, command):
            """Handle /learning slash command for saving team learnings."""
            ack()

            try:
                user_id = command.get('user_id')
                text = command.get('text', '').strip()

                if not text or text == 'help':
                    respond(self._get_learning_help_message())
                    return

                # Parse command
                args = text.split()
                if not args:
                    respond("❌ Please provide a learning: `/learning Your insight here`")
                    return

                subcommand = args[0].lower()

                # Check for subcommands
                if subcommand == 'list':
                    category = args[1] if len(args) > 1 else None
                    respond(self._list_learnings(category))

                elif subcommand == 'search':
                    if len(args) > 1:
                        search_term = ' '.join(args[1:])
                        respond(self._search_learnings(search_term))
                    else:
                        respond("❌ Please provide search terms: `/learning search API patterns`")

                elif subcommand == 'stats':
                    respond(self._get_learning_stats())

                elif subcommand == 'categories':
                    respond(self._list_categories())

                else:
                    # No subcommand, treat entire text as a learning
                    respond(self._create_learning(user_id, text))

            except Exception as e:
                logger.error(f"Error handling /learning command: {e}")
                respond(f"❌ Error processing learning command: {str(e)}")

        @self.app.command("/feedback")
        def handle_feedback_command(ack, respond, command):
            """Handle /feedback slash command for saving feedback."""
            ack()

            try:
                user_id = command.get('user_id')
                text = command.get('text', '').strip()

                if not text or text == 'help':
                    respond(self._get_feedback_help_message())
                    return

                # Parse command: /feedback @recipient Here is my feedback text
                # Recipient is optional
                recipient = None
                content = text

                # Check if text starts with @mention
                if text.startswith('<@'):
                    # Extract Slack user ID from mention
                    parts = text.split('>', 1)
                    if len(parts) == 2:
                        recipient_id = parts[0].replace('<@', '').strip()
                        # Validate recipient exists in Slack
                        if self._validate_slack_user(recipient_id):
                            recipient = self._get_user_display_name(recipient_id)
                            content = parts[1].strip()
                        else:
                            respond("❌ Invalid recipient. Please use a valid Slack user mention.")
                            return

                # Validate content is not empty
                if not content:
                    respond("❌ Please provide feedback content: `/feedback @user Your feedback here`")
                    return

                # Create the feedback
                respond(self._create_feedback(user_id, recipient, content))

            except Exception as e:
                logger.error(f"Error handling /feedback command: {e}")
                respond(f"❌ Error processing feedback command: {str(e)}")

    def _register_listeners(self):
        """Register message listeners."""

        @self.app.message(re.compile(r".*todo.*", re.IGNORECASE))
        def handle_todo_mention(message, say):
            """Handle messages mentioning 'todo'."""
            user_id = message.get('user')
            text = message.get('text', '').lower()

            # Only respond to direct mentions or DMs
            if f"<@{self.app.client.auth_test()['user_id']}>" in text:
                say(self._get_quick_help())

        @self.app.event("message")
        def handle_channel_message(event, say):
            """Handle all channel messages for monitoring."""
            # Skip bot messages
            if event.get('subtype') == 'bot_message':
                return

            user_id = event.get('user')
            text = event.get('text', '')
            channel = event.get('channel')

            # Log the message for analysis
            logger.info(f"Channel message from {user_id} in {channel}: {text}")

            # You can add logic here to analyze messages and create TODOs
            # For example, detect action items or meeting notes
            self._analyze_message_for_todos(text, user_id, channel)

        @self.app.event("channel_created")
        def handle_channel_created(event):
            """Handle new channel creation."""
            channel = event['channel']
            logger.info(f"New channel created: {channel['name']} ({channel['id']})")

        @self.app.event("channel_deleted")
        def handle_channel_deleted(event):
            """Handle channel deletion."""
            channel = event['channel']
            logger.info(f"Channel deleted: {channel} ")

    def _get_help_message(self) -> Dict[str, Any]:
        """Get help message with all available commands."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📋 TODO Bot Commands"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available Commands:*\n\n"
                           "`/todos list [assignee|me]` - List TODOs\n"
                           "`/todos add <title>` - Create new TODO\n"
                           "`/todos complete <id>` - Mark TODO complete\n"
                           "`/todos snooze <id> [days]` - Snooze TODO\n"
                           "`/todos summary` - Get team summary\n"
                           "`/todos channels` - List available channels\n"
                           "`/todo <title>` - Quick create TODO\n"
                           "`/agenda <project-key> [days]` - Generate project agenda\n"
                           "`/dadjoke [about <topic>] [for <person>]` - Get a dad joke\n"
                           "`/learning <text>` - Save a team learning\n"
                           "`/feedback [@user] <text>` - Save private feedback\n\n"
                           "*Examples:*\n"
                           "• `/todos list me` - My TODOs\n"
                           "• `/todo Fix login bug` - Quick create\n"
                           "• `/todos complete abc123` - Complete TODO\n"
                           "• `/agenda PROJ-123 7` - 7-day project digest\n"
                           "• `/dadjoke` - Random dad joke\n"
                           "• `/dadjoke about coffee` - Coffee-themed joke\n"
                           "• `/dadjoke for Mike` - Joke for Mike"
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": "💡 Tip: Use the web dashboard for advanced editing and filtering"
                }]
            }
        ]

        return {"blocks": blocks}

    def _get_quick_help(self) -> str:
        """Get quick help message for mentions."""
        return ("👋 Hi! I can help manage TODOs. Try:\n"
                "• `/todos list` - See your TODOs\n"
                "• `/todo Fix bug` - Create TODO\n"
                "• `/todos help` - Full command list")

    def _list_todos(self, assignee: Optional[str] = None) -> Dict[str, Any]:
        """List TODOs for user or team."""
        try:
            if assignee:
                todos = self.todo_manager.get_active_todos(assignee=assignee, limit=20)
                title = f"📋 TODOs for {assignee}"
            else:
                todos = self.todo_manager.get_active_todos(limit=20)
                title = "📋 All Active TODOs"

            if not todos:
                return {
                    "text": f"🎉 No active TODOs found" + (f" for {assignee}" if assignee else "") + "!"
                }

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                }
            ]

            # Group TODOs by status
            overdue = []
            due_today = []
            upcoming = []
            no_date = []

            now = datetime.now()
            today = now.date()

            for todo in todos:
                if todo.due_date:
                    if todo.due_date.date() < today:
                        overdue.append(todo)
                    elif todo.due_date.date() == today:
                        due_today.append(todo)
                    else:
                        upcoming.append(todo)
                else:
                    no_date.append(todo)

            # Add sections
            if overdue:
                blocks.append(self._create_todo_section("🚨 Overdue", overdue))

            if due_today:
                blocks.append(self._create_todo_section("📅 Due Today", due_today))

            if upcoming:
                blocks.append(self._create_todo_section("⏰ Upcoming", upcoming[:5]))

            if no_date:
                blocks.append(self._create_todo_section("📝 No Due Date", no_date[:5]))

            # Add action buttons
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🌐 Open Dashboard"
                        },
                        "url": f"{settings.web.base_url}/todos"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "➕ Add TODO"
                        },
                        "action_id": "add_todo_button"
                    }
                ]
            })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error listing TODOs: {e}")
            return {"text": f"❌ Error retrieving TODOs: {str(e)}"}

    def _create_todo_section(self, title: str, todos: List) -> Dict[str, Any]:
        """Create a section block for TODO list."""
        todo_lines = []

        for todo in todos:
            # Create todo line with ID, title, assignee
            line = f"• `{todo.id[:8]}` *{todo.title}*"

            if todo.assignee:
                line += f" - {todo.assignee}"

            if todo.due_date:
                date_str = todo.due_date.strftime('%m/%d')
                line += f" ({date_str})"

            if todo.priority and todo.priority != 'Medium':
                priority_emoji = {"High": "🔴", "Low": "🟢"}.get(todo.priority, "")
                line += f" {priority_emoji}"

            todo_lines.append(line)

        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*\n" + "\n".join(todo_lines)
            }
        }

    def _create_todo_quick(self, user_id: str, title: str) -> Dict[str, Any]:
        """Create TODO quickly with minimal info."""
        try:
            from main import TodoItem
            import uuid

            assignee = self._get_user_display_name(user_id)

            # Map Slack user to app user
            app_user_id = self._map_slack_user_to_app_user(user_id)

            todo = TodoItem(
                id=str(uuid.uuid4()),
                title=title,
                description=f"Created via Slack by {assignee}",
                assignee=assignee,
                status='pending',
                priority='Medium',
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_id=app_user_id,  # Link to app user if found
                source='slack'  # Mark as Slack-created for visibility filtering
            )

            self.todo_manager.session.add(todo)
            self.todo_manager.session.commit()

            visibility_note = "🔒 (Private - only you can see this)" if app_user_id else ""

            return {
                "text": f"✅ TODO created: *{title}* {visibility_note}\n"
                       f"ID: `{todo.id[:8]}` | Assigned to: {assignee}\n"
                       f"💡 Use `/todos complete {todo.id[:8]}` to mark done"
            }

        except Exception as e:
            logger.error(f"Error creating quick TODO: {e}")
            return {"text": f"❌ Error creating TODO: {str(e)}"}

    def _create_todo_interactive(self, user_id: str, title: str) -> Dict[str, Any]:
        """Create TODO with interactive options."""
        # For now, create with defaults and show edit options
        result = self._create_todo_quick(user_id, title)

        # Add interactive buttons for editing
        if "✅" in result["text"]:
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": result["text"]
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🗓️ Set Due Date"
                            },
                            "action_id": "set_due_date"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "⚠️ Set Priority"
                            },
                            "action_id": "set_priority"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✏️ Edit Details"
                            },
                            "action_id": "edit_todo"
                        }
                    ]
                }
            ]
            return {"blocks": blocks}

        return result

    def _complete_todo(self, user_id: str, todo_id: str) -> Dict[str, Any]:
        """Complete a TODO item."""
        try:
            # Find TODO by partial ID
            from main import TodoItem
            todo = self.todo_manager.session.query(TodoItem).filter(
                TodoItem.id.startswith(todo_id)
            ).first()

            if not todo:
                return {"text": f"❌ TODO not found with ID starting with: `{todo_id}`"}

            assignee = self._get_user_display_name(user_id)
            success = self.todo_manager.complete_todo(todo.id, assignee, "Completed via Slack")

            if success:
                return {
                    "text": f"✅ Completed: *{todo.title}*\n"
                           f"Marked complete by {assignee}"
                }
            else:
                return {"text": f"❌ Failed to complete TODO: `{todo.id[:8]}`"}

        except Exception as e:
            logger.error(f"Error completing TODO: {e}")
            return {"text": f"❌ Error completing TODO: {str(e)}"}

    def _snooze_todo(self, user_id: str, todo_id: str, days: int = 1) -> Dict[str, Any]:
        """Snooze a TODO item."""
        try:
            from main import TodoItem
            todo = self.todo_manager.session.query(TodoItem).filter(
                TodoItem.id.startswith(todo_id)
            ).first()

            if not todo:
                return {"text": f"❌ TODO not found with ID starting with: `{todo_id}`"}

            success = self.todo_manager.snooze_todo(todo.id, days)

            if success:
                new_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
                return {
                    "text": f"😴 Snoozed: *{todo.title}*\n"
                           f"New due date: {new_date} (+{days} days)"
                }
            else:
                return {"text": f"❌ Failed to snooze TODO: `{todo.id[:8]}`"}

        except Exception as e:
            logger.error(f"Error snoozing TODO: {e}")
            return {"text": f"❌ Error snoozing TODO: {str(e)}"}

    def _get_summary(self) -> Dict[str, Any]:
        """Get team TODO summary."""
        try:
            summary = self.todo_manager.get_todo_summary()

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Team TODO Summary"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*📋 Total Active:*\n{summary.total}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🚨 Overdue:*\n{summary.overdue}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*📅 Due Today:*\n{summary.due_today}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*✅ Completed Today:*\n{summary.completed_today}"
                        }
                    ]
                }
            ]

            # Add assignee breakdown
            if summary.by_assignee:
                assignee_text = "\n".join([
                    f"• {assignee}: {count}"
                    for assignee, count in sorted(summary.by_assignee.items())
                ])

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*By Assignee:*\n{assignee_text}"
                    }
                })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error getting summary: {e}")
            return {"text": f"❌ Error getting summary: {str(e)}"}

    def _list_channels(self) -> Dict[str, Any]:
        """List channels the bot has access to."""
        try:
            # This is a synchronous wrapper for the async method
            import asyncio
            channels = asyncio.run(self.list_channels())

            if not channels:
                return {"text": "❌ No channels found or unable to access channel list."}

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📺 Available Channels"
                    }
                }
            ]

            # Separate channels by type
            public_channels = [ch for ch in channels if ch['type'] == 'public_channel']
            private_channels = [ch for ch in channels if ch['type'] == 'private_channel']

            # Add public channels section
            if public_channels:
                public_text = "\n".join([
                    f"• #{channel['name']} ({channel['num_members']} members)" +
                    (" - 🤖 Member" if channel.get('is_member') else "")
                    for channel in public_channels[:10]
                ])

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🌐 Public Channels:*\n{public_text}"
                    }
                })

            # Add private channels section
            if private_channels:
                private_text = "\n".join([
                    f"• #{channel['name']} ({channel['num_members']} members)"
                    for channel in private_channels[:10]
                ])

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🔒 Private Channels:*\n{private_text}"
                    }
                })

            total_channels = len(channels)
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": f"Total: {total_channels} channels accessible"
                }]
            })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error listing channels: {e}")
            return {"text": f"❌ Error listing channels: {str(e)}"}

    def _get_user_display_name(self, user_id: str) -> str:
        """Get user's display name from Slack."""
        try:
            response = self.client.users_info(user=user_id)
            user = response["user"]
            return user.get("display_name") or user.get("real_name") or user.get("name", user_id)
        except SlackApiError:
            return user_id

    def _get_user_email(self, user_id: str) -> Optional[str]:
        """Get user's email from Slack."""
        try:
            response = self.client.users_info(user=user_id)
            user = response["user"]
            profile = user.get("profile", {})
            return profile.get("email")
        except SlackApiError as e:
            logger.warning(f"Failed to get email for Slack user {user_id}: {e}")
            return None

    def _map_slack_user_to_app_user(self, slack_user_id: str) -> Optional[int]:
        """Map Slack user to app user by email.

        Args:
            slack_user_id: Slack user ID

        Returns:
            App user ID if found, None otherwise
        """
        try:
            # Get Slack user's email
            email = self._get_user_email(slack_user_id)
            if not email:
                logger.warning(f"No email found for Slack user {slack_user_id}")
                return None

            # Look up app user by email
            from src.models.user import User
            from sqlalchemy.orm import sessionmaker
            from config.settings import settings
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    logger.info(f"Mapped Slack user {slack_user_id} ({email}) to app user {user.id}")
                    return user.id
                else:
                    logger.warning(f"No app user found with email {email}")
                    return None
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error mapping Slack user to app user: {e}")
            return None

    def get_handler(self):
        """Get Flask request handler for Slack events."""
        return self.handler

    async def send_daily_digest(self, channel: str = None):
        """Send daily TODO digest to Slack channel."""
        try:
            summary = self.todo_manager.get_todo_summary()
            overdue_todos = self.todo_manager.get_overdue_todos()

            channel = channel or settings.notifications.slack_channel

            if summary.total == 0:
                await self.client.chat_postMessage(
                    channel=channel,
                    text="🎉 No active TODOs today! Great job team!"
                )
                return

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📋 Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*📋 Active TODOs:*\n{summary.total}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🚨 Overdue:*\n{summary.overdue}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*📅 Due Today:*\n{summary.due_today}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*✅ Completed:*\n{summary.completed_today}"
                        }
                    ]
                }
            ]

            # Add urgent items if any
            if overdue_todos:
                urgent_text = "\n".join([
                    f"• {todo.title} ({todo.assignee or 'Unassigned'})"
                    for todo in overdue_todos[:5]
                ])

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 Urgent - Overdue Items:*\n{urgent_text}"
                    }
                })

            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📋 View Dashboard"
                    },
                    "url": f"{settings.web.base_url}/todos"
                }]
            })

            await self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text="Daily TODO Digest"
            )

        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")

    def _analyze_message_for_todos(self, text: str, user_id: str, channel: str):
        """Analyze message content for potential TODOs or action items."""
        # Keywords that might indicate action items
        action_keywords = [
            'action item', 'todo', 'task', 'follow up', 'need to',
            'should do', 'will do', 'assigned to', 'deadline',
            'by friday', 'by next week', 'remind me'
        ]

        text_lower = text.lower()

        # Check if message contains action keywords
        has_action = any(keyword in text_lower for keyword in action_keywords)

        if has_action:
            logger.info(f"Potential TODO detected in {channel}: {text[:100]}...")
            # You could automatically create a TODO here or flag for review
            # For now, just log it

    async def list_channels(self) -> List[Dict[str, Any]]:
        """List all channels the bot has access to."""
        try:
            channels = []

            # Get public channels
            response = await self.client.conversations_list(
                types="public_channel",
                exclude_archived=True
            )

            for channel in response.get('channels', []):
                channels.append({
                    'id': channel['id'],
                    'name': channel['name'],
                    'type': 'public_channel',
                    'is_member': channel.get('is_member', False),
                    'num_members': channel.get('num_members', 0)
                })

            # Get private channels bot is member of
            response = await self.client.conversations_list(
                types="private_channel",
                exclude_archived=True
            )

            for channel in response.get('channels', []):
                if channel.get('is_member'):
                    channels.append({
                        'id': channel['id'],
                        'name': channel['name'],
                        'type': 'private_channel',
                        'is_member': True,
                        'num_members': channel.get('num_members', 0)
                    })

            return channels

        except SlackApiError as e:
            logger.error(f"Error listing channels: {e}")
            return []

    async def resolve_channel_name_to_id(self, channel_name: str) -> str:
        """Resolve a channel name to its ID. Returns the input if it's already an ID."""
        # Strip # prefix if present
        clean_name = channel_name.lstrip('#')

        # If it looks like a channel ID (starts with C and is alphanumeric), return as-is
        if clean_name.startswith('C') and clean_name.replace('C', '').isalnum() and len(clean_name) >= 9:
            logger.info(f"'{channel_name}' appears to be a channel ID, using as-is")
            return clean_name

        try:
            # Get all channels and find the one matching the name
            channels = await self.list_channels()
            for channel in channels:
                if channel['name'] == clean_name:
                    logger.info(f"Resolved channel name '{clean_name}' to ID '{channel['id']}'")
                    return channel['id']

            # If not found, log warning and return the original name
            logger.warning(f"Could not resolve channel name '{clean_name}' to ID. Available channels: {[c['name'] for c in channels[:5]]}")
            return clean_name

        except Exception as e:
            logger.error(f"Error resolving channel name '{clean_name}': {e}")
            return clean_name

    async def read_channel_history(self, channel_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Read recent messages from a specific channel, including threaded replies."""
        try:
            response = self.client.conversations_history(
                channel=channel_id,
                limit=limit
            )

            logger.info(f"Slack API response for channel {channel_id}: {len(response.get('messages', []))} total messages")

            messages = []
            for message in response.get('messages', []):
                message_type = message.get('type')
                has_subtype = 'subtype' in message
                has_text = bool(message.get('text'))
                has_thread = 'thread_ts' in message

                logger.info(f"Message - type: {message_type}, has_subtype: {has_subtype}, has_text: {has_text}, has_thread: {has_thread}, text: {message.get('text', '')[:50]}...")

                # Include main message if it's a regular message
                if message.get('type') == 'message' and 'subtype' not in message:
                    messages.append({
                        'user': message.get('user'),
                        'text': message.get('text'),
                        'timestamp': message.get('ts'),
                        'channel': channel_id,
                        'is_thread_parent': has_thread
                    })

                # If this message has threaded replies, fetch them
                if has_thread:
                    try:
                        thread_response = self.client.conversations_replies(
                            channel=channel_id,
                            ts=message.get('thread_ts')
                        )

                        # Add all replies (excluding the parent message which is already added)
                        for reply in thread_response.get('messages', [])[1:]:  # Skip first message (parent)
                            if (reply.get('type') == 'message' and
                                'subtype' not in reply and
                                reply.get('text')):

                                messages.append({
                                    'user': reply.get('user'),
                                    'text': reply.get('text'),
                                    'timestamp': reply.get('ts'),
                                    'channel': channel_id,
                                    'is_thread_reply': True,
                                    'thread_ts': message.get('thread_ts')
                                })

                        logger.info(f"Added {len(thread_response.get('messages', [])) - 1} thread replies for message {message.get('ts')}")

                    except SlackApiError as e:
                        logger.warning(f"Error fetching thread replies for message {message.get('ts')}: {e}")
                        continue

            logger.info(f"SlackTodoBot returning {len(messages)} filtered messages (including thread replies)")
            return messages

        except SlackApiError as e:
            logger.error(f"Error reading channel history for {channel_id}: {e}")
            return []

    def _get_agenda_help_message(self) -> Dict[str, Any]:
        """Get help message for agenda command."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📅 Agenda Generator Help"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Generate Project Meeting Agendas*\n\n"
                           "`/agenda <project-key> [days]` - Generate agenda for project\n\n"
                           "*Parameters:*\n"
                           "• `project-key` - Jira project key (e.g., PROJ, DEV, SATG)\n"
                           "• `days` - Number of days to look back (1-30, default: 7)\n\n"
                           "*Examples:*\n"
                           "• `/agenda PROJ-123` - 7-day agenda for PROJ-123\n"
                           "• `/agenda DEV-456 14` - 14-day agenda for DEV-456\n"
                           "• `/agenda SATG 3` - 3-day agenda for SATG"
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": "💡 The agenda includes meeting summaries, completed tickets, time tracking, and AI-generated insights"
                }]
            }
        ]

        return {"blocks": blocks}

    def _generate_project_agenda(self, user_id: str, project_key: str, days: int) -> Dict[str, Any]:
        """Generate project agenda using the ProjectActivityAggregator."""
        try:
            # Import the aggregator
            from src.services.project_activity_aggregator import ProjectActivityAggregator
            import asyncio

            # Create aggregator instance
            aggregator = ProjectActivityAggregator()

            # Generate the activity summary
            try:
                # Run the async aggregation
                activity = asyncio.run(aggregator.aggregate_project_activity(
                    project_key=project_key,
                    project_name=project_key,  # Use project key as name for now
                    days_back=days
                ))

                # Generate markdown agenda
                markdown_agenda = aggregator.format_client_agenda(activity)

                # Create response with summary stats
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📅 {project_key} - {days} Day Agenda"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*📋 Meetings:*\n{len(activity.meetings)}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*✅ Completed:*\n{len(activity.completed_tickets)}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*🆕 New Tickets:*\n{len(activity.new_tickets)}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*⏰ Hours:*\n{activity.total_hours:.1f}h"
                            }
                        ]
                    }
                ]

                # Add progress summary if available
                if activity.progress_summary:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*📊 Progress Summary:*\n{activity.progress_summary}"
                        }
                    })

                # Add key achievements if available
                if activity.key_achievements:
                    achievements_text = "\n".join([f"• {achievement}" for achievement in activity.key_achievements[:3]])
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🎯 Key Achievements:*\n{achievements_text}"
                        }
                    })

                # Add action buttons
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🌐 View Full Dashboard"
                            },
                            "url": f"{settings.web.base_url}/"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📄 Download Markdown"
                            },
                            "action_id": "download_agenda",
                            "value": f"{project_key}_{days}days"
                        }
                    ]
                })

                # Add context with generation info
                user_name = self._get_user_display_name(user_id)
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "plain_text",
                        "text": f"Generated by {user_name} • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    }]
                })

                return {"blocks": blocks}

            except Exception as e:
                logger.error(f"Error generating project activity: {e}")
                return {
                    "text": f"❌ Error generating agenda for {project_key}: {str(e)}\n"
                           f"Make sure the project key is valid and you have access to it."
                }

        except ImportError as e:
            logger.error(f"Error importing ProjectActivityAggregator: {e}")
            return {
                "text": "❌ Agenda generation is not available. The project activity aggregator is not properly configured."
            }

    def _generate_dad_joke(self, subject: Optional[str] = None, person_name: Optional[str] = None, requester: str = "someone") -> str:
        """Generate a dad joke using AI."""
        import random  # Move import outside try block

        try:
            # Import OpenAI
            from langchain_openai import ChatOpenAI

            # Initialize LLM (settings is already imported at the top)
            llm = ChatOpenAI(
                model=settings.ai.model,
                temperature=1.2,  # Higher temperature for more creative jokes
                max_tokens=200,
                api_key=settings.ai.api_key
            )

            # Build the prompt
            prompt_parts = ["Generate a single dad joke"]

            if subject and person_name:
                prompt_parts.append(f"about {subject} for {person_name}")
            elif subject:
                prompt_parts.append(f"about {subject}")
            elif person_name:
                prompt_parts.append(f"for {person_name}")

            prompt = " ".join(prompt_parts) + (
                ". Make it appropriately funny, punny, and workplace-appropriate. "
                "Format: Just the joke, no explanations or introductions. "
                "Include appropriate emoji."
            )

            # Log the prompt for debugging
            logger.info(f"Dad joke prompt: {prompt}")

            # Generate the joke
            response = llm.invoke(prompt)

            # Log the raw response for debugging
            logger.info(f"OpenAI response type: {type(response)}")
            logger.info(f"OpenAI response content: {response.content if hasattr(response, 'content') else str(response)}")

            joke_text = response.content.strip() if hasattr(response, 'content') else str(response).strip()

            # Validate we got a response
            if not joke_text:
                raise ValueError("AI returned empty response")

            # Add a random dad joke intro occasionally (30% chance)
            intros = [
                f"📢 {requester} requested a dad joke!",
                f"🎭 Dad joke incoming from {requester}!",
                f"🎪 {requester} thinks you need this:",
                f"🎯 Special delivery for the team:",
                f"✨ Fresh from the dad joke factory:",
            ]

            if random.random() < 0.3:
                joke_text = f"{random.choice(intros)}\n\n{joke_text}"

            # Ensure we have text
            if not joke_text:
                raise ValueError("No joke text generated")

            return joke_text

        except Exception as e:
            logger.error(f"Error generating dad joke: {e}")
            # Fallback to a random hardcoded joke
            fallback_jokes = [
                "Why don't scientists trust atoms? Because they make up everything! ⚛️",
                "I used to hate facial hair, but then it grew on me. 🧔",
                "Why did the developer go broke? Because he used up all his cache! 💸",
                "How do you organize a space party? You planet! 🪐",
                "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
                "I told my computer I needed a break, and now it won't stop sending me Kit-Kats. 🍫",
                "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                "What did the ocean say to the beach? Nothing, it just waved! 🌊"
            ]
            return f"💔 AI couldn't think of a joke, so here's a classic:\n\n{random.choice(fallback_jokes)}"

    def _get_learning_help_message(self) -> Dict[str, Any]:
        """Get help message for learning command."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💡 Learning Tracker Help"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Save and Share Team Learnings*\n\n"
                           "`/learning <text>` - Save a new learning\n"
                           "`/learning list [category]` - List recent learnings\n"
                           "`/learning search <term>` - Search learnings\n"
                           "`/learning stats` - View statistics\n"
                           "`/learning categories` - List all categories\n"
                           "`/learning help` - Show this help\n\n"
                           "*Examples:*\n"
                           "• `/learning Always test edge cases in production-like environment`\n"
                           "• `/learning Document API changes in PR description #technical`\n"
                           "• `/learning list technical` - List technical learnings\n"
                           "• `/learning search API` - Search for API-related learnings"
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": "💡 Pro tip: Add #category to categorize your learning (optional)"
                }]
            }
        ]

        return {"blocks": blocks}

    def _create_learning(self, user_id: str, text: str) -> Dict[str, Any]:
        """Create a new learning from Slack command."""
        try:
            # Get user display name
            user_name = self._get_user_display_name(user_id)

            # Try to map Slack user to app user
            app_user_id = self._map_slack_user_to_app_user(user_id)

            # Parse category from text if present
            category = None
            content = text

            # Check for #category tag
            import re
            category_match = re.search(r'#(\w+)', text)
            if category_match:
                category = category_match.group(1).lower()
                content = text.replace(f'#{category_match.group(1)}', '').strip()

            # Create the learning with mapped user ID if available
            learning = self.learning_manager.create_learning(
                content=content,
                submitted_by=user_name,
                submitted_by_id=str(app_user_id) if app_user_id else None,
                category=category,
                source=f'slack - {user_name}'  # Store name in source for UI display
            )

            # Format response
            category_str = f" [{category}]" if category else ""
            return {
                "text": f"✅ Learning saved{category_str}!\n\n"
                       f"💡 *{content}*\n"
                       f"_ID: {learning.id[:8]}_"
            }

        except Exception as e:
            logger.error(f"Error creating learning: {e}")
            return {"text": f"❌ Error saving learning: {str(e)}"}

    def _list_learnings(self, category: str = None) -> Dict[str, Any]:
        """List recent learnings."""
        try:
            learnings = self.learning_manager.get_learnings(
                limit=10,
                category=category
            )

            if not learnings:
                if category:
                    return {"text": f"No learnings found in category: {category}"}
                else:
                    return {"text": "No learnings found yet. Start adding some with `/learning`!"}

            title = f"💡 Recent Learnings" + (f" [{category}]" if category else "")

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                }
            ]

            # Add learning sections
            for learning in learnings:
                category_str = f" `{learning.category}`" if learning.category else ""
                date_str = learning.created_at.strftime('%m/%d')

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{learning.content}*{category_str}\n"
                               f"  _by {learning.submitted_by} on {date_str}_"
                    }
                })

            # Add action buttons
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🌐 View All"
                        },
                        "url": f"{settings.web.base_url}/learnings"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "➕ Add Learning"
                        },
                        "action_id": "add_learning_button"
                    }
                ]
            })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error listing learnings: {e}")
            return {"text": f"❌ Error retrieving learnings: {str(e)}"}

    def _search_learnings(self, search_term: str) -> Dict[str, Any]:
        """Search learnings by content."""
        try:
            learnings = self.learning_manager.search_learnings(
                search_term=search_term,
                limit=10
            )

            if not learnings:
                return {"text": f"No learnings found matching: {search_term}"}

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🔍 Search Results for '{search_term}'"
                    }
                }
            ]

            # Add learning sections
            for learning in learnings:
                category_str = f" `{learning.category}`" if learning.category else ""
                date_str = learning.created_at.strftime('%m/%d')

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{learning.content}*{category_str}\n"
                               f"  _by {learning.submitted_by} on {date_str}_"
                    }
                })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error searching learnings: {e}")
            return {"text": f"❌ Error searching learnings: {str(e)}"}

    def _get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learnings."""
        try:
            stats = self.learning_manager.get_stats()

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Learning Statistics"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*💡 Total Learnings:*\n{stats['total']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*📅 Today:*\n{stats['today']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*📆 This Week:*\n{stats['this_week']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🏷️ Categories:*\n{stats['categories_count']}"
                        }
                    ]
                }
            ]

            # Add top categories if any
            if stats['categories']:
                categories_text = ", ".join(stats['categories'][:5])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Top Categories:* {categories_text}"
                    }
                })

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {"text": f"❌ Error retrieving statistics: {str(e)}"}

    def _list_categories(self) -> Dict[str, Any]:
        """List all learning categories."""
        try:
            categories = self.learning_manager.get_categories()

            if not categories:
                return {"text": "No categories found yet. Add categories to learnings with #category"}

            categories_text = "\n".join([f"• `{cat}`" for cat in categories])

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🏷️ Learning Categories"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": categories_text
                    }
                },
                {
                    "type": "context",
                    "elements": [{
                        "type": "plain_text",
                        "text": f"Total: {len(categories)} categories"
                    }]
                }
            ]

            return {"blocks": blocks}

        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return {"text": f"❌ Error retrieving categories: {str(e)}"}

    def _get_feedback_help_message(self) -> Dict[str, Any]:
        """Get help message for feedback command."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💬 Feedback Tracker Help"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Save Private Feedback for Later*\n\n"
                           "`/feedback <text>` - Save feedback without a recipient\n"
                           "`/feedback @user <text>` - Save feedback for a specific person\n"
                           "`/feedback help` - Show this help\n\n"
                           "*Examples:*\n"
                           "• `/feedback Great job on the presentation!` - General feedback\n"
                           "• `/feedback @johndoe Excellent work on the API refactor` - Feedback for John\n\n"
                           "*Note:* All feedback is private to you. Only you can see it."
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": "💡 Tip: Use the web dashboard to view and manage your saved feedback"
                }]
            }
        ]

        return {"blocks": blocks}

    def _create_feedback(self, user_id: str, recipient: Optional[str], content: str) -> Dict[str, Any]:
        """Create a new feedback item from Slack command."""
        try:
            from src.models import FeedbackItem
            import uuid

            # Get user display name
            user_name = self._get_user_display_name(user_id)

            # Map Slack user to app user
            app_user_id = self._map_slack_user_to_app_user(user_id)

            if not app_user_id:
                return {
                    "text": "❌ Could not find your user account. Please make sure you're logged into the web app first."
                }

            # Create the feedback
            feedback = FeedbackItem(
                id=str(uuid.uuid4()),
                user_id=app_user_id,
                recipient=recipient,
                content=content,
                status='draft',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Add to database
            from src.utils.database import session_scope
            with session_scope() as db_session:
                db_session.add(feedback)
                db_session.commit()

            # Format response
            recipient_str = f" for *{recipient}*" if recipient else ""
            return {
                "text": f"✅ Feedback saved{recipient_str}! 🔒 (Private to you)\n\n"
                       f"💬 *{content}*\n\n"
                       f"_ID: {feedback.id[:8]} | Status: {feedback.status}_\n"
                       f"💡 View all your feedback at {settings.web.base_url}/feedback"
            }

        except Exception as e:
            logger.error(f"Error creating feedback: {e}")
            return {"text": f"❌ Error saving feedback: {str(e)}"}

    def _validate_slack_user(self, user_id: str) -> bool:
        """Validate that a Slack user exists."""
        try:
            response = self.client.users_info(user=user_id)
            return response.get("ok", False) and not response.get("user", {}).get("deleted", False)
        except SlackApiError:
            return False