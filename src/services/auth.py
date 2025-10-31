"""Authentication and authorization service."""
import os
import jwt
from datetime import datetime, timedelta, timezone
from google.oauth2 import id_token
from google.auth.transport import requests
from functools import wraps
from flask import request, jsonify, current_app
from sqlalchemy.orm import Session
from src.models.user import User, UserRole
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication and authorization."""

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

        # Get required configuration from environment
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.allowed_domain = os.getenv('ALLOWED_EMAIL_DOMAIN', '@syatt.io')
        self.admin_email = os.getenv('ADMIN_EMAIL', 'mike.samimi@syatt.io')

        # JWT Configuration - FAIL FAST if not configured
        # ✅ FIXED: Always require JWT_SECRET_KEY - no fallback
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')

        if not self.jwt_secret:
            logger.warning(
                "JWT_SECRET_KEY is not set - generating random secret (NOT RECOMMENDED FOR PRODUCTION). "
                "Set JWT_SECRET_KEY env var with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
            import secrets
            self.jwt_secret = secrets.token_hex(32)

        self.jwt_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))

        # Validate configuration
        if not self.google_client_id:
            logger.warning("GOOGLE_CLIENT_ID is not set - Google OAuth will not work")

        if not self.allowed_domain.startswith('@'):
            logger.warning(f"ALLOWED_EMAIL_DOMAIN should start with '@', got: {self.allowed_domain}")
            self.allowed_domain = f"@{self.allowed_domain}"

        logger.info(f"AuthService initialized - Domain: {self.allowed_domain}, Admin: {self.admin_email}")

    def verify_google_token(self, token):
        """Verify Google OAuth token and return user info."""
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.google_client_id
            )

            # Check if email is from allowed domain
            email = idinfo.get('email', '')
            if not email.endswith(self.allowed_domain):
                raise ValueError(f"Email domain not allowed. Only {self.allowed_domain} emails are permitted.")

            return {
                'google_id': idinfo['sub'],
                'email': email,
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', '')
            }
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            raise ValueError(f"Invalid Google token: {str(e)}")

    def create_or_update_user(self, user_info):
        """Create or update user from Google info."""
        logger.info(f"Creating/updating user: {user_info.get('email', 'unknown')}")
        db_session = self.db_session_factory()
        logger.info("Database session created successfully")
        try:
            # First try to find by google_id
            logger.info(f"Querying for user with google_id: {user_info.get('google_id', 'unknown')}")
            try:
                user = db_session.query(User).filter_by(google_id=user_info['google_id']).first()
                logger.info(f"Query result: {user}")
            except Exception as query_error:
                logger.error(f"Database query failed: {query_error}", exc_info=True)
                raise

            # If not found by google_id, try to find by email (for existing users with placeholder google_id)
            if not user:
                user = db_session.query(User).filter_by(email=user_info['email']).first()

                # If found by email, update the google_id with the real one from Google
                if user:
                    logger.info(f"Updating existing user {user_info['email']} with real Google ID")
                    user.google_id = user_info['google_id']
                    user.name = user_info['name']  # Update name in case it changed

            if not user:
                # Truly new user - check if it's the admin
                role = UserRole.ADMIN if user_info['email'] == self.admin_email else UserRole.NO_ACCESS

                user = User(
                    email=user_info['email'],
                    name=user_info['name'],
                    google_id=user_info['google_id'],
                    role=role
                )
                db_session.add(user)
                logger.info(f"New user created: {user_info['email']} with role {role.value}")

            # Update last login
            user.last_login = datetime.now(timezone.utc)
            db_session.commit()

            # Make sure we have the role value before detaching
            user_role_value = user.role.value if user.role else None

            # Detach from session
            db_session.expunge(user)

            # Restore the role value as a simple attribute
            user._role_value = user_role_value
            return user
        finally:
            db_session.close()

    def generate_jwt_token(self, user, remember_me=False):
        """Generate JWT token for authenticated user."""
        # Extend expiry if remember_me is True
        expiry_hours = self.jwt_expiry_hours * 7 if remember_me else self.jwt_expiry_hours

        # Get role value safely - use cached value if available
        role_value = getattr(user, '_role_value', None)
        if role_value is None:
            # Fallback to accessing the role relationship
            role_value = user.role.value if user.role else 'NO_ACCESS'

        payload = {
            'user_id': user.id,
            'email': user.email,
            'role': role_value,
            'exp': datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
            'iat': datetime.now(timezone.utc)
        }

        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')

    def verify_jwt_token(self, token):
        """Verify JWT token and return user info."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def get_current_user(self, token):
        """Get current user from JWT token."""
        db_session = self.db_session_factory()
        try:
            payload = self.verify_jwt_token(token)
            user = db_session.query(User).filter_by(id=payload['user_id']).first()

            if not user:
                raise ValueError("User not found")

            if not user.can_access():
                raise ValueError("User access denied")

            # Make sure we have the role value before detaching
            user_role_value = user.role.value if user.role else None

            # Detach user from session so it can be used across requests
            db_session.expunge(user)

            # Restore the role value as a simple attribute
            user._role_value = user_role_value
            return user
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            raise
        finally:
            db_session.close()


def auth_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None

        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401

        # Get token from cookie as fallback
        if not token:
            token = request.cookies.get('auth_token')

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        try:
            # Get auth service from app context
            auth_service = current_app.auth_service
            user = auth_service.get_current_user(token)

            # Add user to request context
            request.current_user = user

            return f(user, *args, **kwargs)
        except Exception as e:
            return jsonify({'error': str(e)}), 401

    return decorated_function


def role_required(role):
    """Decorator to require specific role for routes."""
    def decorator(f):
        @wraps(f)
        @auth_required
        def decorated_function(*args, **kwargs):
            user = request.current_user

            if isinstance(role, str):
                required_role = UserRole[role.upper()]
            else:
                required_role = role

            # Admin can access everything
            if user.role == UserRole.ADMIN:
                return f(*args, **kwargs)

            # Check if user has required role
            if user.role != required_role:
                return jsonify({'error': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to require admin role for routes."""
    return role_required(UserRole.ADMIN)(f)