"""
API endpoints for epic forecasting.
"""

from flask import Blueprint, request, jsonify, make_response
from src.services.forecasting_service import ForecastingService
from src.models import EpicForecast
from src.utils.database import get_session
import logging
import csv
import io

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
        "be_integrations": int (1-5 slider value),
        "custom_theme": int (1-5 slider value),
        "custom_designs": int (1-5 slider value),
        "ux_research": int (1-5 slider value),
        "extensive_customizations": int (1-5 slider value, optional, default: 1),
        "project_oversight": int (1-5 slider value, optional, default: 3),
        "teams_selected": [...],
        "estimated_months": int,
        "start_date": str (YYYY-MM-DD, optional)
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
            estimated_months=data['estimated_months'],
            extensive_customizations=data.get('extensive_customizations', 1),
            project_oversight=data.get('project_oversight', 3),
            start_date=data.get('start_date')
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error calculating team distribution: {e}")
        return jsonify({'error': str(e)}), 500


@forecasts_bp.route('/export-combined-forecast', methods=['POST'])
def export_combined_forecast():
    """
    Export combined project forecast (team distribution + epic schedule) as CSV.

    Request body:
    {
        "total_hours": float,
        "be_integrations": int (1-5),
        "custom_theme": int (1-5),
        "custom_designs": int (1-5),
        "ux_research": int (1-5),
        "extensive_customizations": int (1-5, optional),
        "project_oversight": int (1-5, optional),
        "teams_selected": [...],
        "estimated_months": int,
        "start_date": str (YYYY-MM-DD)
    }
    """
    try:
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        from src.api.analytics_schedule import generate_project_schedule

        data = request.json

        # Validate required fields
        required_fields = ['total_hours', 'be_integrations', 'custom_theme', 'custom_designs',
                          'ux_research', 'teams_selected', 'estimated_months', 'start_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Get team distribution data
        team_result = forecasting_service.calculate_from_total_hours(
            total_hours=data['total_hours'],
            be_integrations=data['be_integrations'],
            custom_theme=data['custom_theme'],
            custom_designs=data['custom_designs'],
            ux_research=data['ux_research'],
            teams_selected=data['teams_selected'],
            estimated_months=data['estimated_months'],
            extensive_customizations=data.get('extensive_customizations', 1),
            project_oversight=data.get('project_oversight', 3)
        )

        # Get epic schedule data
        epic_schedule = generate_project_schedule(
            total_hours=data['total_hours'],
            duration_months=data['estimated_months'],
            start_date=data['start_date']
        )

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Section 1: Project Summary
        writer.writerow(['PROJECT FORECAST SUMMARY'])
        writer.writerow([''])
        writer.writerow(['Total Hours', data['total_hours']])
        writer.writerow(['Duration (Months)', data['estimated_months']])
        writer.writerow(['Start Date', data['start_date']])
        writer.writerow([''])
        writer.writerow(['Project Characteristics'])
        writer.writerow(['Backend Integrations', data['be_integrations']])
        writer.writerow(['Custom Theme', data['custom_theme']])
        writer.writerow(['Custom Designs', data['custom_designs']])
        writer.writerow(['UX Research', data['ux_research']])
        writer.writerow(['Extensive Customizations', data.get('extensive_customizations', 1)])
        writer.writerow([''])
        writer.writerow([''])

        # Section 2: Team Distribution
        writer.writerow(['TEAM DISTRIBUTION'])
        writer.writerow([''])
        writer.writerow(['Team', 'Total Hours', 'Percentage'])
        for team_data in team_result['teams']:
            writer.writerow([
                team_data['team'],
                team_data['total_hours'],
                f"{team_data['percentage']}%"
            ])
        writer.writerow([''])
        writer.writerow([''])

        # Section 3: Team Monthly Breakdown
        writer.writerow(['TEAM MONTHLY BREAKDOWN'])
        writer.writerow([''])
        for team_data in team_result['teams']:
            writer.writerow([f"{team_data['team']} ({team_data['total_hours']}h total)"])
            writer.writerow(['Month', 'Phase', 'Hours'])
            for month_data in team_data['monthly_breakdown']:
                writer.writerow([
                    f"Month {month_data['month']}",
                    month_data['phase'],
                    month_data['hours']
                ])
            writer.writerow([''])
        writer.writerow([''])

        # Section 4: Epic Schedule Breakdown
        writer.writerow(['EPIC SCHEDULE BREAKDOWN'])
        writer.writerow([''])

        # Epic schedule header
        header_row = ['Epic', 'Temporal Pattern', 'Total Hours']
        start_date_obj = datetime.strptime(data['start_date'], '%Y-%m-%d')
        for i in range(data['estimated_months']):
            month_date = start_date_obj + relativedelta(months=i)
            header_row.append(month_date.strftime('%b %Y'))
        writer.writerow(header_row)

        # Epic schedule data
        for epic in epic_schedule.get('epics', []):
            row = [
                epic['name'],
                epic.get('temporal_pattern', 'Even'),
                epic['total_hours']
            ]
            for month_hours in epic['monthly_hours']:
                row.append(month_hours)
            writer.writerow(row)

        writer.writerow([''])
        writer.writerow(['Total Hours', epic_schedule.get('total_hours', data['total_hours'])])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=project_forecast_{data["start_date"]}.csv'

        return response

    except Exception as e:
        logger.error(f"Error exporting combined forecast: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
