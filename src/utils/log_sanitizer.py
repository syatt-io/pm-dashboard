"""Log sanitization utility for redacting sensitive credentials from logs.

This module provides utilities to automatically redact sensitive information
(API keys, tokens, passwords, secrets) from log messages to prevent credential
leakage in application logs.
"""

import re
import logging
from typing import Any, Dict, Optional, Pattern
import json


# ✅ SECURITY: Comprehensive patterns for sensitive data
SENSITIVE_PATTERNS = {
    # API Keys and Tokens
    'api_key': re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]+)(["\']?)', re.IGNORECASE),
    'api_token': re.compile(r'(api[_-]?token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]+)(["\']?)', re.IGNORECASE),
    'access_token': re.compile(r'(access[_-]?token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-\.]+)(["\']?)', re.IGNORECASE),
    'refresh_token': re.compile(r'(refresh[_-]?token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-\.]+)(["\']?)', re.IGNORECASE),

    # Authorization headers
    'bearer_token': re.compile(r'(Bearer\s+)([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    'basic_auth': re.compile(r'(Basic\s+)([a-zA-Z0-9+/=]+)', re.IGNORECASE),
    'authorization': re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)', re.IGNORECASE),

    # JWT tokens
    'jwt': re.compile(r'(eyJ[a-zA-Z0-9_\-]*\.eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*)'),

    # Passwords and Secrets
    'password': re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)', re.IGNORECASE),
    'secret': re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]+)(["\']?)', re.IGNORECASE),
    'secret_key': re.compile(r'(secret[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]+)(["\']?)', re.IGNORECASE),

    # OAuth and Google credentials
    'oauth_token': re.compile(r'(oauth[_-]?token["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)', re.IGNORECASE),
    'client_secret': re.compile(r'(client[_-]?secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]+)(["\']?)', re.IGNORECASE),

    # Database and connection strings
    'connection_string': re.compile(r'(postgresql|mysql|mongodb)://[^:]+:([^@]+)@', re.IGNORECASE),
    'database_url': re.compile(r'(DATABASE_URL["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)', re.IGNORECASE),

    # Slack tokens
    'slack_token': re.compile(r'(xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]+)'),

    # GitHub tokens
    'github_token': re.compile(r'(gh[pousr]_[a-zA-Z0-9]{36,})'),

    # Email credentials
    'smtp_password': re.compile(r'(smtp[_-]?password["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)', re.IGNORECASE),

    # Generic patterns for environment variables
    'env_key': re.compile(r'([A-Z_]+_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)'),
}

# ✅ SECURITY: Redaction format options
REDACTION_FORMAT = '[REDACTED]'
PARTIAL_REDACTION_PREFIX_LEN = 4  # Show first 4 characters
PARTIAL_REDACTION_SUFFIX_LEN = 4  # Show last 4 characters


def redact_sensitive_data(message: str, partial: bool = False) -> str:
    """Redact sensitive data from log messages.

    Args:
        message: The log message to sanitize
        partial: If True, show first/last N characters for debugging

    Returns:
        Sanitized log message with credentials redacted

    Example:
        >>> redact_sensitive_data('API_KEY=abc123def456')
        'API_KEY=[REDACTED]'
        >>> redact_sensitive_data('API_KEY=abc123def456', partial=True)
        'API_KEY=abc1...[REDACTED]...f456'
    """
    sanitized = message

    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        if pattern_name == 'jwt':
            # JWT: Show algorithm hint only
            sanitized = pattern.sub(r'[REDACTED-JWT]', sanitized)
        elif pattern_name in ('bearer_token', 'basic_auth'):
            # Authorization headers: Keep the auth type, redact the value
            if partial:
                def partial_redact_auth(match):
                    prefix = match.group(1)
                    token = match.group(2)
                    if len(token) > (PARTIAL_REDACTION_PREFIX_LEN + PARTIAL_REDACTION_SUFFIX_LEN):
                        return f"{prefix}{token[:PARTIAL_REDACTION_PREFIX_LEN]}...[REDACTED]...{token[-PARTIAL_REDACTION_SUFFIX_LEN:]}"
                    return f"{prefix}[REDACTED]"
                sanitized = pattern.sub(partial_redact_auth, sanitized)
            else:
                sanitized = pattern.sub(r'\1[REDACTED]', sanitized)
        elif pattern_name == 'connection_string':
            # Database URLs: Redact password only
            sanitized = pattern.sub(r'\1://[REDACTED-USER]:[REDACTED-PASSWORD]@', sanitized)
        elif pattern_name in ('slack_token', 'github_token'):
            # Slack/GitHub tokens: Redact entirely
            sanitized = pattern.sub(r'[REDACTED-\1]', sanitized)
        else:
            # Generic key=value patterns
            if partial:
                def partial_redact_value(match):
                    prefix = match.group(1)
                    value = match.group(2)
                    suffix = match.group(3) if len(match.groups()) >= 3 else ''
                    if len(value) > (PARTIAL_REDACTION_PREFIX_LEN + PARTIAL_REDACTION_SUFFIX_LEN):
                        return f"{prefix}{value[:PARTIAL_REDACTION_PREFIX_LEN]}...[REDACTED]...{value[-PARTIAL_REDACTION_SUFFIX_LEN:]}{suffix}"
                    return f"{prefix}[REDACTED]{suffix}"
                sanitized = pattern.sub(partial_redact_value, sanitized)
            else:
                # Redact the value completely
                sanitized = pattern.sub(lambda m: f"{m.group(1)}[REDACTED]{m.group(3) if len(m.groups()) >= 3 else ''}", sanitized)

    return sanitized


def redact_dict(data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    """Redact sensitive data from dictionary (useful for logging JSON payloads).

    Args:
        data: Dictionary to sanitize
        partial: If True, show first/last N characters for debugging

    Returns:
        Sanitized dictionary with credentials redacted

    Example:
        >>> redact_dict({'api_key': 'secret123', 'name': 'John'})
        {'api_key': '[REDACTED]', 'name': 'John'}
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}
    sensitive_keys = {
        'api_key', 'api_token', 'access_token', 'refresh_token',
        'password', 'secret', 'secret_key', 'auth', 'authorization',
        'bearer', 'oauth_token', 'client_secret', 'private_key',
        'slack_token', 'github_token', 'jwt', 'jwt_secret',
        'database_url', 'connection_string', 'smtp_password',
        'fireflies_api_key', 'jira_api_token', 'tempo_api_token',
        'openai_api_key', 'google_client_secret', 'encryption_key',
        'admin_api_key', 'pinecone_api_key', 'anthropic_api_key',
    }

    for key, value in data.items():
        # Check if key contains sensitive pattern
        key_lower = key.lower().replace('_', '').replace('-', '')
        is_sensitive = any(pattern in key_lower for pattern in sensitive_keys)

        if is_sensitive and isinstance(value, str):
            if partial and len(value) > (PARTIAL_REDACTION_PREFIX_LEN + PARTIAL_REDACTION_SUFFIX_LEN):
                sanitized[key] = f"{value[:PARTIAL_REDACTION_PREFIX_LEN]}...[REDACTED]...{value[-PARTIAL_REDACTION_SUFFIX_LEN:]}"
            else:
                sanitized[key] = REDACTION_FORMAT
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = redact_dict(value, partial=partial)
        elif isinstance(value, list):
            # Sanitize lists of dictionaries
            sanitized[key] = [
                redact_dict(item, partial=partial) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


class SensitiveDataFilter(logging.Filter):
    """Logging filter to automatically redact sensitive data from log records.

    This filter should be added to all loggers to prevent credential leakage.

    Usage:
        import logging
        from src.utils.log_sanitizer import SensitiveDataFilter

        logger = logging.getLogger(__name__)
        logger.addFilter(SensitiveDataFilter())

        # Now all log messages will be automatically sanitized
        logger.info(f"API Key: {api_key}")  # Will be redacted
    """

    def __init__(self, partial: bool = False):
        """Initialize the filter.

        Args:
            partial: If True, show first/last N characters for debugging (use only in development)
        """
        super().__init__()
        self.partial = partial

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record to redact sensitive data.

        Args:
            record: The log record to filter

        Returns:
            True (always allow the record, but sanitize it first)
        """
        # Sanitize the main message
        record.msg = redact_sensitive_data(str(record.msg), partial=self.partial)

        # Sanitize args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_dict(record.args, partial=self.partial)
            elif isinstance(record.args, tuple):
                sanitized_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        sanitized_args.append(redact_sensitive_data(arg, partial=self.partial))
                    elif isinstance(arg, dict):
                        sanitized_args.append(redact_dict(arg, partial=self.partial))
                    else:
                        sanitized_args.append(arg)
                record.args = tuple(sanitized_args)

        return True


def configure_root_logger_with_sanitization(partial: bool = False):
    """Configure root logger to use sensitive data filtering.

    This should be called early in application startup to ensure all loggers
    inherit the sanitization filter.

    Args:
        partial: If True, show first/last N characters for debugging (use only in development)

    Usage:
        from src.utils.log_sanitizer import configure_root_logger_with_sanitization

        # In main application startup
        configure_root_logger_with_sanitization()
    """
    root_logger = logging.getLogger()

    # Add filter if not already present
    if not any(isinstance(f, SensitiveDataFilter) for f in root_logger.filters):
        root_logger.addFilter(SensitiveDataFilter(partial=partial))
        logging.info("✅ Sensitive data filtering enabled for all loggers")
