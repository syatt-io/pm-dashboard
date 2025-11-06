"""Analytics API endpoints for epic hours insights and forecasting."""

from flask import Blueprint, jsonify, request
from src.models import EpicBaseline, EpicHours
from src.utils.database import get_session
from src.services.auth import admin_required
from sqlalchemy import func
from collections import defaultdict
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


def normalize_epic_name(epic_summary: str) -> str:
    """Normalize epic names for matching."""
    return epic_summary.strip().lower()


@analytics_bp.route('/baselines', methods=['GET'])
@admin_required
def get_baselines(user):
    """
    Get all epic baselines with statistics.

    Query params:
        - variance_level: Filter by variance level (low/medium/high)
        - min_projects: Minimum number of projects
    """
    try:
        session = get_session()
        query = session.query(EpicBaseline)

        # Apply filters
        variance_level = request.args.get('variance_level')
        if variance_level:
            query = query.filter(EpicBaseline.variance_level == variance_level)

        min_projects = request.args.get('min_projects', type=int)
        if min_projects:
            query = query.filter(EpicBaseline.project_count >= min_projects)

        # Order by project count (most common first)
        baselines = query.order_by(
            EpicBaseline.project_count.desc(),
            EpicBaseline.median_hours.desc()
        ).all()

        return jsonify({
            'success': True,
            'count': len(baselines),
            'baselines': [{
                'epic_category': b.epic_category,
                'median_hours': b.median_hours,
                'mean_hours': b.mean_hours,
                'p75_hours': b.p75_hours,
                'p90_hours': b.p90_hours,
                'min_hours': b.min_hours,
                'max_hours': b.max_hours,
                'project_count': b.project_count,
                'occurrence_count': b.occurrence_count,
                'coefficient_of_variation': b.coefficient_of_variation,
                'variance_level': b.variance_level,
                'recommended_estimate': b.get_recommended_estimate()
            } for b in baselines]
        })

    except Exception as e:
        logger.error(f"Error fetching baselines: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_bp.route('/forecast', methods=['POST'])
@admin_required
def forecast_project(user):
    """
    Forecast project hours based on epic list.

    Request body:
        {
            "epics": ["Header", "Footer", "Cart", "Search", ...]
        }
    """
    try:
        data = request.get_json()
        epic_list = data.get('epics', [])

        if not epic_list:
            return jsonify({'success': False, 'error': 'Epic list is required'}), 400

        session = get_session()

        # Load all baselines
        baselines = {}
        for baseline in session.query(EpicBaseline).all():
            baselines[baseline.epic_category] = baseline

        # Match epics and calculate estimates
        epic_estimates = []
        dev_hours = 0
        custom_epics = []
        high_risk_epics = []

        for epic in epic_list:
            normalized = normalize_epic_name(epic)
            baseline = baselines.get(normalized)

            if not baseline:
                # Try fuzzy match
                for key, b in baselines.items():
                    if normalized in key or key in normalized:
                        baseline = b
                        break

            if baseline:
                hours = baseline.get_recommended_estimate()
                epic_estimates.append({
                    'epic': epic,
                    'matched_category': baseline.epic_category,
                    'hours': round(hours, 1),
                    'variance_level': baseline.variance_level,
                    'confidence': 'high' if baseline.variance_level == 'low' else 'medium',
                    'range': f"{baseline.min_hours:.1f}-{baseline.max_hours:.1f}h"
                })
                dev_hours += hours

                if baseline.variance_level == 'high':
                    high_risk_epics.append(epic)
            else:
                # Custom epic
                epic_estimates.append({
                    'epic': epic,
                    'hours': None,
                    'variance_level': 'custom',
                    'confidence': 'low',
                    'note': 'No historical data - requires custom scoping'
                })
                custom_epics.append(epic)

        # Add PM overhead (25%)
        pm_hours = dev_hours * 0.25
        total_hours = dev_hours + pm_hours

        # Project size classification
        if total_hours < 900:
            project_size = 'small'
            months = 8
            burn_rate = 118.65
        elif total_hours < 1400:
            project_size = 'medium'
            months = 12
            burn_rate = 87.52
        else:
            project_size = 'large'
            months = 12
            burn_rate = 136.64

        # Confidence level
        if custom_epics or len(high_risk_epics) > len(epic_list) * 0.3:
            confidence = 'low'
            margin = 0.30
        elif high_risk_epics:
            confidence = 'medium'
            margin = 0.20
        else:
            confidence = 'high'
            margin = 0.10

        # Generate burn schedule
        schedule = []
        total_weight = 0
        weights = []

        for month in range(1, months + 1):
            if month <= months * 0.33:
                weight = 1.3
            elif month <= months * 0.67:
                weight = 1.0
            else:
                weight = 0.7
            weights.append(weight)
            total_weight += weight

        cumulative = 0
        for month, weight in enumerate(weights, 1):
            month_hours = (weight / total_weight) * total_hours
            cumulative += month_hours
            schedule.append({
                'month': month,
                'hours': round(month_hours, 1),
                'cumulative': round(cumulative, 1)
            })

        return jsonify({
            'success': True,
            'forecast': {
                'summary': {
                    'total_epics': len(epic_list),
                    'matched_epics': len(epic_list) - len(custom_epics),
                    'custom_epics': len(custom_epics),
                    'development_hours': round(dev_hours, 1),
                    'pm_overhead_hours': round(pm_hours, 1),
                    'total_hours': round(total_hours, 1),
                    'confidence': confidence,
                    'range_low': round(total_hours * (1 - margin), 1),
                    'range_high': round(total_hours * (1 + margin), 1)
                },
                'timeline': {
                    'project_size': project_size,
                    'estimated_months': months,
                    'avg_burn_rate': round(total_hours / months, 1)
                },
                'burn_schedule': schedule,
                'epic_breakdown': epic_estimates,
                'risks': {
                    'custom_epics': custom_epics,
                    'high_risk_epics': high_risk_epics
                }
            }
        })

    except Exception as e:
        logger.error(f"Error forecasting project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_bp.route('/projects', methods=['GET'])
@admin_required
def get_projects(user):
    """Get list of all projects with basic stats."""
    try:
        session = get_session()

        results = session.query(
            EpicHours.project_key,
            func.sum(EpicHours.hours).label('total_hours'),
            func.count(func.distinct(EpicHours.epic_key)).label('epic_count'),
            func.count(func.distinct(EpicHours.month)).label('month_count'),
            func.min(EpicHours.month).label('start_month'),
            func.max(EpicHours.month).label('end_month')
        ).group_by(
            EpicHours.project_key
        ).order_by(
            func.sum(EpicHours.hours).desc()
        ).all()

        projects = []
        for r in results:
            projects.append({
                'project_key': r.project_key,
                'total_hours': round(r.total_hours, 1),
                'epic_count': r.epic_count,
                'month_count': r.month_count,
                'start_month': r.start_month.strftime('%Y-%m'),
                'end_month': r.end_month.strftime('%Y-%m')
            })

        return jsonify({
            'success': True,
            'count': len(projects),
            'projects': projects
        })

    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_bp.route('/projects/<project_key>/composition', methods=['GET'])
@admin_required
def get_project_composition(user, project_key: str):
    """Get epic category breakdown for a specific project."""
    try:
        session = get_session()

        results = session.query(
            EpicHours.epic_summary,
            func.sum(EpicHours.hours).label('total_hours')
        ).filter(
            EpicHours.project_key == project_key
        ).group_by(
            EpicHours.epic_summary
        ).all()

        if not results:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        # Simple categorization for API
        categories = defaultdict(float)
        total_hours = 0

        for result in results:
            if not result.epic_summary:
                continue

            normalized = result.epic_summary.lower()
            total_hours += result.total_hours

            # Categorize
            if any(k in normalized for k in ['oversight', 'support', 'management']):
                categories['PM/Oversight'] += result.total_hours
            elif any(k in normalized for k in ['design', 'ux', 'ui']):
                categories['Design/UX'] += result.total_hours
            elif any(k in normalized for k in ['content', 'component', 'module']):
                categories['Content/Modules'] += result.total_hours
            elif any(k in normalized for k in ['header', 'footer', 'menu']):
                categories['Navigation'] += result.total_hours
            elif any(k in normalized for k in ['pdp', 'plp', 'product']):
                categories['Product Pages'] += result.total_hours
            elif any(k in normalized for k in ['search', 'filter', 'browse']):
                categories['Search/Browse'] += result.total_hours
            elif any(k in normalized for k in ['cart', 'checkout']):
                categories['Cart/Checkout'] += result.total_hours
            elif any(k in normalized for k in ['integration', 'api', 'migration']):
                categories['Integration'] += result.total_hours
            else:
                categories['Other'] += result.total_hours

        composition = []
        for category, hours in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            composition.append({
                'category': category,
                'hours': round(hours, 1),
                'percentage': round((hours / total_hours * 100) if total_hours > 0 else 0, 1)
            })

        pm_hours = categories.get('PM/Oversight', 0)
        pm_percentage = (pm_hours / total_hours * 100) if total_hours > 0 else 0

        return jsonify({
            'success': True,
            'project_key': project_key,
            'total_hours': round(total_hours, 1),
            'pm_hours': round(pm_hours, 1),
            'pm_percentage': round(pm_percentage, 1),
            'composition': composition
        })

    except Exception as e:
        logger.error(f"Error fetching project composition: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_bp.route('/variance', methods=['GET'])
@admin_required
def get_high_variance_epics(user):
    """Get list of high-variance epics that need careful scoping."""
    try:
        session = get_session()

        high_variance = session.query(EpicBaseline).filter(
            EpicBaseline.variance_level == 'high'
        ).order_by(
            EpicBaseline.coefficient_of_variation.desc()
        ).all()

        return jsonify({
            'success': True,
            'count': len(high_variance),
            'high_risk_epics': [{
                'epic_category': b.epic_category,
                'median_hours': b.median_hours,
                'range': f"{b.min_hours:.1f}h - {b.max_hours:.1f}h",
                'coefficient_of_variation': b.coefficient_of_variation,
                'project_count': b.project_count,
                'recommended_estimate': b.p90_hours  # Use P90 for high variance
            } for b in high_variance]
        })

    except Exception as e:
        logger.error(f"Error fetching high variance epics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
