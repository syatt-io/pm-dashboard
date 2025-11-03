"""Authentication API routes."""
from flask import Blueprint, request, jsonify, make_response, redirect, session
from src.services.auth import AuthService, auth_required, admin_required
from src.models.user import UserRole
from sqlalchemy.orm import Session
import logging
import os
import secrets
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

def create_auth_blueprint(db_session_factory, limiter=None):
    """Create authentication blueprint with database session factory and rate limiter."""
    auth_bp = Blueprint('auth', __name__)
    auth_service = AuthService(db_session_factory)

    # Helper to conditionally apply rate limiting
    def rate_limit(limit_string):
        def decorator(f):
            if limiter:
                return limiter.limit(limit_string)(f)
            return f
        return decorator

    # ✅ FIXED: Apply rate limiting to authentication endpoints
    @auth_bp.route('/api/auth/google', methods=['POST'])
    @rate_limit("10 per minute")  # Max 10 login attempts per minute
    def google_login():
        """Handle Google OAuth login."""
        try:
            logger.info("=== Google login request received ===")
            data = request.get_json()
            logger.info(f"Request data: {data}")
            token = data.get('credential')
            remember_me = data.get('rememberMe', False)
            logger.info(f"Token present: {bool(token)}, Remember me: {remember_me}")

            if not token:
                logger.error("No Google token provided")
                return jsonify({'error': 'No Google token provided'}), 400

            # Verify Google token
            user_info = auth_service.verify_google_token(token)

            # Create or update user
            user = auth_service.create_or_update_user(user_info)

            # Check if user has access
            if not user.can_access():
                logger.info(f"User {user.email} authenticated but pending admin approval (role: {user.role.value if user.role else 'unknown'})")
                return jsonify({
                    'message': 'Account Created - Pending Approval',
                    'error': 'Your account has been created successfully! An administrator needs to approve your access before you can use the app. Please contact an admin or wait for approval.',
                    'status': 'pending_approval',
                    'user_email': user.email
                }), 403

            # Generate JWT token
            jwt_token = auth_service.generate_jwt_token(user, remember_me)

            # Create response
            response_data = {
                'message': 'Login successful',
                'token': jwt_token,
                'user': user.to_dict()
            }
            logger.info(f"Sending successful response: {response_data}")
            response = make_response(jsonify(response_data))

            # Set secure cookie
            cookie_max_age = 604800 if remember_me else 86400  # 7 days or 1 day
            is_production = os.getenv('FLASK_ENV') == 'production'
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=is_production,  # Secure cookies in production only
                samesite='Strict' if is_production else 'Lax',  # Strict in production
                max_age=cookie_max_age
            )
            logger.info("=== Login successful, sending response ===")
            return response

        except ValueError as e:
            logger.error(f"Login failed with ValueError: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Login failed with unexpected error: {e}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Login failed: {str(e)}'}), 500

    @auth_bp.route('/api/auth/user', methods=['GET'])
    @auth_required
    def get_current_user(user):
        """Get current user information."""
        try:
            user = request.current_user
            return jsonify({'user': user.to_dict()})
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            return jsonify({'error': 'Failed to get user information'}), 500

    @auth_bp.route('/api/auth/logout', methods=['POST'])
    def logout():
        """Handle logout."""
        response = make_response(jsonify({'message': 'Logged out successfully'}))
        response.set_cookie('auth_token', '', expires=0, httponly=True, secure=True, samesite='Strict')
        return response

    @auth_bp.route('/api/auth/refresh', methods=['POST'])
    @rate_limit("30 per minute")  # ✅ SECURITY: Prevent token refresh abuse
    def refresh_token():
        """Refresh JWT token."""
        try:
            logger.info("Token refresh request received")
            # Get token from header or cookie
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header:
                try:
                    parts = auth_header.split(' ')
                    if len(parts) == 2 and parts[0] == 'Bearer':
                        token = parts[1]
                    else:
                        logger.warning(f"Invalid authorization header format: {auth_header}")
                except Exception as e:
                    logger.warning(f"Error parsing authorization header: {e}")

            if not token:
                token = request.cookies.get('auth_token')

            logger.info(f"Token found: {bool(token)} (source: {'header' if auth_header else 'cookie'})")

            if not token:
                logger.warning("No token provided for refresh")
                return jsonify({'error': 'No token provided'}), 401

            # Get user from token (even if expired)
            try:
                user = auth_service.get_current_user(token)
            except ValueError as e:
                # Try to decode expired token to get user info
                import jwt as jwt_lib
                try:
                    payload = jwt_lib.decode(token, auth_service.jwt_secret, algorithms=['HS256'], options={"verify_exp": False})
                    from src.models.user import User
                    db_session = db_session_factory()
                    try:
                        user = db_session.query(User).filter_by(id=payload['user_id']).first()
                        if not user or not user.can_access():
                            raise ValueError("User not found or access denied")
                    finally:
                        db_session.close()
                except Exception:
                    return jsonify({'error': 'Invalid token'}), 401

            remember_me = request.get_json().get('rememberMe', False) if request.get_json() else False

            # Generate new token
            jwt_token = auth_service.generate_jwt_token(user, remember_me)

            response = make_response(jsonify({
                'message': 'Token refreshed',
                'token': jwt_token
            }))

            # Update cookie
            cookie_max_age = 604800 if remember_me else 86400
            is_production = os.getenv('FLASK_ENV') == 'production'
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=is_production,  # Secure cookies in production only
                samesite='Strict' if is_production else 'Lax',  # Strict in production
                max_age=cookie_max_age
            )

            return response

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return jsonify({'error': 'Token refresh failed'}), 500

    @auth_bp.route('/api/auth/users', methods=['GET'])
    @rate_limit("30 per minute")  # ✅ SECURITY: Prevent admin endpoint abuse
    @admin_required
    def get_all_users(current_user):
        """Get all users (admin only)."""
        db_session = db_session_factory()
        try:
            from src.models.user import User
            users = db_session.query(User).all()
            return jsonify({
                'users': [user.to_dict() for user in users]
            })
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return jsonify({'error': 'Failed to get users'}), 500
        finally:
            db_session.close()

    @auth_bp.route('/api/auth/users/<int:user_id>/role', methods=['PUT'])
    @rate_limit("30 per minute")  # ✅ SECURITY: Prevent admin endpoint abuse
    @admin_required
    def update_user_role(current_user, user_id):
        """Update user role (admin only)."""
        db_session = db_session_factory()
        try:
            from src.models.user import User
            data = request.get_json()
            new_role = data.get('role')

            if not new_role:
                return jsonify({'error': 'Role is required'}), 400

            # Validate role
            try:
                role = UserRole[new_role.upper()]
            except KeyError:
                return jsonify({'error': 'Invalid role'}), 400

            user = db_session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Prevent self-demotion for admin
            if user.id == current_user.id and role != UserRole.ADMIN:
                return jsonify({'error': 'Cannot change your own admin role'}), 400

            user.role = role
            db_session.commit()

            return jsonify({
                'message': 'User role updated',
                'user': user.to_dict()
            })

        except Exception as e:
            logger.error(f"Failed to update user role: {e}")
            db_session.rollback()
            return jsonify({'error': 'Failed to update user role'}), 500
        finally:
            db_session.close()

    @auth_bp.route('/api/auth/users/<int:user_id>/status', methods=['PUT'])
    @rate_limit("30 per minute")  # ✅ SECURITY: Prevent admin endpoint abuse
    @admin_required
    def update_user_status(current_user, user_id):
        """Update user active status (admin only)."""
        db_session = db_session_factory()
        try:
            from src.models.user import User
            data = request.get_json()
            is_active = data.get('is_active')

            if is_active is None:
                return jsonify({'error': 'is_active is required'}), 400

            user = db_session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Prevent self-deactivation
            if user.id == current_user.id and not is_active:
                return jsonify({'error': 'Cannot deactivate your own account'}), 400

            user.is_active = is_active
            db_session.commit()

            return jsonify({
                'message': f"User {'activated' if is_active else 'deactivated'}",
                'user': user.to_dict()
            })

        except Exception as e:
            logger.error(f"Failed to update user status: {e}")
            db_session.rollback()
            return jsonify({'error': 'Failed to update user status'}), 500
        finally:
            db_session.close()

    @auth_bp.route('/api/auth/google/workspace/authorize', methods=['GET'])
    @auth_required
    def google_workspace_authorize(user):
        """Initiate Google Workspace OAuth flow for document access."""
        try:
            # Get OAuth credentials from environment
            client_id = os.getenv('GOOGLE_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            redirect_uri = os.getenv('GOOGLE_WORKSPACE_REDIRECT_URI')

            if not all([client_id, client_secret, redirect_uri]):
                return jsonify({
                    'error': 'Google Workspace OAuth is not configured. Please contact your administrator.'
                }), 500

            # Define scopes for Google Workspace access
            # Include OpenID and other scopes that Google automatically adds
            scopes = [
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/documents.readonly',
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/analytics.readonly'  # May be auto-added by Google
            ]

            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=scopes,
                redirect_uri=redirect_uri
            )

            # Generate state parameter for security
            state = secrets.token_urlsafe(32)
            session[f'oauth_state_{user.id}'] = state
            session[f'oauth_user_id'] = user.id  # Store user ID for callback

            # Generate authorization URL
            authorization_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=state,
                prompt='consent'  # Force consent to get refresh token
            )

            logger.info(f"Google Workspace OAuth initiated for user {user.id}")
            return jsonify({
                'authorization_url': authorization_url
            })

        except Exception as e:
            logger.error(f"Failed to initiate Google Workspace OAuth: {e}")
            return jsonify({'error': 'Failed to start authorization'}), 500

    @auth_bp.route('/api/auth/google/workspace/callback', methods=['GET'])
    @rate_limit("10 per minute")  # ✅ SECURITY: Prevent OAuth callback flooding
    def google_workspace_callback():
        """Handle Google Workspace OAuth callback."""
        try:
            # Get OAuth credentials from environment
            client_id = os.getenv('GOOGLE_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            redirect_uri = os.getenv('GOOGLE_WORKSPACE_REDIRECT_URI')

            if not all([client_id, client_secret, redirect_uri]):
                return jsonify({'error': 'OAuth not configured'}), 500

            # Get authorization code and state from callback
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')

            if error:
                logger.warning(f"OAuth callback error: {error}")
                # Redirect to settings with error
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=oauth_denied")

            if not code or not state:
                return jsonify({'error': 'Invalid callback parameters'}), 400

            # Get user ID from session (stored during authorize)
            user_id = session.get('oauth_user_id')
            if not user_id:
                logger.error("No user_id in session during OAuth callback")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=oauth_failed")

            # Verify state parameter
            expected_state = session.get(f'oauth_state_{user_id}')
            if not expected_state or expected_state != state:
                logger.warning(f"OAuth state mismatch for user {user_id}")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=oauth_failed")

            # Clear state and user_id from session
            session.pop(f'oauth_state_{user_id}', None)
            session.pop('oauth_user_id', None)

            # Define scopes (must match the authorize endpoint)
            # Include OpenID and other scopes that Google automatically adds
            scopes = [
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/documents.readonly',
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/analytics.readonly'  # May be auto-added by Google
            ]

            # Exchange code for tokens
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=scopes,
                redirect_uri=redirect_uri
            )

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Store tokens in user's database record
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None
            }

            # Update user with OAuth token
            db_session = db_session_factory()
            try:
                from src.models.user import User
                user = db_session.query(User).filter_by(id=user_id).first()
                if not user:
                    logger.error(f"User {user_id} not found during OAuth callback")
                    raise ValueError("User not found")

                user.set_google_oauth_token(token_data)
                db_session.commit()
                logger.info(f"Google Workspace OAuth completed for user {user_id}")
            finally:
                db_session.close()

            # Redirect to settings page with success message
            frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
            return redirect(f"{frontend_url}/settings?success=google_workspace_connected")

        except Exception as e:
            logger.error(f"Failed to complete Google Workspace OAuth: {e}")
            frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
            return redirect(f"{frontend_url}/settings?error=oauth_failed")

    @auth_bp.route('/api/auth/slack/authorize', methods=['GET'])
    @auth_required
    def slack_authorize(user):
        """Initiate Slack OAuth flow for search access."""
        try:
            # Get Slack OAuth credentials from environment
            client_id = os.getenv('SLACK_CLIENT_ID')
            redirect_uri = os.getenv('SLACK_REDIRECT_URI')

            if not all([client_id, redirect_uri]):
                return jsonify({
                    'error': 'Slack OAuth is not configured. Please contact your administrator.'
                }), 500

            # Define scopes for Slack search
            scopes = ['search:read']

            # Generate state parameter for security
            state = secrets.token_urlsafe(32)
            session[f'slack_oauth_state_{user.id}'] = state
            session[f'slack_oauth_user_id'] = user.id  # Store user ID for callback

            # Generate authorization URL
            authorization_url = (
                f"https://slack.com/oauth/v2/authorize"
                f"?client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state}"
                f"&user_scope={','.join(scopes)}"  # User-level token only
            )

            logger.info(f"Slack OAuth initiated for user {user.id}")
            return jsonify({
                'authorization_url': authorization_url
            })

        except Exception as e:
            logger.error(f"Failed to initiate Slack OAuth: {e}")
            return jsonify({'error': 'Failed to start authorization'}), 500

    @auth_bp.route('/api/auth/slack/callback', methods=['GET'])
    @rate_limit("10 per minute")  # ✅ SECURITY: Prevent OAuth callback flooding
    def slack_callback():
        """Handle Slack OAuth callback."""
        try:
            import requests

            # Get Slack OAuth credentials from environment
            client_id = os.getenv('SLACK_CLIENT_ID')
            client_secret = os.getenv('SLACK_CLIENT_SECRET')
            redirect_uri = os.getenv('SLACK_REDIRECT_URI')

            if not all([client_id, client_secret, redirect_uri]):
                return jsonify({'error': 'OAuth not configured'}), 500

            # Get authorization code and state from callback
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')

            if error:
                logger.warning(f"Slack OAuth callback error: {error}")
                # Redirect to settings with error
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=slack_oauth_denied")

            if not code or not state:
                return jsonify({'error': 'Invalid callback parameters'}), 400

            # Get user ID from session (stored during authorize)
            user_id = session.get('slack_oauth_user_id')
            if not user_id:
                logger.error("No user_id in session during Slack OAuth callback")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=slack_oauth_failed")

            # Verify state parameter
            expected_state = session.get(f'slack_oauth_state_{user_id}')
            if not expected_state or expected_state != state:
                logger.warning(f"Slack OAuth state mismatch for user {user_id}")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=slack_oauth_failed")

            # Clear state and user_id from session
            session.pop(f'slack_oauth_state_{user_id}', None)
            session.pop('slack_oauth_user_id', None)

            # Exchange code for access token
            token_response = requests.post(
                'https://slack.com/api/oauth.v2.access',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': code,
                    'redirect_uri': redirect_uri
                }
            )

            token_data = token_response.json()

            if not token_data.get('ok'):
                logger.error(f"Slack OAuth token exchange failed: {token_data.get('error')}")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=slack_oauth_failed")

            # Extract user token (not team/bot token)
            authed_user = token_data.get('authed_user', {})
            access_token = authed_user.get('access_token')

            if not access_token:
                logger.error("No user access token in Slack OAuth response")
                frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
                return redirect(f"{frontend_url}/settings?error=slack_oauth_failed")

            # Store tokens in user's database record
            token_info = {
                'access_token': access_token,
                'token_type': authed_user.get('token_type', 'user'),
                'scope': authed_user.get('scope', ''),
                'team_id': token_data.get('team', {}).get('id'),
                'team_name': token_data.get('team', {}).get('name'),
                'user_id': authed_user.get('id')
            }

            # Update user with OAuth token and Slack user ID
            db_session = db_session_factory()
            try:
                from src.models.user import User
                user = db_session.query(User).filter_by(id=user_id).first()
                if not user:
                    logger.error(f"User {user_id} not found during Slack OAuth callback")
                    raise ValueError("User not found")

                # Store the Slack user ID for command mapping
                slack_user_id = authed_user.get('id')
                if slack_user_id:
                    user.slack_user_id = slack_user_id
                    logger.info(f"Stored Slack user ID {slack_user_id} for user {user_id}")

                user.set_slack_user_token(token_info)
                db_session.commit()
                logger.info(f"Slack OAuth completed for user {user_id}")
            finally:
                db_session.close()

            # Redirect to settings page with success message
            frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
            return redirect(f"{frontend_url}/settings?success=slack_connected")

        except Exception as e:
            logger.error(f"Failed to complete Slack OAuth: {e}")
            frontend_url = os.getenv('WEB_BASE_URL', 'http://localhost:3000')
            return redirect(f"{frontend_url}/settings?error=slack_oauth_failed")

    return auth_bp