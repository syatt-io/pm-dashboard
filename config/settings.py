"""Configuration management for PM Agent."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class FirefliesConfig:
    """Fireflies.ai API configuration."""
    api_key: str
    base_url: str = "https://api.fireflies.ai/graphql"


@dataclass
class JiraConfig:
    """Jira configuration for MCP integration."""
    url: str
    username: str
    api_token: str
    default_project: Optional[str] = None


@dataclass
class NotificationConfig:
    """Notification settings for multiple channels."""
    slack_bot_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    slack_channel: str = "#pm-updates"
    slack_urgent_channel: str = "#urgent-tasks"

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    teams_webhook_url: Optional[str] = None

    morning_digest_time: str = "08:00"
    evening_digest_time: str = "17:00"


@dataclass
class AIConfig:
    """AI model configuration."""
    api_key: str
    provider: str = "openai"  # or "anthropic"
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000


@dataclass
class WebConfig:
    """Web interface configuration."""
    base_url: str = "http://localhost:3030"
    port: int = 3030
    host: str = "127.0.0.1"
    debug: bool = True


@dataclass
class AgentConfig:
    """Main agent configuration."""
    run_schedule: str = "0 8,17 * * *"  # Cron expression
    debug_mode: bool = False
    log_level: str = "INFO"
    database_url: str = "sqlite:///database/pm_agent.db"


class Settings:
    """Main settings manager."""

    def __init__(self):
        self.fireflies = self._load_fireflies_config()
        self.jira = self._load_jira_config()
        self.notifications = self._load_notification_config()
        self.ai = self._load_ai_config()
        self.agent = self._load_agent_config()
        self.web = self._load_web_config()

    @staticmethod
    def _load_fireflies_config() -> FirefliesConfig:
        api_key = os.getenv("FIREFLIES_API_KEY")
        if not api_key:
            raise ValueError("FIREFLIES_API_KEY not set in environment")

        return FirefliesConfig(
            api_key=api_key,
            base_url=os.getenv("FIREFLIES_BASE_URL", "https://api.fireflies.ai/graphql")
        )

    @staticmethod
    def _load_jira_config() -> JiraConfig:
        jira_url = os.getenv("JIRA_URL")
        username = os.getenv("JIRA_USERNAME")
        api_token = os.getenv("JIRA_API_TOKEN")

        if not all([jira_url, username, api_token]):
            raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN must be set")

        return JiraConfig(
            url=jira_url,
            username=username,
            api_token=api_token,
            default_project=os.getenv("JIRA_DEFAULT_PROJECT")
        )

    @staticmethod
    def _load_notification_config() -> NotificationConfig:
        return NotificationConfig(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN"),
            slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
            slack_channel=os.getenv("SLACK_CHANNEL", "#pm-updates"),
            slack_urgent_channel=os.getenv("SLACK_URGENT_CHANNEL", "#urgent-tasks"),
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASS"),
            teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL"),
            morning_digest_time=os.getenv("MORNING_DIGEST_TIME", "08:00"),
            evening_digest_time=os.getenv("EVENING_DIGEST_TIME", "17:00")
        )

    @staticmethod
    def _load_ai_config() -> AIConfig:
        provider = os.getenv("AI_PROVIDER", "openai")

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            model = os.getenv("OPENAI_MODEL", "gpt-4")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        if not api_key:
            raise ValueError(f"{provider.upper()}_API_KEY not set in environment")

        return AIConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=float(os.getenv("AI_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "2000"))
        )

    @staticmethod
    def _load_agent_config() -> AgentConfig:
        return AgentConfig(
            run_schedule=os.getenv("AGENT_RUN_SCHEDULE", "0 8,17 * * *"),
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///database/pm_agent.db")
        )

    @staticmethod
    def _load_web_config() -> WebConfig:
        return WebConfig(
            base_url=os.getenv("WEB_BASE_URL", "http://localhost:3030"),
            port=int(os.getenv("WEB_PORT", "3030")),
            host=os.getenv("WEB_HOST", "127.0.0.1"),
            debug=os.getenv("WEB_DEBUG", "true").lower() == "true"
        )


settings = Settings()