"""Log sanitization utility to prevent sensitive data from appearing in logs.

This module provides functions to sanitize sensitive information from log messages,
including API tokens, passwords, session tokens, and other credentials.

Usage:
    from src.utils.log_sanitizer import sanitize_for_logging

    # Sanitize a dictionary before logging
    safe_data = sanitize_for_logging(user_data)
    logger.info(f"User data: {safe_data}")

    # Sanitize a string
    safe_message = sanitize_for_logging(error_message)
    logger.error(f"Error: {safe_message}")
"""

import re
from typing import Any, Dict, List, Union


# Sensitive field names (case-insensitive)
SENSITIVE_FIELDS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "refresh_token",
    "bearer",
    "authorization",
    "auth",
    "session",
    "session_id",
    "sessionid",
    "cookie",
    "csrf",
    "xsrf",
    "private_key",
    "privatekey",
    "client_secret",
    "encryption_key",
    "signing_secret",
}

# Regex patterns for sensitive data in strings
SENSITIVE_PATTERNS = [
    # API tokens (common formats)
    (re.compile(r"(xox[a-z]-[a-zA-Z0-9-]+)"), "[SLACK_TOKEN]"),
    (re.compile(r"(sk-[a-zA-Z0-9]{32,})"), "[OPENAI_KEY]"),
    (re.compile(r"(ghp_[a-zA-Z0-9]{36})"), "[GITHUB_TOKEN]"),
    (re.compile(r"(gho_[a-zA-Z0-9]{36})"), "[GITHUB_TOKEN]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+([a-zA-Z0-9._-]+)", re.IGNORECASE), "Bearer [REDACTED]"),
    # AWS keys
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "[AWS_KEY]"),
    # Generic long alphanumeric strings that look like tokens (64+ chars)
    (
        re.compile(r"\b([a-zA-Z0-9]{64,})\b"),
        "[POSSIBLE_TOKEN]",
    ),
]


def sanitize_string(value: str) -> str:
    """Sanitize sensitive data from a string.

    Args:
        value: String that may contain sensitive data

    Returns:
        Sanitized string with sensitive data replaced
    """
    if not isinstance(value, str):
        return value

    result = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


def sanitize_dict(data: Dict[str, Any], max_depth: int = 5) -> Dict[str, Any]:
    """Sanitize sensitive fields from a dictionary.

    Args:
        data: Dictionary that may contain sensitive fields
        max_depth: Maximum recursion depth for nested dictionaries

    Returns:
        Sanitized dictionary with sensitive fields redacted
    """
    if max_depth <= 0:
        return {"...": "max_depth_reached"}

    sanitized = {}
    for key, value in data.items():
        # Check if field name is sensitive
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, max_depth - 1)
        elif isinstance(value, list):
            sanitized[key] = sanitize_list(value, max_depth - 1)
        elif isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        else:
            sanitized[key] = value

    return sanitized


def sanitize_list(data: List[Any], max_depth: int = 5) -> List[Any]:
    """Sanitize sensitive data from a list.

    Args:
        data: List that may contain sensitive data
        max_depth: Maximum recursion depth for nested structures

    Returns:
        Sanitized list
    """
    if max_depth <= 0:
        return ["...max_depth_reached..."]

    sanitized = []
    for item in data:
        if isinstance(item, dict):
            sanitized.append(sanitize_dict(item, max_depth - 1))
        elif isinstance(item, list):
            sanitized.append(sanitize_list(item, max_depth - 1))
        elif isinstance(item, str):
            sanitized.append(sanitize_string(item))
        else:
            sanitized.append(item)

    return sanitized


def sanitize_for_logging(
    data: Union[str, Dict, List, Any], max_depth: int = 5
) -> Union[str, Dict, List, Any]:
    """Sanitize any data structure for safe logging.

    This is the main entry point for log sanitization. It handles strings,
    dictionaries, lists, and other types appropriately.

    Args:
        data: Data to sanitize (string, dict, list, or other)
        max_depth: Maximum recursion depth for nested structures

    Returns:
        Sanitized data safe for logging

    Examples:
        >>> sanitize_for_logging({"api_key": "secret123", "user": "bob"})
        {'api_key': '[REDACTED]', 'user': 'bob'}

        >>> sanitize_for_logging("Bearer xoxb-1234-secret-token")
        'Bearer [REDACTED]'

        >>> sanitize_for_logging([{"password": "pass123"}, {"user": "alice"}])
        [{'password': '[REDACTED]'}, {'user': 'alice'}]
    """
    if isinstance(data, dict):
        return sanitize_dict(data, max_depth)
    elif isinstance(data, list):
        return sanitize_list(data, max_depth)
    elif isinstance(data, str):
        return sanitize_string(data)
    else:
        return data


# Convenience functions for common use cases


def sanitize_exception(exc: Exception) -> str:
    """Sanitize an exception message for logging.

    Args:
        exc: Exception to sanitize

    Returns:
        Sanitized exception message
    """
    return sanitize_string(str(exc))


def sanitize_url(url: str) -> str:
    """Sanitize a URL to hide query parameters that might contain tokens.

    Args:
        url: URL that may contain sensitive query parameters

    Returns:
        URL with query parameters redacted

    Example:
        >>> sanitize_url("https://api.com/users?token=secret123&user=bob")
        'https://api.com/users?[QUERY_PARAMS_REDACTED]'
    """
    if "?" in url:
        base_url = url.split("?")[0]
        return f"{base_url}?[QUERY_PARAMS_REDACTED]"
    return url
