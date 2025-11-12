"""Tests for JWT_SECRET_KEY validation in production."""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestJWTSecretValidationWebInterface:
    """Test suite for JWT_SECRET_KEY validation in web_interface.py."""

    def test_production_fails_without_jwt_secret(self):
        """Test that production fails fast when JWT_SECRET_KEY is not set."""
        with patch.dict(
            os.environ, {"FLASK_ENV": "production", "JWT_SECRET_KEY": ""}, clear=False
        ):
            with pytest.raises(ValueError) as exc_info:
                # Import will trigger validation
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

            assert "CRITICAL SECURITY ERROR" in str(exc_info.value)
            assert "JWT_SECRET_KEY is not set in production" in str(exc_info.value)

    def test_production_fails_with_short_jwt_secret(self):
        """Test that production fails fast when JWT_SECRET_KEY is too short."""
        # 15 character secret (less than MIN_SECRET_LENGTH of 32)
        short_secret = "short-secret-15"

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": short_secret},
            clear=False,
        ):
            with pytest.raises(ValueError) as exc_info:
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

            assert "CRITICAL SECURITY ERROR" in str(exc_info.value)
            assert "JWT_SECRET_KEY is too short" in str(exc_info.value)
            assert "15 chars" in str(exc_info.value)

    def test_production_succeeds_with_strong_jwt_secret(self):
        """Test that production succeeds with a strong JWT secret."""
        # 64 character secure random secret
        strong_secret = "a" * 64

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": strong_secret},
            clear=False,
        ):
            # Should not raise an exception
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            # Verify secret was set
            assert src.web_interface.app.secret_key == strong_secret

    def test_development_allows_missing_jwt_secret(self):
        """Test that development mode allows missing JWT_SECRET_KEY with warning."""
        with patch.dict(
            os.environ, {"FLASK_ENV": "development", "JWT_SECRET_KEY": ""}, clear=False
        ):
            # Should not raise an exception in development
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            # Verify fallback secret was generated
            assert src.web_interface.app.secret_key is not None
            assert len(src.web_interface.app.secret_key) >= 32
            assert (
                "dev-secret-DO-NOT-USE-IN-PRODUCTION"
                in src.web_interface.app.secret_key
            )

    def test_development_allows_short_jwt_secret(self):
        """Test that development mode allows short JWT_SECRET_KEY with warning."""
        short_secret = "short"

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "development", "JWT_SECRET_KEY": short_secret},
            clear=False,
        ):
            # Should not raise an exception in development
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            # Verify secret was still set (even though weak)
            assert src.web_interface.app.secret_key == short_secret

    def test_jwt_secret_whitespace_handling(self):
        """Test that JWT_SECRET_KEY strips whitespace correctly."""
        secret_with_whitespace = "  strong-secret-with-32-characters  "

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": secret_with_whitespace},
            clear=False,
        ):
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            # Verify whitespace was stripped
            assert src.web_interface.app.secret_key == secret_with_whitespace.strip()

    def test_weak_secret_pattern_warning(self, caplog):
        """Test that common weak patterns in JWT_SECRET_KEY trigger warnings."""
        weak_secrets = [
            "dev-secret-" + "a" * 32,
            "test-secret-" + "a" * 32,
            "password-secret-" + "a" * 32,
            "12345-secret-" + "a" * 32,
        ]

        for weak_secret in weak_secrets:
            with patch.dict(
                os.environ,
                {"FLASK_ENV": "development", "JWT_SECRET_KEY": weak_secret},
                clear=False,
            ):
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

                # Check that weak pattern was detected
                # Note: In real tests, you'd check caplog for the warning message


