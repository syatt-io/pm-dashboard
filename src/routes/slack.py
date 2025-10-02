"""Slack bot integration routes."""
from flask import Blueprint, jsonify, request
import asyncio
import logging

logger = logging.getLogger(__name__)

slack_bp = Blueprint('slack', __name__)

# Slack bot instance will be injected
_slack_bot = None


def init_slack_routes(slack_bot_instance):
    """Initialize Slack routes with bot instance."""
    global _slack_bot
    _slack_bot = slack_bot_instance


@slack_bp.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events and commands."""
    # Handle URL verification challenge from Slack
    if request.is_json and request.json and request.json.get('type') == 'url_verification':
        return jsonify({'challenge': request.json.get('challenge')}), 200

    if not _slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    # Let Slack Bolt handler process all requests (slash commands, events, etc.)
    return _slack_bot.get_handler().handle(request)


@slack_bp.route("/slack/commands", methods=["POST"])
def slack_commands():
    """Handle Slack slash commands."""
    if not _slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return _slack_bot.get_handler().handle(request)


@slack_bp.route("/slack/interactive", methods=["POST"])
def slack_interactive():
    """Handle Slack interactive components."""
    if not _slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return _slack_bot.get_handler().handle(request)


@slack_bp.route("/api/slack/digest", methods=["POST"])
def send_slack_digest():
    """Manually trigger Slack daily digest."""
    if not _slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    try:
        channel = request.json.get('channel') if request.json else None
        asyncio.run(_slack_bot.send_daily_digest(channel))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
