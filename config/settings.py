"""Configuration management for PM Agent."""

import os
from dataclasses import dataclass
from typing import Optional, List
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
    tempo_api_token: Optional[str] = None


@dataclass
class NotificationConfig:
    """Notification settings for multiple channels."""

    slack_bot_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    slack_channel: str = "#mikes-minion"
    slack_urgent_channel: str = "#mikes-minion"

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    teams_webhook_url: Optional[str] = None

    morning_digest_time: str = "08:00"
    evening_digest_time: str = "17:00"


@dataclass
class SlackChatConfig:
    """Slack conversational chat feature configuration."""

    enabled: bool = False
    whitelisted_users: List[str] = None  # List of Slack user IDs

    def __post_init__(self):
        if self.whitelisted_users is None:
            self.whitelisted_users = []


@dataclass
class AIConfig:
    """AI model configuration."""

    api_key: str
    provider: str = "openai"  # "openai", "anthropic", or "google"
    model: str = "gpt-4"  # Default - override with provider-specific MODEL env var
    temperature: float = 0.3
    max_tokens: int = 2000


@dataclass
class PineconeConfig:
    """Pinecone vector database configuration."""

    api_key: str
    environment: str
    index_name: str = "agent-pm-context"
    dimension: int = 1536  # text-embedding-3-small dimension
    metric: str = "cosine"


@dataclass
class NotionConfig:
    """Notion API configuration."""

    api_key: str


