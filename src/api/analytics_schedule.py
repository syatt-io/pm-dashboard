"""Project schedule generation logic for analytics."""

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from src.models import EpicHours
from src.utils.database import get_session


def normalize_epic_name(epic_summary: str) -> str:
    """Normalize epic names (same as in analytics.py)."""
    normalized = epic_summary.strip().lower()
    consolidations = {
        "pdp details": "product details",
        "pdp image & summary": "product details",
        "product detail page": "product details",
        "globals": "globals & style guide",
    }
    for pattern, canonical in consolidations.items():
        if normalized == pattern:
            return canonical
    return normalized


def calculate_epic_ratios():
    """
    Calculate average ratio of each epic to total project hours.

    Returns:
        dict: {epic_name: average_ratio}
    """
    session = get_session()
    all_records = session.query(EpicHours).all()

    # Calculate total hours per project
    project_totals = defaultdict(float)
    for record in all_records:
        project_totals[record.project_key] += record.hours

    # Calculate epic hours per project (with consolidation)
    project_epic_hours = defaultdict(lambda: defaultdict(float))
    for record in all_records:
        if not record.epic_summary:
            continue
        normalized = normalize_epic_name(record.epic_summary)
        project_epic_hours[record.project_key][normalized] += record.hours

    # Calculate ratios for each epic
    epic_ratios = {}
    epic_project_counts = defaultdict(int)

    for project_key, epics in project_epic_hours.items():
        project_total = project_totals[project_key]
        for epic, hours in epics.items():
            if epic not in epic_ratios:
                epic_ratios[epic] = []
            epic_ratios[epic].append(hours / project_total)
            epic_project_counts[epic] += 1

    # Return average ratio for epics in 3+ projects
    result = {}
    for epic, ratios in epic_ratios.items():
        if epic_project_counts[epic] >= 3:
            result[epic] = sum(ratios) / len(ratios)

    return result


def get_temporal_distribution_weights():
    """
    Return temporal distribution weights for each epic category.

    Based on research showing which epics are front-loaded, even, or back-loaded.

    Returns:
        dict: {epic_name: distribution_pattern}
        distribution_pattern: 'front', 'even', 'mid-peak', or 'back'
    """
    return {
        # Front-loaded (more hours in first 1/3)
        "footer": "front",
        "search": "front",
        "analytics": "front",
        "plp / srp": "front",
        "globals & style guide": "front",
        "header": "front",
        "components": "front",
        # Evenly distributed
        "project oversight / support": "even",
        "content sections": "even",
        "cart": "even",
        "product details": "even",
        "3rd party apps": "even",
        "design": "even",
        "ux": "even",
        "emails": "even",
        # Mid-peaked
        "pages": "mid-peak",
        # Back-loaded (more hours in last 1/3)
        "checkout": "back",
        "brands": "back",
        "mega menu": "back",
    }


def calculate_monthly_distribution(
    epic_name: str, total_hours: float, duration_months: int
):
    """
    Distribute epic hours across months based on temporal patterns.

    Args:
        epic_name: Name of the epic
        total_hours: Total allocated hours for this epic
        duration_months: Project duration in months

    Returns:
        list: Hours per month
    """
    distribution = get_temporal_distribution_weights().get(epic_name, "even")

    # Generate weights for each month based on distribution pattern
    weights = []

    if distribution == "front":
        # Front-loaded: Heavy first 1/3, light middle, lighter end
        for i in range(duration_months):
            if i < duration_months / 3:
                weights.append(1.8)  # 80% heavier
            elif i < duration_months * 2 / 3:
                weights.append(0.9)  # 10% lighter
            else:
                weights.append(0.5)  # 50% lighter

    elif distribution == "back":
        # Back-loaded: Light first 2/3, heavy last 1/3
        for i in range(duration_months):
            if i < duration_months * 2 / 3:
                weights.append(0.3)  # 70% lighter
            else:
                weights.append(2.5)  # 150% heavier

    elif distribution == "mid-peak":
        # Mid-peaked: Bell curve centered in middle
        for i in range(duration_months):
            # Distance from middle (0 = middle, 1 = edges)
            distance = abs(i - duration_months / 2) / (duration_months / 2)
            weights.append(2.0 - distance * 1.5)  # Peak at 2.0, edges at 0.5

    else:  # 'even'
        # Evenly distributed with slight ramp-up/down
        for i in range(duration_months):
            if i == 0:
                weights.append(0.8)  # Slightly lighter start
            elif i == duration_months - 1:
                weights.append(0.8)  # Slightly lighter end
            else:
                weights.append(1.0)  # Even middle

    # Normalize weights to sum to 1
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]

    # Calculate hours per month
    monthly_hours = [total_hours * w for w in normalized_weights]

    return monthly_hours


def generate_project_schedule(
    total_hours: float, duration_months: int, start_date: str
):
    """
    Generate complete project schedule with month-by-month breakdown.

    Args:
        total_hours: Total project hours
        duration_months: Project duration in months
        start_date: ISO format date string (YYYY-MM-DD)

    Returns:
        dict: Complete schedule with epic breakdowns
    """
    # Calculate epic ratios
    epic_ratios = calculate_epic_ratios()

    # Sort epics by name for consistent display
    sorted_epics = sorted(epic_ratios.keys())

    # Generate month labels from start date
    start_dt = datetime.fromisoformat(start_date)
    months = []
    for i in range(duration_months):
        month_dt = start_dt + relativedelta(months=i)
        months.append(month_dt.strftime("%Y-%m"))

    # Generate schedule for each epic
    epics_data = []
    monthly_totals = defaultdict(float)

    for epic in sorted_epics:
        ratio = epic_ratios[epic]
        allocated_hours = total_hours * ratio

        # Calculate monthly breakdown based on temporal patterns
        monthly_breakdown = calculate_monthly_distribution(
            epic, allocated_hours, duration_months
        )

        # Format monthly breakdown
        breakdown = []
        for i, month in enumerate(months):
            hours = round(monthly_breakdown[i], 1)
            breakdown.append({"month": month, "hours": hours})
            monthly_totals[month] += hours

        epics_data.append(
            {
                "epic_category": epic,
                "ratio": round(ratio, 4),
                "allocated_hours": round(allocated_hours, 1),
                "monthly_breakdown": breakdown,
            }
        )

    # Format monthly totals
    monthly_totals_list = [
        {"month": month, "total_hours": round(monthly_totals[month], 1)}
        for month in months
    ]

    return {
        "total_hours": total_hours,
        "duration_months": duration_months,
        "start_date": start_date,
        "months": months,
        "epics": epics_data,
        "monthly_totals": monthly_totals_list,
    }
