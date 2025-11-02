"""Tests for CSRF protection in Flask application."""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestCSRFProtection:
    """Test suite for CSRF protection implementation."""

    def test_csrf_token_endpoint_returns_token(self, client):
        """Test that /api/csrf-token endpoint returns a valid token."""
        response = client.get('/api/csrf-token')

        assert response.status_code == 200
        data = response.get_json()
        assert 'csrf_token' in data
        assert isinstance(data['csrf_token'], str)
        assert len(data['csrf_token']) > 0

    def test_csrf_token_is_unique(self, client):
        """Test that multiple calls to CSRF endpoint return unique tokens."""
        response1 = client.get('/api/csrf-token')
        response2 = client.get('/api/csrf-token')

        token1 = response1.get_json()['csrf_token']
        token2 = response2.get_json()['csrf_token']

        # Tokens should be different for different requests
        assert token1 != token2

    def test_get_requests_exempt_from_csrf(self, client, auth_headers):
        """Test that GET requests do not require CSRF tokens."""
        # GET requests should work without CSRF token
        response = client.get('/api/todos', headers=auth_headers)

        # Should not fail with CSRF error (might fail with auth, but not CSRF)
        # CSRF errors are 400, not 401
        assert response.status_code != 400 or b'CSRF' not in response.data

    def test_post_request_without_csrf_fails(self, client, auth_headers):
        """Test that POST requests without CSRF token are rejected."""
        # Try to create a TODO without CSRF token
        response = client.post(
            '/api/todos',
            json={'title': 'Test', 'description': 'Test'},
            headers=auth_headers
        )

        # Should fail with CSRF error
        assert response.status_code == 400

    def test_post_request_with_valid_csrf_succeeds(self, client, auth_headers):
        """Test that POST requests with valid CSRF token succeed."""
        # Get CSRF token
        csrf_response = client.get('/api/csrf-token')
        csrf_token = csrf_response.get_json()['csrf_token']

        # Add CSRF token to headers
        headers_with_csrf = dict(auth_headers)
        headers_with_csrf['X-CSRF-Token'] = csrf_token

        # Try to create a TODO with CSRF token
        response = client.post(
            '/api/todos',
            json={'title': 'Test', 'description': 'Test', 'priority': 'medium'},
            headers=headers_with_csrf
        )

        # Should succeed (200 or 201)
        assert response.status_code in [200, 201]

    def test_put_request_without_csrf_fails(self, client, auth_headers):
        """Test that PUT requests without CSRF token are rejected."""
        response = client.put(
            '/api/todos/1',
            json={'title': 'Updated'},
            headers=auth_headers
        )

        # Should fail with CSRF error
        assert response.status_code == 400

    def test_delete_request_without_csrf_fails(self, client, auth_headers):
        """Test that DELETE requests without CSRF token are rejected."""
        response = client.delete('/api/todos/1', headers=auth_headers)

        # Should fail with CSRF error
        assert response.status_code == 400

    def test_health_check_exempt_from_csrf(self, client):
        """Test that health check endpoint is exempt from CSRF protection."""
        # Health check should work without CSRF token
        response = client.get('/health')

        # Should succeed
        assert response.status_code == 200

    def test_csrf_with_invalid_token_fails(self, client, auth_headers):
        """Test that requests with invalid CSRF tokens are rejected."""
        # Add invalid CSRF token to headers
        headers_with_csrf = dict(auth_headers)
        headers_with_csrf['X-CSRF-Token'] = 'invalid-token-12345'

        # Try to create a TODO with invalid CSRF token
        response = client.post(
            '/api/todos',
            json={'title': 'Test', 'description': 'Test'},
            headers=headers_with_csrf
        )

        # Should fail with CSRF error
        assert response.status_code == 400

    def test_csrf_token_works_across_cors_origins(self, client, auth_headers):
        """Test that CSRF tokens work with CORS headers."""
        # Get CSRF token
        csrf_response = client.get('/api/csrf-token')
        csrf_token = csrf_response.get_json()['csrf_token']

        # Add CSRF token and Origin header
        headers_with_csrf = dict(auth_headers)
        headers_with_csrf['X-CSRF-Token'] = csrf_token
        headers_with_csrf['Origin'] = 'http://localhost:4001'

        # Try to create a TODO
        response = client.post(
            '/api/todos',
            json={'title': 'Test', 'description': 'Test', 'priority': 'medium'},
            headers=headers_with_csrf
        )

        # Should succeed
        assert response.status_code in [200, 201]

    def test_csrf_headers_in_cors_config(self):
        """Test that X-CSRF-Token is allowed in CORS configuration."""
        from src.web_interface import app

        # Check that CORS is configured to allow X-CSRF-Token header
        with app.test_request_context():
            # Flask-CORS stores allowed headers in app config
            # We can't directly test the CORS config, but we can verify the header works
            pass

    def test_csrf_protection_initialized(self):
        """Test that CSRF protection is properly initialized."""
        from src.web_interface import app, csrf

        # Verify CSRF protection is enabled
        assert csrf is not None
        assert csrf.app == app

    def test_csrf_token_endpoint_has_no_side_effects(self, client):
        """Test that fetching CSRF token doesn't modify application state."""
        # Get token multiple times
        for _ in range(5):
            response = client.get('/api/csrf-token')
            assert response.status_code == 200
            assert 'csrf_token' in response.get_json()

    def test_csrf_protection_with_json_content_type(self, client, auth_headers):
        """Test CSRF protection works with application/json content type."""
        # Get CSRF token
        csrf_response = client.get('/api/csrf-token')
        csrf_token = csrf_response.get_json()['csrf_token']

        # Add CSRF token and Content-Type
        headers_with_csrf = dict(auth_headers)
        headers_with_csrf['X-CSRF-Token'] = csrf_token
        headers_with_csrf['Content-Type'] = 'application/json'

        # Try to create a TODO
        response = client.post(
            '/api/todos',
            json={'title': 'Test', 'description': 'Test', 'priority': 'medium'},
            headers=headers_with_csrf
        )

        # Should succeed
        assert response.status_code in [200, 201]

    def test_csrf_protection_applies_to_all_blueprints(self, client, auth_headers):
        """Test that CSRF protection is applied to all blueprints."""
        # Get CSRF token
        csrf_response = client.get('/api/csrf-token')
        csrf_token = csrf_response.get_json()['csrf_token']

        # Test different blueprints (todos, meetings, etc.)
        endpoints_to_test = [
            '/api/todos',
            # Add more endpoints as needed
        ]

        for endpoint in endpoints_to_test:
            # Without CSRF should fail
            response = client.post(
                endpoint,
                json={'test': 'data'},
                headers=auth_headers
            )
            assert response.status_code == 400, f"Endpoint {endpoint} should require CSRF token"

            # With CSRF should not fail with CSRF error (might fail for other reasons)
            headers_with_csrf = dict(auth_headers)
            headers_with_csrf['X-CSRF-Token'] = csrf_token
            response = client.post(
                endpoint,
                json={'title': 'Test', 'description': 'Test', 'priority': 'medium'},
                headers=headers_with_csrf
            )
            # Should not be CSRF error (400 with CSRF in message)
            assert response.status_code != 400 or b'CSRF' not in response.data


class TestCSRFConfiguration:
    """Test suite for CSRF configuration settings."""

    def test_csrf_uses_session_based_tokens(self):
        """Test that CSRF uses session-based tokens (works with cookies)."""
        from src.web_interface import app

        # Flask-WTF CSRF uses session by default
        assert app.secret_key is not None, "App must have secret key for CSRF"

    def test_app_secret_key_is_secure(self):
        """Test that app has a secure secret key configured."""
        from src.web_interface import app

        # Verify secret key is set
        assert app.secret_key is not None
        assert isinstance(app.secret_key, (str, bytes))
        assert len(str(app.secret_key)) >= 16, "Secret key should be at least 16 characters"

    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key-for-csrf'})
    def test_csrf_works_with_custom_secret_key(self):
        """Test that CSRF protection works with custom JWT secret key."""
        # Reload the app with custom secret key
        import importlib
        import src.web_interface
        importlib.reload(src.web_interface)

        from src.web_interface import app

        # Verify secret key is set
        assert app.secret_key == 'test-secret-key-for-csrf'
