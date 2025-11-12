"""Retry logic utilities for external API calls.

This module provides decorators and functions for adding robust retry logic
to external API calls (Fireflies, Jira, Tempo, AI providers, etc.).

Uses exponential backoff with jitter to avoid thundering herd problems.
"""

import logging
import time
import functools
from typing import Callable, Any, Tuple, Type, Optional, List
import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError, RequestException

logger = logging.getLogger(__name__)


# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0

# Retriable HTTP status codes
RETRIABLE_STATUS_CODES = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# Retriable exception types
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    Timeout,
    ConnectionError,
    # Don't retry on HTTPError by default - we'll check status codes
)


def exponential_backoff(
    attempt: int, base_delay: float, max_delay: float, backoff_factor: float
) -> float:
    """Calculate exponential backoff with jitter.

    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Backoff multiplier

    Returns:
        Delay in seconds with jitter added
    """
    import random

    # Calculate exponential delay: base_delay * (backoff_factor ^ attempt)
    delay = min(base_delay * (backoff_factor**attempt), max_delay)

    # Add jitter (±25% of delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    return max(0, delay + jitter)


def is_retriable_error(exception: Exception) -> bool:
    """Determine if an exception is retriable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception should trigger a retry
    """
    # Check if it's a retriable exception type
    if isinstance(exception, RETRIABLE_EXCEPTIONS):
        return True

    # Special handling for HTTPError - check status code
    if isinstance(exception, HTTPError):
        if hasattr(exception, "response") and exception.response is not None:
            return exception.response.status_code in RETRIABLE_STATUS_CODES

    return False


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    retriable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    retriable_status_codes: Optional[set] = None,
):
    """Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Backoff multiplier (default 2.0 = exponential)
        retriable_exceptions: Tuple of exception types to retry
        retriable_status_codes: Set of HTTP status codes to retry

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fetch_data():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Use provided or default retriable exceptions
            exceptions_to_retry = retriable_exceptions or RETRIABLE_EXCEPTIONS
            status_codes_to_retry = retriable_status_codes or RETRIABLE_STATUS_CODES

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions_to_retry as e:
                    last_exception = e

                    # Check if we should retry
                    should_retry = False

                    # Check retriable exception types
                    if isinstance(e, exceptions_to_retry):
                        should_retry = True

                    # Special handling for HTTPError
                    if isinstance(e, HTTPError):
                        if hasattr(e, "response") and e.response is not None:
                            should_retry = (
                                e.response.status_code in status_codes_to_retry
                            )

                    # If this is the last attempt, or not retriable, raise
                    if attempt >= max_retries or not should_retry:
                        logger.error(
                            f"{func.__name__} failed after {attempt + 1} attempts: {e}",
                            exc_info=True,
                        )
                        raise

                    # Calculate backoff delay
                    delay = exponential_backoff(
                        attempt, base_delay, max_delay, backoff_factor
                    )

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

                except Exception as e:
                    # Non-retriable exception - raise immediately
                    logger.error(
                        f"{func.__name__} failed with non-retriable error: {e}",
                        exc_info=True,
                    )
                    raise

            # Should never reach here, but just in case
            raise last_exception

        return wrapper

    return decorator


def retry_requests_call(
    func: Callable,
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    **kwargs,
) -> Any:
    """Retry a requests library call with exponential backoff.

    This is a functional interface for cases where a decorator is not convenient.

    Args:
        func: Function to call (should return requests.Response)
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result of func(*args, **kwargs)

    Example:
        response = retry_requests_call(
            requests.get,
            "https://api.example.com/data",
            headers={"Authorization": "Bearer token"},
            max_retries=3
        )
    """

    @retry_with_backoff(max_retries=max_retries, base_delay=base_delay)
    def wrapper():
        return func(*args, **kwargs)

    return wrapper()


def retry_langchain_call(
    func: Callable,
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    **kwargs,
) -> Any:
    """Retry a LangChain LLM call with exponential backoff.

    Handles LangChain-specific exceptions and rate limiting.

    Args:
        func: LLM function to call
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result of func(*args, **kwargs)

    Example:
        response = retry_langchain_call(
            llm.invoke,
            messages,
            max_retries=3
        )
    """

    # LangChain may raise different exceptions, so we need broader exception handling
    @retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        retriable_exceptions=(Exception,),  # Catch all for LLM calls
    )
    def wrapper():
        return func(*args, **kwargs)

    return wrapper()


# Convenience functions for common API patterns


def retry_graphql_request(
    url: str,
    query: str,
    variables: dict,
    headers: dict,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = 30,
) -> dict:
    """Retry a GraphQL request with exponential backoff.

    Args:
        url: GraphQL endpoint URL
        query: GraphQL query string
        variables: Query variables
        headers: HTTP headers
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds

    Returns:
        GraphQL response as dict

    Example:
        response = retry_graphql_request(
            "https://api.fireflies.ai/graphql",
            "query { transcripts { id title } }",
            {},
            {"Authorization": "Bearer token"}
        )
    """

    @retry_with_backoff(max_retries=max_retries)
    def make_request():
        payload = {"query": query, "variables": variables}
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()

    return make_request()


def retry_rest_request(
    method: str,
    url: str,
    headers: dict,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = 30,
    **kwargs,
) -> requests.Response:
    """Retry a REST API request with exponential backoff.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        url: API endpoint URL
        headers: HTTP headers
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        **kwargs: Additional arguments for requests (params, json, data, etc.)

    Returns:
        Response object

    Example:
        response = retry_rest_request(
            "GET",
            "https://api.tempo.io/4/worklogs",
            {"Authorization": "Bearer token"},
            params={"from": "2025-01-01", "to": "2025-01-31"}
        )
    """

    @retry_with_backoff(max_retries=max_retries)
    def make_request():
        response = requests.request(
            method, url, headers=headers, timeout=timeout, **kwargs
        )
        response.raise_for_status()
        return response

    return make_request()


# Metrics and monitoring


class RetryMetrics:
    """Track retry metrics for monitoring and alerting."""

    def __init__(self):
        self.total_calls = 0
        self.total_retries = 0
        self.total_failures = 0
        self.retry_counts: dict = {}  # function_name -> retry count

    def record_call(self, function_name: str):
        """Record a function call."""
        self.total_calls += 1
        if function_name not in self.retry_counts:
            self.retry_counts[function_name] = 0

    def record_retry(self, function_name: str):
        """Record a retry attempt."""
        self.total_retries += 1
        if function_name in self.retry_counts:
            self.retry_counts[function_name] += 1

    def record_failure(self, function_name: str):
        """Record a final failure after all retries."""
        self.total_failures += 1

    def get_stats(self) -> dict:
        """Get retry statistics."""
        return {
            "total_calls": self.total_calls,
            "total_retries": self.total_retries,
            "total_failures": self.total_failures,
            "retry_rate": (
                self.total_retries / self.total_calls if self.total_calls > 0 else 0
            ),
            "failure_rate": (
                self.total_failures / self.total_calls if self.total_calls > 0 else 0
            ),
            "by_function": self.retry_counts,
        }

    def reset(self):
        """Reset all metrics."""
        self.total_calls = 0
        self.total_retries = 0
        self.total_failures = 0
        self.retry_counts.clear()


# Global metrics instance
metrics = RetryMetrics()
