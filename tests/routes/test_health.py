"""Tests for health check endpoints."""

import pytest
from datetime import datetime


def test_health_endpoint(client):
    """Test basic health check endpoint."""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
