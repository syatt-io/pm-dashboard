"""Health check and diagnostic endpoints."""

from flask import Blueprint, jsonify
from datetime import datetime
import logging
import os
import base64
import httpx
import traceback

from config.settings import settings

logger = logging.getLogger(__name__)

# Create blueprint
health_bp = Blueprint('health', __name__, url_prefix='/api')


@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for DigitalOcean App Platform."""
    try:
        # Basic health check - can add database check if needed
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@health_bp.route('/health/jira', methods=['GET'])
def jira_health_check():
    """Diagnostic endpoint for Jira connection."""
    try:
        diagnostics = {
            'jira_url': settings.jira.url if hasattr(settings, 'jira') else 'NOT_LOADED',
            'jira_username': settings.jira.username if hasattr(settings, 'jira') else 'NOT_LOADED',
            'jira_token_set': bool(settings.jira.api_token) if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') else False,
            'jira_token_length': len(settings.jira.api_token) if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') and settings.jira.api_token else 0,
            'jira_token_prefix': settings.jira.api_token[:10] + '...' if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') and settings.jira.api_token else None,
            'env_jira_url': os.getenv('JIRA_URL'),
            'env_jira_username': os.getenv('JIRA_USERNAME'),
            'env_jira_token_set': bool(os.getenv('JIRA_API_TOKEN')),
            'env_jira_token_length': len(os.getenv('JIRA_API_TOKEN', '')),
            'env_jira_token_prefix': os.getenv('JIRA_API_TOKEN', '')[:10] + '...' if os.getenv('JIRA_API_TOKEN') else None,
        }

        # Test actual Jira API call synchronously
        try:
            auth_string = base64.b64encode(f"{settings.jira.username}:{settings.jira.api_token}".encode()).decode()

            # Use httpx synchronously for testing
            client = httpx.Client(timeout=30.0)
            response = client.get(
                f"{settings.jira.url}/rest/api/3/project",
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Accept": "application/json"
                }
            )

            response_data = response.json() if response.status_code == 200 else None
            diagnostics['api_test'] = {
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'project_count': len(response_data) if response_data else 0,
                'sample_response': response_data[:2] if response_data and len(response_data) > 0 else response_data,
                'error': response.text if response.status_code != 200 else None
            }

            client.close()

        except Exception as api_error:
            diagnostics['api_test'] = {
                'success': False,
                'error': str(api_error),
                'traceback': traceback.format_exc()
            }

        return jsonify(diagnostics)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500