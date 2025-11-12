"""API endpoint caching manager using Redis.

Provides decorators and utilities for caching API responses with configurable TTL
and smart invalidation strategies.
"""

import json
import logging
import os
import hashlib
import functools
from typing import Any, Optional, Dict, Callable
from datetime import datetime
import redis
from flask import request, jsonify

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages API endpoint caching using Redis."""

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize cache manager.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        self._enabled = True

        # Try to connect, but don't fail if Redis is unavailable
        try:
            self._connect()
            logger.info(f"Cache manager initialized: {self._mask_url(self.redis_url)}")
        except Exception as e:
            logger.warning(f"Redis connection failed (caching disabled): {e}")
            self._enabled = False

    def _mask_url(self, url: str) -> str:
        """Mask password in Redis URL for logging."""
        if "@" in url and "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                auth, host = rest.rsplit("@", 1)
                return f"{protocol}://***:***@{host}"
        return url

    def _connect(self):
        """Establish Redis connection."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,  # Auto-decode to strings
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Test connection
            self._client.ping()

    def _generate_cache_key(self, prefix: str, user_id: Optional[int], **kwargs) -> str:
        """Generate cache key from prefix, user_id, and additional parameters.

        Args:
            prefix: Cache key prefix (e.g., 'projects', 'meetings')
            user_id: User ID for user-specific caching (None for global cache)
            **kwargs: Additional parameters to include in cache key

        Returns:
            Cache key string
        """
        # Build key components
        key_parts = [f"api_cache:{prefix}"]

        if user_id is not None:
            key_parts.append(f"user:{user_id}")

        # Add query parameters (sorted for consistent keys)
        if kwargs:
            param_str = json.dumps(kwargs, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(f"params:{param_hash}")

        return ":".join(key_parts)

    def get(
        self, prefix: str, user_id: Optional[int] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached data.

        Args:
            prefix: Cache key prefix
            user_id: User ID for user-specific cache
            **kwargs: Additional parameters for cache key

        Returns:
            Cached data dict or None if not found
        """
        if not self._enabled:
            return None

        try:
            if self._client is None:
                self._connect()

            key = self._generate_cache_key(prefix, user_id, **kwargs)
            data = self._client.get(key)

            if data is None:
                logger.debug(f"Cache MISS: {key}")
                return None

            logger.info(f"Cache HIT: {key}")
            return json.loads(data)

        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None

    def set(
        self,
        data: Dict[str, Any],
        prefix: str,
        ttl: int,
        user_id: Optional[int] = None,
        **kwargs,
    ) -> bool:
        """Store data in cache.

        Args:
            data: Data to cache (must be JSON-serializable)
            prefix: Cache key prefix
            ttl: Time-to-live in seconds
            user_id: User ID for user-specific cache
            **kwargs: Additional parameters for cache key

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            return False

        try:
            if self._client is None:
                self._connect()

            key = self._generate_cache_key(prefix, user_id, **kwargs)

            # Add cache metadata
            cached_data = {
                "data": data,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl": ttl,
            }

            serialized = json.dumps(cached_data)
            self._client.setex(key, ttl, serialized)
            logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error storing in cache: {e}")
            return False

    def invalidate(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., 'api_cache:projects:*')

        Returns:
            Number of keys deleted
        """
        if not self._enabled:
            return 0

        try:
            if self._client is None:
                self._connect()

            keys = self._client.keys(pattern)
            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"Cache INVALIDATE: {pattern} ({deleted} keys deleted)")
                return deleted
            return 0

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

    def clear_all(self) -> bool:
        """Clear all API cache entries.

        Returns:
            True if successful, False otherwise
        """
        return self.invalidate("api_cache:*") >= 0


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """Get or create the global cache manager.

    Args:
        redis_url: Optional Redis URL (uses REDIS_URL env var by default)

    Returns:
        CacheManager instance
    """
    global _cache_manager

    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url=redis_url)

    return _cache_manager


def cached_endpoint(
    prefix: str, ttl: int, user_specific: bool = True, exclude_params: list = None
):
    """Decorator for caching endpoint responses.

    Args:
        prefix: Cache key prefix (e.g., 'projects', 'meetings')
        ttl: Cache time-to-live in seconds
        user_specific: Whether to cache per-user (default: True)
        exclude_params: List of query params to exclude from cache key (e.g., ['page', 'perPage'])

    Usage:
        @cached_endpoint('projects', ttl=3600, user_specific=True)
        @auth_required
        def get_projects(user):
            # ... fetch projects logic
            return jsonify({'data': projects})

        # For paginated endpoints, exclude pagination params from cache key:
        @cached_endpoint('meetings', ttl=3600, user_specific=True, exclude_params=['page', 'perPage'])
        @auth_required
        def get_meetings(user):
            # This caches the full dataset, pagination happens in-memory
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Extract user_id if user_specific
            user_id = None
            if user_specific:
                # Try to get user from kwargs (passed by auth_required decorator)
                user = kwargs.get("user")
                if user and hasattr(user, "id"):
                    user_id = user.id

            # Build cache key parameters from request, excluding specified params
            cache_params = {}
            if request.args:
                excluded = set(exclude_params or [])
                cache_params = {
                    k: v for k, v in request.args.items() if k not in excluded
                }

            # Try to get from cache
            cached_data = cache.get(prefix, user_id=user_id, **cache_params)
            if cached_data is not None:
                # Return cached response with cache metadata headers
                response = jsonify(cached_data["data"])
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-Time"] = cached_data.get("cached_at", "")
                return response

            # Call original function
            result = func(*args, **kwargs)

            # Cache the response if it's successful
            if result and hasattr(result, "json") and hasattr(result, "status_code"):
                if 200 <= result.status_code < 300:
                    try:
                        response_data = result.get_json()
                        cache.set(
                            response_data, prefix, ttl, user_id=user_id, **cache_params
                        )
                        # Add cache miss header
                        result.headers["X-Cache"] = "MISS"
                    except Exception as e:
                        logger.warning(f"Failed to cache response: {e}")

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str):
    """Invalidate cache entries matching pattern.

    Args:
        pattern: Redis key pattern (e.g., 'api_cache:projects:*')

    Returns:
        Number of keys deleted
    """
    cache = get_cache_manager()
    return cache.invalidate(pattern)
