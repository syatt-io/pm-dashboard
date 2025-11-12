"""Prompt Manager for loading and managing AI prompts from configuration."""

import os
import yaml
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages AI prompts loaded from configuration files."""

    def __init__(self, config_path: str = None):
        """
        Initialize the PromptManager with a configuration file.

        Args:
            config_path: Path to the prompts configuration file.
                        Defaults to config/ai_prompts.yaml
        """
        if config_path is None:
            # Default to config/ai_prompts.yaml relative to project root
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            config_path = os.path.join(project_root, "config", "ai_prompts.yaml")

        self.config_path = config_path
        self.prompts = self._load_prompts()
        self.settings = self.prompts.get("prompt_settings", {})

    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from the YAML configuration file."""
        try:
            with open(self.config_path, "r") as f:
                prompts = yaml.safe_load(f)
                logger.info(f"Successfully loaded prompts from {self.config_path}")
                return prompts
        except FileNotFoundError:
            logger.error(f"Prompts configuration file not found: {self.config_path}")
            return self._get_default_prompts()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing prompts YAML: {e}")
            return self._get_default_prompts()
        except Exception as e:
            logger.error(f"Unexpected error loading prompts: {e}")
            return self._get_default_prompts()

    def reload_prompts(self):
        """Reload prompts from the configuration file."""
        logger.info("Reloading prompts configuration...")
        self.prompts = self._load_prompts()
        self.settings = self.prompts.get("prompt_settings", {})

    def get_meeting_analysis_prompts(self) -> Dict[str, str]:
        """Get all meeting analysis related prompts."""
        return self.prompts.get("meeting_analysis", {})

    def get_slack_analysis_prompts(self) -> Dict[str, str]:
        """Get all Slack analysis related prompts."""
        return self.prompts.get("slack_analysis", {})

    def get_digest_prompts(self) -> Dict[str, str]:
        """Get all digest generation related prompts."""
        return self.prompts.get("digest_generation", {})

    def get_context_search_prompts(self) -> Dict[str, str]:
        """Get all context search related prompts."""
        return self.prompts.get("context_search", {})

    def get_prompt(self, category: str, prompt_key: str, default: str = "") -> str:
        """
        Get a specific prompt by category and key.

        Args:
            category: The category of prompts (e.g., 'meeting_analysis')
            prompt_key: The specific prompt key (e.g., 'system_prompt')
            default: Default value if prompt not found

        Returns:
            The prompt string or default if not found
        """
        return self.prompts.get(category, {}).get(prompt_key, default)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a prompt-related setting.

        Args:
            key: The setting key
            default: Default value if setting not found

        Returns:
            The setting value or default if not found
        """
        return self.settings.get(key, default)

    def format_prompt(self, category: str, prompt_key: str, **kwargs) -> str:
        """
        Get and format a prompt with provided variables.

        Args:
            category: The category of prompts
            prompt_key: The specific prompt key
            **kwargs: Variables to format into the prompt

        Returns:
            Formatted prompt string
        """
        prompt = self.get_prompt(category, prompt_key)
        try:
            return prompt.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in prompt formatting: {e}")
            return prompt
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            return prompt

    def _get_default_prompts(self) -> Dict[str, Any]:
        """Return default prompts as fallback."""
        return {
            "meeting_analysis": {
                "system_prompt": """You are an expert meeting analyst. Extract key information from meeting transcripts.""",
                "action_items_prompt": """Extract action items from this meeting transcript.""",
                "blockers_prompt": """Identify blockers and risks from this meeting.""",
                "summary_prompt": """Create a concise meeting summary.""",
            },
            "slack_analysis": {
                "discussions_prompt_template": """Analyze Slack discussions and extract key points."""
            },
            "digest_generation": {
                "system_message": """You are a project management assistant.""",
                "insights_prompt_template": """Generate project insights from the provided data.""",
            },
            "context_search": {
                "system_message": """You are an expert technical analyst helping engineers understand project context.""",
                "user_prompt_template": """Query: "{query}"\n{domain_context}\nSEARCH RESULTS:\n{context_text}\n\nSynthesize the results into a concise answer.""",
                "domain_context_template": """\nDOMAIN CONTEXT:\nThis query relates to the "{project_key}" project. Related terms: {keywords_str}.\n""",
                "detail_levels": {
                    "brief": "Keep your summary concise (100-200 words). Focus on the most critical information only.",
                    "normal": "Target 150-250 words. Be brief and direct - cut unnecessary words, get straight to the point.",
                    "detailed": "Be thorough but not verbose (400-600 words). Include relevant details but avoid wordiness.",
                    "slack": "CRITICAL: Maximum 2000 characters total. Target 200-300 words MAX. Be extremely concise.",
                },
            },
            "prompt_settings": {
                "summary_max_length": 500,
                "transcript_max_chars": 8000,
                "slack_messages_max_chars": 3000,
                "max_key_discussions": 10,
            },
        }


# Singleton instance
_prompt_manager = None


def get_prompt_manager(config_path: str = None) -> PromptManager:
    """
    Get the singleton PromptManager instance.

    Args:
        config_path: Optional path to prompts configuration file

    Returns:
        PromptManager instance
    """
    global _prompt_manager
    if _prompt_manager is None or config_path is not None:
        _prompt_manager = PromptManager(config_path)
    return _prompt_manager
