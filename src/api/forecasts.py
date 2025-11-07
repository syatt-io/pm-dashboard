"""
API endpoints for epic forecasting.
"""

from flask import Blueprint, request, jsonify
from src.services.forecasting_service import ForecastingService
from src.models import EpicForecast
from src.utils.database import get_session
import logging

logger = logging.getLogger(__name__)

forecasts_bp = Blueprint('forecasts', __name__, url_prefix='/api/forecasts')
forecasting_service = ForecastingService()


@forecasts_bp.route('/calculate', methods=['POST'])
def calculate_forecast():
    """
    Calculate a forecast based on project characteristics.

    Request body:
    {
        "be_integrations": bool,
        "custom_theme": bool,
        "custom_designs": bool,
        "ux_research": bool,
        "teams_selected": ["BE Devs", "FE Devs", ...],
        "estimated_months": int
    }
    """
    try:
        data = request.json

        # Validate required fields
        required_fields = ['be_integrations', 'custom_theme', 'custom_designs', 'ux_research', 'teams_selected', 'estimated_months']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Calculate forecast
        forecast_result = forecasting_service.calculate_forecast(
            be_integrations=data['be_integrations'],
            custom_theme=data['custom_theme'],
            custom_designs=data['custom_designs'],
            ux_research=data['ux_research'],
            teams_selected=data['teams_selected'],
            estimated_months=data['estimated_months']
        )

        return jsonify(forecast_result), 200

    except Exception as e:
        logger.error(f"Error calculating forecast: {e}")
        return jsonify({'error': str(e)}), 500


@forecasts_bp.route('', methods=['GET'])
def list_forecasts():
    """List all saved forecasts."""
    try:
        session = get_session()
        forecasts = session.query(EpicForecast).order_by(EpicForecast.created_at.desc()).all()

        return jsonify({
            'forecasts': [
                {
                    'id': f.id,
                    'project_key': f.project_key,
                    'epic_name': f.epic_name,
                    'total_hours': f.total_hours,
                    'estimated_months': f.estimated_months,
                    'teams_selected': f.teams_selected,
                    'characteristics': {
                        'be_integrations': f.be_integrations,
                        'custom_theme': f.custom_theme,
                        'custom_designs': f.custom_designs,
                        'ux_research': f.ux_research
                    },
                    'created_at': f.created_at.isoformat() if f.created_at else None
                }
                for f in forecasts
            ]
        }), 200

    except Exception as e:
        logger.error(f"Error listing forecasts: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route('', methods=['POST'])
def save_forecast():
    """
    Save a new forecast.

    Request body:
    {
        "project_key": str,
        "epic_name": str,
        "epic_description": str (optional),
        "be_integrations": bool,
        "custom_theme": bool,
        "custom_designs": bool,
        "ux_research": bool,
        "teams_selected": [...],
        "estimated_months": int,
        "forecast_data": {...},
        "total_hours": float
    }
    """
    try:
        data = request.json
        session = get_session()

        forecast = EpicForecast(
            project_key=data['project_key'],
            epic_name=data['epic_name'],
            epic_description=data.get('epic_description'),
            be_integrations=data['be_integrations'],
            custom_theme=data['custom_theme'],
            custom_designs=data['custom_designs'],
            ux_research=data['ux_research'],
            teams_selected=data['teams_selected'],
            estimated_months=data['estimated_months'],
            forecast_data=data['forecast_data'],
            total_hours=data['total_hours'],
            created_by=data.get('created_by')
        )

        session.add(forecast)
        session.commit()

        return jsonify({
            'id': forecast.id,
            'message': 'Forecast saved successfully'
        }), 201

    except Exception as e:
        logger.error(f"Error saving forecast: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route('/<int:forecast_id>', methods=['GET'])
def get_forecast(forecast_id):
    """Get a specific forecast by ID."""
    try:
        session = get_session()
        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({'error': 'Forecast not found'}), 404

        return jsonify({
            'id': forecast.id,
            'project_key': forecast.project_key,
            'epic_name': forecast.epic_name,
            'epic_description': forecast.epic_description,
            'characteristics': {
                'be_integrations': forecast.be_integrations,
                'custom_theme': forecast.custom_theme,
                'custom_designs': forecast.custom_designs,
                'ux_research': forecast.ux_research
            },
            'teams_selected': forecast.teams_selected,
            'estimated_months': forecast.estimated_months,
            'forecast_data': forecast.forecast_data,
            'total_hours': forecast.total_hours,
            'created_at': forecast.created_at.isoformat() if forecast.created_at else None,
            'updated_at': forecast.updated_at.isoformat() if forecast.updated_at else None
        }), 200

    except Exception as e:
        logger.error(f"Error getting forecast: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route('/<int:forecast_id>', methods=['PUT'])
def update_forecast(forecast_id):
    """Update an existing forecast."""
    try:
        data = request.json
        session = get_session()

        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({'error': 'Forecast not found'}), 404

        # Update fields
        if 'epic_name' in data:
            forecast.epic_name = data['epic_name']
        if 'epic_description' in data:
            forecast.epic_description = data['epic_description']
        if 'project_key' in data:
            forecast.project_key = data['project_key']

        session.commit()

        return jsonify({'message': 'Forecast updated successfully'}), 200

    except Exception as e:
        logger.error(f"Error updating forecast: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route('/<int:forecast_id>', methods=['DELETE'])
def delete_forecast(forecast_id):
    """Delete a forecast."""
    try:
        session = get_session()
        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({'error': 'Forecast not found'}), 404

        session.delete(forecast)
        session.commit()

        return jsonify({'message': 'Forecast deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting forecast: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route('/baselines', methods=['GET'])
def get_baselines():
    """Get baseline hours for all teams based on integration requirement."""
    try:
        be_integrations = request.args.get('be_integrations', 'false').lower() == 'true'

        baselines = forecasting_service.get_baseline_info(be_integrations)
        baseline_set = 'with_integration' if be_integrations else 'no_integration'

        return jsonify({
            'baseline_set': baseline_set,
            'baselines': baselines
        }), 200

    except Exception as e:
        logger.error(f"Error getting baselines: {e}")
        return jsonify({'error': str(e)}), 500


@forecasts_bp.route('/lifecycle/<team>', methods=['GET'])
def get_lifecycle(team):
    """Get lifecycle percentages for a specific team."""
    try:
        lifecycle = forecasting_service.get_lifecycle_info(team)

        return jsonify({
            'team': team,
            'lifecycle': lifecycle
        }), 200

    except Exception as e:
        logger.error(f"Error getting lifecycle info: {e}")
        return jsonify({'error': str(e)}), 500


@forecasts_bp.route('/calculate-from-total', methods=['POST'])
def calculate_from_total_hours():
    """
    Calculate team distribution from total hours budget.

    Request body:
    {
        "total_hours": float,
        "be_integrations": bool,
        "custom_theme": bool,
        "custom_designs": bool,
        "ux_research": bool,
        "teams_selected": [...],
        "estimated_months": int
    }
    """
    try:
        data = request.json

        # Validate required fields
        required_fields = ['total_hours', 'be_integrations', 'custom_theme', 'custom_designs', 'ux_research', 'teams_selected', 'estimated_months']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Calculate distribution
        result = forecasting_service.calculate_from_total_hours(
            total_hours=data['total_hours'],
            be_integrations=data['be_integrations'],
            custom_theme=data['custom_theme'],
            custom_designs=data['custom_designs'],
            ux_research=data['ux_research'],
            teams_selected=data['teams_selected'],
            estimated_months=data['estimated_months']
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error calculating team distribution: {e}")
        return jsonify({'error': str(e)}), 500
