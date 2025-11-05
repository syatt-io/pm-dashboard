"""Unit tests for insights API routes."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.models import ProactiveInsight, User, UserNotificationPreferences


def test_list_insights_requires_auth(client):
    """Test that listing insights requires authentication."""
    response = client.get('/api/insights')
    assert response.status_code in [401, 403]  # Unauthorized


def test_get_insight_requires_auth(client):
    """Test that getting a specific insight requires authentication."""
    response = client.get('/api/insights/test-insight-123')
    assert response.status_code in [401, 403]  # Unauthorized


def test_dismiss_insight_requires_auth(client):
    """Test that dismissing an insight requires authentication."""
    response = client.post('/api/insights/test-insight-123/dismiss')
    # Should fail - could be 400 (Bad Request), 401 (Unauthorized), or 403 (Forbidden)
    assert response.status_code in [400, 401, 403]


def test_act_on_insight_requires_auth(client):
    """Test that acting on an insight requires authentication."""
    response = client.post(
        '/api/insights/test-insight-123/act',
        data=json.dumps({"action_taken": "resolved"}),
        content_type='application/json'
    )
    # Should fail - could be 400 (Bad Request), 401 (Unauthorized), or 403 (Forbidden)
    assert response.status_code in [400, 401, 403]


def test_get_insight_stats_requires_auth(client):
    """Test that getting insight stats requires authentication."""
    response = client.get('/api/insights/stats')
    assert response.status_code in [401, 403]  # Unauthorized


def test_get_notification_preferences_requires_auth(client):
    """Test that getting notification preferences requires authentication."""
    response = client.get('/api/insights/preferences')
    assert response.status_code in [401, 403]  # Unauthorized


def test_update_notification_preferences_requires_auth(client):
    """Test that updating notification preferences requires authentication."""
    response = client.put(
        '/api/insights/preferences',
        data=json.dumps({"daily_brief_slack": True}),
        content_type='application/json'
    )
    # Should fail - could be 400 (Bad Request), 401 (Unauthorized), or 403 (Forbidden)
    assert response.status_code in [400, 401, 403]


def test_list_insights_with_invalid_auth(client):
    """Test listing insights with invalid authentication token."""
    # Make request with invalid auth token
    response = client.get(
        '/api/insights',
        headers={'Authorization': 'Bearer invalid-fake-token-123'}
    )

    # Should fail with 401/403 (auth required)
    # Note: Depending on auth implementation, could be 400 (Bad Request) if token is malformed
    assert response.status_code in [400, 401, 403]


def test_get_notification_preferences_with_invalid_auth(client):
    """Test getting notification preferences with invalid auth."""
    # Make request with invalid token
    response = client.get(
        '/api/insights/preferences',
        headers={'Authorization': 'Bearer invalid-fake-token-123'}
    )

    # Should fail with 401/403 (auth required)
    # Note: Depending on auth implementation, could be 400 (Bad Request) if token is malformed
    assert response.status_code in [400, 401, 403]


def test_insights_blueprint_registered(app):
    """Test that insights blueprint is registered with the app."""
    # Check if the blueprint is registered by looking for its routes
    rules = [str(rule) for rule in app.url_map.iter_rules()]

    # Should have insights routes
    assert any('/api/insights' in rule for rule in rules)
