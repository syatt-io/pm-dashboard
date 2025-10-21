"""Admin system settings routes."""
from flask import Blueprint, jsonify, request
import logging

from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models.system_settings import SystemSettings

logger = logging.getLogger(__name__)

admin_settings_bp = Blueprint('admin_settings', __name__, url_prefix='/api/admin')


def admin_required(f):
    """Decorator to require admin role."""
    def wrapper(user, *args, **kwargs):
        if not user.is_admin():
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        return f(user, *args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@admin_settings_bp.route("/system-settings", methods=["GET"])
@auth_required
@admin_required
def get_system_settings(user):
    """Get current system settings (admin only)."""
    try:
        with session_scope() as db_session:
            settings = db_session.query(SystemSettings).first()

            if not settings:
                # Return defaults if no settings exist yet
                return jsonify({
                    'success': True,
                    'data': {
                        'ai_provider': 'openai',
                        'ai_model': None,
                        'ai_temperature': 0.3,
                        'ai_max_tokens': 2000,
                        'has_openai_key': False,
                        'has_anthropic_key': False,
                        'has_google_key': False,
                        'updated_at': None,
                        'updated_by_user_id': None
                    }
                })

            return jsonify({
                'success': True,
                'data': settings.to_dict()
            })

    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_settings_bp.route("/system-settings/ai", methods=["PUT"])
@auth_required
@admin_required
def update_ai_settings(user):
    """Update AI configuration settings (admin only)."""
    try:
        data = request.get_json()

        provider = data.get('ai_provider')
        model = data.get('ai_model')
        temperature = data.get('ai_temperature')
        max_tokens = data.get('ai_max_tokens')

        # Validate provider
        if provider and provider not in ['openai', 'anthropic', 'google']:
            return jsonify({
                'success': False,
                'error': 'Invalid AI provider. Must be: openai, anthropic, or google'
            }), 400

        # Validate temperature
        if temperature is not None and (temperature < 0 or temperature > 2):
            return jsonify({
                'success': False,
                'error': 'Temperature must be between 0 and 2'
            }), 400

        # Validate max_tokens
        if max_tokens is not None and max_tokens < 1:
            return jsonify({
                'success': False,
                'error': 'Max tokens must be at least 1'
            }), 400

        with session_scope() as db_session:
            settings = db_session.query(SystemSettings).first()

            if not settings:
                # Create new settings
                settings = SystemSettings()
                db_session.add(settings)

            # Update fields
            if provider:
                settings.ai_provider = provider
            if model is not None:  # Allow empty string to clear
                settings.ai_model = model if model else None
            if temperature is not None:
                settings.ai_temperature = temperature
            if max_tokens is not None:
                settings.ai_max_tokens = max_tokens

            settings.updated_by_user_id = user.id

            db_session.flush()

            return jsonify({
                'success': True,
                'message': 'AI settings updated successfully',
                'data': settings.to_dict()
            })

    except Exception as e:
        logger.error(f"Error updating AI settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_settings_bp.route("/system-settings/ai/api-key", methods=["POST"])
@auth_required
@admin_required
def save_ai_api_key(user):
    """Save or update AI provider API key (admin only)."""
    try:
        data = request.get_json()
        provider = data.get('provider')
        api_key = data.get('api_key', '').strip()

        if not provider:
            return jsonify({
                'success': False,
                'error': 'Provider is required'
            }), 400

        if provider not in ['openai', 'anthropic', 'google']:
            return jsonify({
                'success': False,
                'error': 'Invalid provider. Must be: openai, anthropic, or google'
            }), 400

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400

        with session_scope() as db_session:
            settings = db_session.query(SystemSettings).first()

            if not settings:
                # Create new settings
                settings = SystemSettings()
                db_session.add(settings)

            # Set the API key
            settings.set_api_key(provider, api_key)
            settings.updated_by_user_id = user.id

            db_session.flush()

            logger.info(f"Admin {user.email} updated {provider} API key")

            return jsonify({
                'success': True,
                'message': f'{provider.title()} API key saved successfully'
            })

    except Exception as e:
        logger.error(f"Error saving AI API key: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_settings_bp.route("/system-settings/ai/api-key/<provider>", methods=["DELETE"])
@auth_required
@admin_required
def delete_ai_api_key(user, provider):
    """Delete AI provider API key (admin only)."""
    try:
        if provider not in ['openai', 'anthropic', 'google']:
            return jsonify({
                'success': False,
                'error': 'Invalid provider. Must be: openai, anthropic, or google'
            }), 400

        with session_scope() as db_session:
            settings = db_session.query(SystemSettings).first()

            if not settings:
                return jsonify({
                    'success': False,
                    'error': 'No settings found'
                }), 404

            settings.clear_api_key(provider)
            settings.updated_by_user_id = user.id

            db_session.flush()

            logger.info(f"Admin {user.email} deleted {provider} API key")

            return jsonify({
                'success': True,
                'message': f'{provider.title()} API key deleted successfully'
            })

    except Exception as e:
        logger.error(f"Error deleting AI API key: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_settings_bp.route("/system-settings/ai/models", methods=["GET"])
@auth_required
@admin_required
def get_available_models(user):
    """Get available models for each AI provider (admin only)."""
    # Fetch OpenAI models dynamically from API
    openai_models = _fetch_openai_models()

    # Curated lists for Anthropic and Google (with custom input option)
    return jsonify({
        'success': True,
        'data': {
            'openai': openai_models,
            'anthropic': [
                {'value': 'claude-3-5-sonnet-20241022', 'label': 'Claude 3.5 Sonnet (Latest)'},
                {'value': 'claude-3-5-haiku-20241022', 'label': 'Claude 3.5 Haiku (Fast)'},
                {'value': 'claude-3-opus-20240229', 'label': 'Claude 3 Opus'},
                {'value': '__custom__', 'label': '✏️ Custom Model ID...'},
            ],
            'google': [
                {'value': 'gemini-1.5-pro', 'label': 'Gemini 1.5 Pro (Latest)'},
                {'value': 'gemini-1.5-flash', 'label': 'Gemini 1.5 Flash (Fast)'},
                {'value': 'gemini-1.0-pro', 'label': 'Gemini 1.0 Pro'},
                {'value': '__custom__', 'label': '✏️ Custom Model ID...'},
            ]
        },
        'supports_custom_input': {
            'openai': False,  # Fetched from API
            'anthropic': True,
            'google': True
        }
    })


def _fetch_openai_models():
    """Fetch available models from OpenAI API."""
    try:
        import openai
        import os

        # Try to get API key from system settings or environment
        api_key = None
        try:
            with session_scope() as db_session:
                settings = db_session.query(SystemSettings).first()
                if settings:
                    api_key = settings.get_api_key('openai')
        except Exception:
            pass

        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')

        if not api_key:
            # Return fallback list if no API key
            logger.warning("No OpenAI API key available, returning fallback model list")
            return _get_fallback_openai_models()

        # Fetch models from OpenAI API
        client = openai.OpenAI(api_key=api_key)
        models_response = client.models.list()

        # Filter to only GPT models and sort by ID
        gpt_models = []
        for model in models_response.data:
            model_id = model.id
            # Filter for GPT models only (exclude embeddings, whisper, dall-e, etc.)
            if model_id.startswith('gpt-'):
                # Prioritize commonly used models
                if model_id in ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']:
                    priority = 0
                else:
                    priority = 1

                gpt_models.append({
                    'value': model_id,
                    'label': model_id.upper().replace('-', ' ').replace('GPT ', 'GPT-'),
                    'priority': priority
                })

        # Sort by priority and then by name
        gpt_models.sort(key=lambda x: (x['priority'], x['value']))

        # Remove priority from response
        for model in gpt_models:
            del model['priority']

        # If we got models, return them
        if gpt_models:
            return gpt_models

        # Otherwise fallback
        return _get_fallback_openai_models()

    except Exception as e:
        logger.error(f"Failed to fetch OpenAI models: {e}")
        return _get_fallback_openai_models()


def _get_fallback_openai_models():
    """Fallback OpenAI model list if API fetch fails."""
    return [
        {'value': 'gpt-4o', 'label': 'GPT-4o (Latest)'},
        {'value': 'gpt-4o-mini', 'label': 'GPT-4o Mini (Fast & Affordable)'},
        {'value': 'gpt-4-turbo', 'label': 'GPT-4 Turbo'},
        {'value': 'gpt-4', 'label': 'GPT-4'},
        {'value': 'gpt-3.5-turbo', 'label': 'GPT-3.5 Turbo'},
    ]
