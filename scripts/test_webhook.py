#!/usr/bin/env python3
"""
Test Fireflies webhook endpoint with mock payload.

This script sends a test webhook request to verify:
1. Endpoint is accessible
2. Signature verification works correctly
3. Environment variables are properly configured

Usage:
    python scripts/test_webhook.py [--production]
"""
import hmac
import hashlib
import requests
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def generate_signature(payload_json: str, secret: str) -> str:
    """Generate HMAC SHA-256 signature for webhook payload."""
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f'sha256={signature}'


def test_webhook(base_url: str, webhook_secret: str):
    """Test webhook endpoint with various scenarios."""
    webhook_url = f'{base_url}/api/webhooks/fireflies'

    print(f"\n🧪 Testing Fireflies Webhook Endpoint")
    print(f"📍 URL: {webhook_url}")
    print("=" * 60)

    # Test 1: Valid webhook request
    print("\n✅ Test 1: Valid webhook with correct signature")
    payload = {
        "event": "transcript.completed",
        "meetingId": "TEST_MEETING_123",
        "eventType": "transcription_complete"
    }
    payload_json = json.dumps(payload)
    signature = generate_signature(payload_json, webhook_secret)

    try:
        response = requests.post(
            webhook_url,
            data=payload_json,
            headers={
                'Content-Type': 'application/json',
                'x-hub-signature': signature
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'already_processed':
                print("   ✅ PASS: Meeting already processed (idempotency working)")
            elif result.get('status') == 'enqueued':
                print("   ✅ PASS: Webhook accepted and Celery task enqueued")
            else:
                print(f"   ⚠️  WARNING: Unexpected status: {result.get('status')}")
        else:
            print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

    # Test 2: Invalid signature
    print("\n❌ Test 2: Invalid signature (should be rejected)")
    invalid_signature = 'sha256=invalid_signature_here'

    try:
        response = requests.post(
            webhook_url,
            data=payload_json,
            headers={
                'Content-Type': 'application/json',
                'x-hub-signature': invalid_signature
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 401:
            print("   ✅ PASS: Invalid signature correctly rejected with 401")
        else:
            print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

    # Test 3: Missing signature
    print("\n❌ Test 3: Missing signature header (should be rejected)")

    try:
        response = requests.post(
            webhook_url,
            data=payload_json,
            headers={
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 401:
            print("   ✅ PASS: Missing signature correctly rejected with 401")
        else:
            print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

    # Test 4: Non-completion event (should be ignored)
    print("\n⏭️  Test 4: Non-completion event (should be ignored)")
    ignore_payload = {
        "event": "transcript.started",
        "meetingId": "TEST_MEETING_456",
        "eventType": "transcription_started"
    }
    ignore_json = json.dumps(ignore_payload)
    ignore_signature = generate_signature(ignore_json, webhook_secret)

    try:
        response = requests.post(
            webhook_url,
            data=ignore_json,
            headers={
                'Content-Type': 'application/json',
                'x-hub-signature': ignore_signature
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'ignored':
                print("   ✅ PASS: Non-completion event correctly ignored")
            else:
                print(f"   ⚠️  WARNING: Unexpected status: {result.get('status')}")
        else:
            print(f"   ❌ FAIL: Expected 200, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

    print("\n" + "=" * 60)
    print("🏁 Test suite complete!")
    print("\n📝 Next steps:")
    print("   1. Check application logs for webhook processing details")
    print("   2. Verify Celery worker logs for task execution")
    print("   3. Confirm meeting analysis stored in database")
    print("   4. Test with real Fireflies meeting to validate end-to-end")


if __name__ == '__main__':
    # Determine environment
    use_production = '--production' in sys.argv or '-p' in sys.argv

    if use_production:
        base_url = 'https://agent-pm-tsbbb.ondigitalocean.app'
        print("\n⚠️  PRODUCTION MODE: Testing against live production endpoint")
    else:
        base_url = 'http://localhost:4000'
        print("\n🧪 LOCAL MODE: Testing against local development server")

    # Get webhook secret
    webhook_secret = os.getenv('FIREFLIES_WEBHOOK_SECRET')

    if not webhook_secret:
        print("\n❌ ERROR: FIREFLIES_WEBHOOK_SECRET not found in environment")
        print("   Please ensure .env file exists with the webhook secret")
        sys.exit(1)

    print(f"🔑 Using webhook secret: {webhook_secret[:8]}... (hidden)")

    # Run tests
    test_webhook(base_url, webhook_secret)
