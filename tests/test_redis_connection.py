#!/usr/bin/env python3
"""Quick script to test Redis connection in production."""

import os
import sys

def test_redis():
    """Test Redis connectivity."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    print(f"Testing Redis connection to: {mask_password(redis_url)}")

    try:
        import redis
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )

        # Test ping
        client.ping()
        print("✅ Redis PING successful")

        # Test set/get
        test_key = "slack_conv_test:test"
        client.setex(test_key, 60, "test_value")
        value = client.get(test_key)

        if value == "test_value":
            print("✅ Redis SET/GET successful")
        else:
            print(f"❌ Redis GET returned unexpected value: {value}")

        # Clean up
        client.delete(test_key)
        print("✅ Redis connection working perfectly!")

        return True

    except ImportError:
        print("❌ Redis library not installed")
        return False
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False


def mask_password(url: str) -> str:
    """Mask password in URL for safe logging."""
    if '@' in url and '://' in url:
        protocol, rest = url.split('://', 1)
        if '@' in rest:
            auth, host = rest.rsplit('@', 1)
            return f"{protocol}://***@{host}"
    return url


if __name__ == "__main__":
    success = test_redis()
    sys.exit(0 if success else 1)
