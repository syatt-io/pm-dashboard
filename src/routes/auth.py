"""Authentication API routes."""
from flask import Blueprint, request, jsonify, make_response
from src.services.auth import AuthService, auth_required, admin_required
from src.models.user import UserRole
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

def create_auth_blueprint(db_session_factory):
    """Create authentication blueprint with database session factory."""
    auth_bp = Blueprint('auth', __name__)
    auth_service = AuthService(db_session_factory)

    @auth_bp.route('/api/auth/google', methods=['POST'])
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
                return jsonify({
                    'error': 'Access denied. Please contact an administrator for access.',
                    'status': 'no_access'
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
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=False,  # Changed for local development
                samesite='Lax',  # Changed for local development
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
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=False,  # Changed for local development
                samesite='Lax',  # Changed for local development
                max_age=cookie_max_age
            )

            return response

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return jsonify({'error': 'Token refresh failed'}), 500

    @auth_bp.route('/api/auth/users', methods=['GET'])
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

    return auth_bp