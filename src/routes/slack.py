"""Slack bot integration routes."""
from flask import Blueprint, jsonify, request
import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

slack_bp = Blueprint('slack', __name__)

# Lazy initialization of Slack bot
_slack_bot = None
_slack_bot_lock = threading.Lock()
_slack_config = None


def init_slack_routes(bot_token, signing_secret):
    """Initialize Slack routes with configuration for lazy loading.

    Args:
        bot_token: Slack bot token (or None if not configured)
        signing_secret: Slack signing secret
    """
    global _slack_config
    _slack_config = {
        'bot_token': bot_token,
        'signing_secret': signing_secret
    }


def get_slack_bot():
    """Get or create Slack bot instance (lazy initialization).

    Returns:
        SlackTodoBot instance or None if not configured
    """
    global _slack_bot

    # Fast path: bot already initialized
    if _slack_bot is not None:
        return _slack_bot

    # Not configured at all
    if not _slack_config or not _slack_config.get('bot_token'):
        return None

    # Slow path: initialize with thread safety (double-check locking)
    with _slack_bot_lock:
        # Check again inside lock (another thread might have initialized it)
        if _slack_bot is None:
            try:
                from src.managers.slack_bot import SlackTodoBot
                _slack_bot = SlackTodoBot(
                    bot_token=_slack_config['bot_token'],
                    signing_secret=_slack_config['signing_secret']
                )
                logger.info("Slack bot initialized successfully (lazy)")
            except Exception as e:
                logger.warning(f"Failed to initialize Slack bot: {e}")
                # Don't set _slack_bot, allow retry on next request
                return None

        return _slack_bot


@slack_bp.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events and commands."""
    # Handle URL verification challenge from Slack
    if request.is_json and request.json and request.json.get('type') == 'url_verification':
        return jsonify({'challenge': request.json.get('challenge')}), 200

    slack_bot = get_slack_bot()
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    # Let Slack Bolt handler process all requests (slash commands, events, etc.)
    return slack_bot.get_handler().handle(request)


@slack_bp.route("/slack/commands", methods=["POST"])
def slack_commands():
    """Handle Slack slash commands."""
    slack_bot = get_slack_bot()
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return slack_bot.get_handler().handle(request)


@slack_bp.route("/slack/interactive", methods=["POST"])
def slack_interactive():
    """Handle Slack interactive components."""
    slack_bot = get_slack_bot()
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return slack_bot.get_handler().handle(request)


@slack_bp.route("/api/slack/digest", methods=["POST"])
def send_slack_digest():
    """Manually trigger Slack daily digest."""
    slack_bot = get_slack_bot()
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    try:
        channel = request.json.get('channel') if request.json else None
        asyncio.run(slack_bot.send_daily_digest(channel))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