@dataclass
class GitHubConfig:
    """GitHub API configuration.

    Supports two authentication modes:
    1. Personal Access Token (legacy): Set api_token
    2. GitHub App (recommended): Set app_id, private_key, installation_id
    """

    # Personal Access Token (legacy)
    api_token: str = ""

    # GitHub App (recommended)
    app_id: str = ""
    private_key: str = ""
    installation_id: str = ""

    # Organization name (optional, for filtering)
    organization: str = ""


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
        self.github = self._load_github_config()
        self.notifications = self._load_notification_config()
        self.slack_chat = self._load_slack_chat_config()
        self.ai = self._load_ai_config()
        self.agent = self._load_agent_config()
        self.web = self._load_web_config()
        self.pinecone = self._load_pinecone_config()
        self.notion = self._load_notion_config()

    @staticmethod
    def _load_fireflies_config() -> FirefliesConfig:
        # Fireflies API key is now optional (stored per-user)
        api_key = os.getenv("FIREFLIES_API_KEY", "")

        return FirefliesConfig(
            api_key=api_key,
            base_url=os.getenv(
                "FIREFLIES_BASE_URL", "https://api.fireflies.ai/graphql"
            ),
        )

    @staticmethod
    def _load_jira_config() -> Optional[JiraConfig]:
        jira_url = os.getenv("JIRA_URL")
        username = os.getenv("JIRA_USERNAME")
        api_token = os.getenv("JIRA_API_TOKEN")

        if not all([jira_url, username, api_token]):
            # JIRA config is optional - warn but don't fail
            import warnings

            warnings.warn(
                "JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN not set. JIRA integration will be disabled."
            )
            return None

        return JiraConfig(
            url=jira_url,
            username=username,
            api_token=api_token,
            default_project=os.getenv("JIRA_DEFAULT_PROJECT"),
            tempo_api_token=os.getenv("TEMPO_API_TOKEN"),
        )

    @staticmethod
    def _load_github_config() -> GitHubConfig:
        """Load GitHub configuration.

        Supports two authentication modes:
        1. Personal Access Token: GITHUB_API_TOKEN
        2. GitHub App: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID
        """
        # Load GitHub App config (preferred)
        app_id = os.getenv("GITHUB_APP_ID", "")
        private_key_env = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
        installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID", "")

        # Handle private key - support both raw key and file path
        private_key = ""
        if private_key_env:
            if private_key_env.startswith("-----BEGIN"):
                # Raw PEM key in environment variable
                private_key = private_key_env
            elif os.path.isfile(private_key_env):
                # Path to PEM file
                with open(private_key_env, "r") as f:
                    private_key = f.read()
            else:
                # Try to interpret as base64-encoded key (for environment variables)
                import base64

                try:
                    private_key = base64.b64decode(private_key_env).decode("utf-8")
                except Exception:
                    private_key = private_key_env  # Use as-is

        # Load Personal Access Token (fallback)
        api_token = os.getenv("GITHUB_API_TOKEN", "")

        return GitHubConfig(
            api_token=api_token,
            app_id=app_id,
            private_key=private_key,
            installation_id=installation_id,
            organization=os.getenv("GITHUB_ORGANIZATION", ""),
        )

    @staticmethod
    def _load_notification_config() -> NotificationConfig:
        # Handle empty string env vars by treating them as None/defaults
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str else 587

        return NotificationConfig(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN") or None,
            slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET") or None,
            slack_channel=os.getenv("SLACK_CHANNEL") or "#mikes-minion",
            slack_urgent_channel=os.getenv("SLACK_URGENT_CHANNEL") or "#mikes-minion",
            smtp_host=os.getenv("SMTP_HOST") or None,
            smtp_port=smtp_port,
            smtp_user=os.getenv("SMTP_USER") or None,
            smtp_password=os.getenv("SMTP_PASSWORD") or None,
            teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL") or None,
            morning_digest_time=os.getenv("MORNING_DIGEST_TIME") or "08:00",
            evening_digest_time=os.getenv("EVENING_DIGEST_TIME") or "17:00",
        )

    @staticmethod
    def _load_slack_chat_config() -> SlackChatConfig:
        """Load Slack chat feature configuration."""
        enabled = os.getenv("SLACK_CHAT_ENABLED", "false").lower() == "true"

        # Parse whitelisted users (comma-separated Slack user IDs)
        whitelist_str = os.getenv("SLACK_CHAT_WHITELISTED_USERS", "")
        whitelisted_users = [
            uid.strip() for uid in whitelist_str.split(",") if uid.strip()
        ]

        return SlackChatConfig(enabled=enabled, whitelisted_users=whitelisted_users)

    @staticmethod
    def _load_ai_config() -> Optional[AIConfig]:
        """Load AI configuration from database if available, otherwise from environment."""
        # Try to load from database first (admin-configured settings)
        db_settings = Settings._load_ai_config_from_db()
        if db_settings:
            return db_settings

        # Fallback to environment variables
        provider = os.getenv("AI_PROVIDER", "openai")

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            model = os.getenv("OPENAI_MODEL", "gpt-5")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        elif provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
            model = os.getenv("GOOGLE_MODEL", "gemini-1.5-pro")
        else:
            import warnings

            warnings.warn(
                f"Unsupported AI provider: {provider}. AI features will be disabled."
            )
            return None

        if not api_key:
            import warnings

            warnings.warn(
                f"{provider.upper()}_API_KEY not set in environment. AI features will be disabled."
            )
            return None

        return AIConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=float(os.getenv("AI_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "2000")),
        )

    @staticmethod
    def _load_ai_config_from_db() -> AIConfig | None:
        """Load AI configuration from database if available."""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from src.models.system_settings import SystemSettings

            # Get database URL
            database_url = os.getenv("DATABASE_URL", "sqlite:///database/pm_agent.db")

            # Create engine and session
            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                # Get system settings (there should only be one row)
                system_settings = session.query(SystemSettings).first()

                if not system_settings:
                    return None

                # Get the API key for the configured provider
                api_key = system_settings.get_api_key(system_settings.ai_provider)

                if not api_key:
                    # No API key in database, fallback to env
                    return None

                # Use model from DB if set, otherwise use provider defaults
                model = system_settings.ai_model
                if not model:
                    if system_settings.ai_provider == "openai":
                        model = "gpt-4"
                    elif system_settings.ai_provider == "anthropic":
                        model = "claude-3-5-sonnet-20241022"
                    elif system_settings.ai_provider == "google":
                        model = "gemini-1.5-pro"

                return AIConfig(
                    provider=system_settings.ai_provider,
                    model=model,
                    api_key=api_key,
                    temperature=system_settings.ai_temperature,
                    max_tokens=system_settings.ai_max_tokens,
                )
            finally:
                session.close()

        except Exception as e:
            # If database doesn't exist or table doesn't exist yet, return None to fallback to env
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Could not load AI config from database: {e}")
            return None

    def reload_ai_config(self):
        """Reload AI configuration from database (for dynamic updates)."""
        self.ai = self._load_ai_config()
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"AI config reloaded: provider={self.ai.provider}, model={self.ai.model}"
        )

    @classmethod
    def get_fresh_ai_config(cls) -> AIConfig:
        """Get fresh AI configuration without affecting the singleton instance.

        This is useful for getting the latest config from the database without
        reloading the entire settings singleton.
        """
        return cls._load_ai_config()

    @staticmethod
    def _load_agent_config() -> AgentConfig:
        return AgentConfig(
            run_schedule=os.getenv("AGENT_RUN_SCHEDULE", "0 8,17 * * *"),
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///database/pm_agent.db"),
        )

    @staticmethod
    def _load_web_config() -> WebConfig:
        return WebConfig(
            base_url=os.getenv(
                "WEB_BASE_URL", "https://agent-pm-tsbbb.ondigitalocean.app"
            ),
            port=int(os.getenv("WEB_PORT", "3030")),
            host=os.getenv("WEB_HOST", "127.0.0.1"),
            debug=os.getenv("WEB_DEBUG", "true").lower() == "true",
        )

    @staticmethod
    def _load_pinecone_config() -> PineconeConfig:
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            # Pinecone is optional - if not configured, vector search won't be available
            return PineconeConfig(api_key="", environment="")

        return PineconeConfig(
            api_key=api_key,
            environment=os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws"),
            index_name=os.getenv("PINECONE_INDEX_NAME", "agent-pm-context"),
            dimension=int(os.getenv("PINECONE_DIMENSION", "1536")),
            metric=os.getenv("PINECONE_METRIC", "cosine"),
        )

    @staticmethod
    def _load_notion_config() -> NotionConfig:
        api_key = os.getenv("NOTION_API_KEY", "")
        return NotionConfig(api_key=api_key)


settings = Settings()