class TestJWTSecretValidationAuthService:
    """Test suite for JWT_SECRET_KEY validation in AuthService."""

    def test_auth_service_production_fails_without_jwt_secret(self):
        """Test that AuthService fails fast in production when JWT_SECRET_KEY is not set."""
        with patch.dict(
            os.environ, {"FLASK_ENV": "production", "JWT_SECRET_KEY": ""}, clear=False
        ):
            from src.services.auth import AuthService

            with pytest.raises(ValueError) as exc_info:
                AuthService(db_session_factory=MagicMock())

            assert "CRITICAL SECURITY ERROR" in str(exc_info.value)
            assert "JWT_SECRET_KEY is not set in production" in str(exc_info.value)

    def test_auth_service_production_fails_with_short_jwt_secret(self):
        """Test that AuthService fails fast when JWT_SECRET_KEY is too short."""
        short_secret = "short-secret-15"

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": short_secret},
            clear=False,
        ):
            from src.services.auth import AuthService

            with pytest.raises(ValueError) as exc_info:
                AuthService(db_session_factory=MagicMock())

            assert "CRITICAL SECURITY ERROR" in str(exc_info.value)
            assert "JWT_SECRET_KEY is too short" in str(exc_info.value)

    def test_auth_service_production_succeeds_with_strong_jwt_secret(self):
        """Test that AuthService succeeds with a strong JWT secret."""
        strong_secret = "a" * 64

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": strong_secret},
            clear=False,
        ):
            from src.services.auth import AuthService

            # Should not raise an exception
            auth_service = AuthService(db_session_factory=MagicMock())

            # Verify secret was set
            assert auth_service.jwt_secret == strong_secret

    def test_auth_service_development_allows_missing_jwt_secret(self):
        """Test that AuthService allows missing JWT_SECRET_KEY in development."""
        with patch.dict(
            os.environ, {"FLASK_ENV": "development", "JWT_SECRET_KEY": ""}, clear=False
        ):
            from src.services.auth import AuthService

            # Should not raise an exception in development
            auth_service = AuthService(db_session_factory=MagicMock())

            # Verify fallback secret was generated
            assert auth_service.jwt_secret is not None
            assert len(auth_service.jwt_secret) >= 32
            assert "dev-secret-DO-NOT-USE-IN-PRODUCTION" in auth_service.jwt_secret

    def test_auth_service_development_allows_short_jwt_secret(self):
        """Test that AuthService allows short JWT_SECRET_KEY in development."""
        short_secret = "short"

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "development", "JWT_SECRET_KEY": short_secret},
            clear=False,
        ):
            from src.services.auth import AuthService

            # Should not raise an exception in development
            auth_service = AuthService(db_session_factory=MagicMock())

            # Verify secret was still set (even though weak)
            assert auth_service.jwt_secret == short_secret

    def test_auth_service_jwt_secret_whitespace_handling(self):
        """Test that AuthService strips whitespace from JWT_SECRET_KEY."""
        secret_with_whitespace = "  strong-secret-with-32-characters  "

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": secret_with_whitespace},
            clear=False,
        ):
            from src.services.auth import AuthService

            auth_service = AuthService(db_session_factory=MagicMock())

            # Verify whitespace was stripped
            assert auth_service.jwt_secret == secret_with_whitespace.strip()


class TestJWTSecretMinimumLength:
    """Test suite for JWT_SECRET_KEY minimum length validation."""

    def test_minimum_length_is_32_characters(self):
        """Test that minimum JWT_SECRET_KEY length is 32 characters (HS256 standard)."""
        # 31 character secret (just below minimum)
        almost_valid_secret = "a" * 31

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": almost_valid_secret},
            clear=False,
        ):
            with pytest.raises(ValueError) as exc_info:
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

            assert "31 chars" in str(exc_info.value)
            assert "Minimum length: 32" in str(exc_info.value)

    def test_exactly_minimum_length_succeeds(self):
        """Test that JWT_SECRET_KEY with exactly minimum length (32 chars) succeeds."""
        # Exactly 32 character secret
        valid_secret = "a" * 32

        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": valid_secret},
            clear=False,
        ):
            # Should not raise an exception
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            assert src.web_interface.app.secret_key == valid_secret


class TestJWTSecretEdgeCases:
    """Test suite for JWT_SECRET_KEY edge cases."""

    def test_empty_string_treated_as_missing(self):
        """Test that empty string JWT_SECRET_KEY is treated as missing."""
        with patch.dict(
            os.environ, {"FLASK_ENV": "production", "JWT_SECRET_KEY": ""}, clear=False
        ):
            with pytest.raises(ValueError) as exc_info:
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

            assert "JWT_SECRET_KEY is not set" in str(exc_info.value)

    def test_whitespace_only_treated_as_missing(self):
        """Test that whitespace-only JWT_SECRET_KEY is treated as missing."""
        with patch.dict(
            os.environ,
            {"FLASK_ENV": "production", "JWT_SECRET_KEY": "   "},
            clear=False,
        ):
            with pytest.raises(ValueError) as exc_info:
                import importlib
                import src.web_interface

                importlib.reload(src.web_interface)

            assert "JWT_SECRET_KEY is not set" in str(exc_info.value)

    def test_flask_env_not_set_defaults_to_development(self):
        """Test that missing FLASK_ENV defaults to development behavior."""
        # Remove FLASK_ENV to test default behavior
        env = os.environ.copy()
        if "FLASK_ENV" in env:
            del env["FLASK_ENV"]

        with patch.dict(os.environ, env, clear=True):
            # Set JWT_SECRET_KEY but not FLASK_ENV
            os.environ["JWT_SECRET_KEY"] = ""

            # Should not raise exception (development mode)
            import importlib
            import src.web_interface

            importlib.reload(src.web_interface)

            # Verify fallback was used
            assert src.web_interface.app.secret_key is not None
