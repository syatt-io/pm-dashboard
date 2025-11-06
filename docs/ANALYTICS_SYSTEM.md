# Analytics & Forecasting System

## Overview

A comprehensive analytics system for deriving insights from historical epic hours data to provide better baseline estimates and project forecasting capabilities.

## System Architecture

### 1. Data Foundation
- **Source Data**: 574 epic hours records across 7 projects (COOP, IRIS, SRLK, CAR, BEVS, BIGO, BMBY)
- **Total Hours**: 8,903.12 hours of historical project data
- **Time Range**: Various projects with launch date cutoffs applied

### 2. Epic Baselines Database

**Location**: `src/models/epic_baselines.py`

**Purpose**: Stores statistical estimates for 22 common epics that appear across 3+ projects

**Schema**:
```python
class EpicBaseline:
    - epic_category: Normalized epic name
    - median_hours: Median hours (50th percentile)
    - mean_hours: Average hours
    - p75_hours: 75th percentile
    - p90_hours: 90th percentile
    - min_hours: Minimum observed hours
    - max_hours: Maximum observed hours
    - project_count: Number of projects featuring this epic
    - occurrence_count: Total times epic appeared
    - coefficient_of_variation: (std_dev / mean) * 100
    - variance_level: 'low' (CV < 80%), 'medium' (80-120%), 'high' (> 120%)
```

**Key Statistics**:
- 22 common epics identified
- Variance distribution: 1 low, 14 medium, 7 high
- Median estimate used for low variance, P75 for medium, P90 for high

### 3. CLI Analysis Scripts

#### `scripts/generate_epic_baselines.py`
- Analyzes historical data to populate baselines table
- Filters to epics appearing in 3+ projects
- Calculates statistical metrics (median, P75, P90, CV%)
- Classifies variance levels

**Usage**:
```bash
python scripts/generate_epic_baselines.py
```

#### `scripts/forecast_project.py`
- Forecasts project hours and timeline from epic list
- Matches epics against baselines (exact + fuzzy matching)
- Applies 25% PM overhead
- Generates month-by-month burn rate schedule

**Usage**:
```bash
python scripts/forecast_project.py --epics "Header,Footer,Cart,Search"
python scripts/forecast_project.py --epics-file epics.txt
```

**Output**:
- Development hours estimate
- Total hours (dev + 25% PM overhead)
- Confidence interval (±10%/20%/30%)
- Project size classification (Small < 900h, Medium 900-1400h, Large > 1400h)
- Estimated months and burn rate
- Risk assessment (custom epics, high-variance epics)
- Month-by-month burn schedule

#### `scripts/analyze_project_composition.py`
- Categorizes epics into 11 categories
- Calculates PM overhead percentage
- Shows category distribution by project

**Categories**:
- PM/Oversight
- Design/UX
- Content/Modules
- Navigation
- Product Pages
- Search/Browse
- Cart/Checkout
- Account/Auth
- Integration
- Infrastructure
- Custom Features

**Usage**:
```bash
python scripts/analyze_project_composition.py
python scripts/analyze_project_composition.py --project COOP
```

#### `scripts/analyze_temporal_patterns.py`
- Analyzes project lifecycle patterns (early/mid/late phases)
- Calculates burn rates by month
- Classifies projects as front-loaded, balanced, or back-loaded

**Usage**:
```bash
python scripts/analyze_temporal_patterns.py
python scripts/analyze_temporal_patterns.py --project COOP
```

#### `scripts/analyze_custom_features.py`
- Identifies project-specific epics (appearing in only 1 project)
- Calculates custom complexity scores
- Flags high-risk custom epics (> 50 hours)

**Complexity Levels**:
- Low: < 20% custom work
- Medium: 20-40% custom work
- High: > 40% custom work

**Usage**:
```bash
python scripts/analyze_custom_features.py
python scripts/analyze_custom_features.py --project COOP
```

## REST API Endpoints

**Location**: `src/api/analytics.py`

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

### 1. GET `/api/analytics/baselines`
Get all epic baselines with optional filters.

**Query Parameters**:
- `variance_level`: Filter by 'low', 'medium', or 'high'
- `min_projects`: Minimum number of projects (integer)

**Response**:
```json
{
  "success": true,
  "count": 22,
  "baselines": [
    {
      "epic_category": "header",
      "median_hours": 45.2,
      "mean_hours": 48.5,
      "p75_hours": 55.0,
      "p90_hours": 62.1,
      "min_hours": 32.5,
      "max_hours": 78.3,
      "project_count": 5,
      "occurrence_count": 7,
      "coefficient_of_variation": 25.4,
      "variance_level": "low",
      "recommended_estimate": 45.2
    }
  ]
}
```

### 2. POST `/api/analytics/forecast`
Forecast project hours and timeline based on epic list.

**Request Body**:
```json
{
  "epics": ["Header", "Footer", "Cart", "Search", "PDP"]
}
```

**Response**:
```json
{
  "success": true,
  "forecast": {
    "summary": {
      "total_epics": 5,
      "matched_epics": 5,
      "custom_epics": 0,
      "development_hours": 284.5,
      "pm_overhead_hours": 71.1,
      "total_hours": 355.6,
      "confidence": "high",
      "range_low": 319.0,
      "range_high": 392.2
    },
    "timeline": {
      "project_size": "small",
      "estimated_months": 8,
      "avg_burn_rate": 44.5
    },
    "burn_schedule": [
      {"month": 1, "hours": 51.2, "cumulative": 51.2},
      {"month": 2, "hours": 51.2, "cumulative": 102.4}
      // ...
    ],
    "epic_breakdown": [
      {
        "epic": "Header",
        "matched_category": "header",
        "hours": 45.2,
        "variance_level": "low",
        "confidence": "high",
        "range": "32.5-78.3h"
      }
    ],
    "risks": {
      "custom_epics": [],
      "high_risk_epics": []
    }
  }
}
```

### 3. GET `/api/analytics/projects`
Get list of all projects with basic stats.

**Response**:
```json
{
  "success": true,
  "count": 7,
  "projects": [
    {
      "project_key": "COOP",
      "total_hours": 1245.5,
      "epic_count": 18,
      "month_count": 12,
      "start_month": "2023-01",
      "end_month": "2023-12"
    }
  ]
}
```

### 4. GET `/api/analytics/projects/<project_key>/composition`
Get epic category breakdown for a specific project.

**Response**:
```json
{
  "success": true,
  "project_key": "COOP",
  "total_hours": 1245.5,
  "pm_hours": 287.3,
  "pm_percentage": 23.1,
  "composition": [
    {
      "category": "PM/Oversight",
      "hours": 287.3,
      "percentage": 23.1
    },
    {
      "category": "Design/UX",
      "hours": 156.8,
      "percentage": 12.6
    }
  ]
}
```

### 5. GET `/api/analytics/variance`
Get list of high-variance epics needing careful scoping.

**Response**:
```json
{
  "success": true,
  "count": 7,
  "high_risk_epics": [
    {
      "epic_category": "integration",
      "median_hours": 85.5,
      "range": "45.2h - 156.8h",
      "coefficient_of_variation": 145.2,
      "project_count": 4,
      "recommended_estimate": 142.1
    }
  ]
}
```

## Web Dashboard

**Location**: `frontend/src/components/Analytics.tsx`

**Access**: Navigate to "Analytics" in the main navigation menu

### Features

#### Tab 1: Epic Baselines
- View all 22 common epics with historical data
- Shows median, P75, P90, range, project count, variance level
- Recommended estimate highlighted
- Filter and sort capabilities

#### Tab 2: Project Forecasting
- Input epic names (one per line)
- Generates comprehensive forecast:
  - Hours estimate (dev + PM overhead)
  - Confidence interval
  - Timeline (months, burn rate)
  - Risk warnings (custom epics, high-variance epics)
- Real-time forecasting via API

#### Tab 3: High-Risk Epics
- List of 7 high-variance epics
- Shows CV%, range, recommended P90 estimates
- Warning alerts for careful scoping

## Key Algorithms

### Variance Classification
```python
def classify_variance(cv: float) -> str:
    if cv < 80:
        return 'low'      # Predictable
    elif cv < 120:
        return 'medium'   # Moderate variation
    else:
        return 'high'     # High uncertainty
```

### Recommended Estimate Selection
```python
def get_recommended_estimate(baseline):
    if baseline.variance_level == 'low':
        return baseline.median_hours
    elif baseline.variance_level == 'medium':
        return baseline.p75_hours
    else:
        return baseline.p90_hours  # Conservative for high variance
```

### Burn Rate Distribution
Weighted distribution across project phases:
- **Early Phase (first 1/3)**: 130% of average
- **Mid Phase (middle 1/3)**: 100% of average
- **Late Phase (last 1/3)**: 70% of average

### PM Overhead
Fixed at 25% based on historical average of 28.3% (range: 21.3% - 41.4%)

### Confidence Intervals
- **High Confidence** (±10%): No custom epics, few high-variance epics
- **Medium Confidence** (±20%): Some high-variance epics
- **Low Confidence** (±30%): Custom epics or many high-variance epics

## Project Size Tiers

Based on total hours (dev + PM overhead):

| Size   | Threshold | Typical Duration | Typical Burn Rate |
|--------|-----------|------------------|-------------------|
| Small  | < 900h    | 8 months         | 118.65 h/month    |
| Medium | 900-1400h | 12 months        | 87.52 h/month     |
| Large  | > 1400h   | 12 months        | 136.64 h/month    |

## Usage Workflows

### Sales/PM: Scoping a New Project

1. **Prepare Epic List**: List all expected epics for the project
2. **Use Forecasting Tool**:
   - Navigate to Analytics → Project Forecasting
   - Enter epic names (one per line)
   - Click "Generate Forecast"
3. **Review Results**:
   - Note total hours estimate and confidence level
   - Check confidence interval range
   - Review risk warnings
4. **Add Buffers**:
   - Custom epics: Add 30-50% buffer
   - High-variance epics: Add 20-30% buffer
5. **Finalize Estimate**: Use upper bound of confidence interval for proposals

### PM: Project Planning

1. **Check Epic Baselines**: Review historical data for each epic
2. **Identify High-Risk Areas**: Check High-Risk Epics tab
3. **Plan Burn Schedule**: Use burn rate schedule for resource planning
4. **Set Milestones**: Align with early/mid/late phase patterns

### Leadership: Historical Analysis

1. **Project Composition**: Analyze category distribution across projects
2. **Temporal Patterns**: Understand typical project progression
3. **Custom Complexity**: Assess project-specific work levels

## Testing

### API Endpoints
```bash
# Test baseline endpoint
curl -X GET "http://localhost:4000/api/analytics/baselines" \
  -H "Authorization: Bearer <token>"

# Test forecasting
curl -X POST "http://localhost:4000/api/analytics/forecast" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"epics": ["Header", "Footer", "Cart"]}'
```

### CLI Scripts
```bash
# Generate baselines
python scripts/generate_epic_baselines.py

# Test forecasting
python scripts/forecast_project.py --epics "Header,Footer,Cart"

# Run analysis
python scripts/analyze_project_composition.py --project COOP
```

## Database Migration

To regenerate baselines from updated data:

```bash
# Clear existing baselines
python -c "from src.models import EpicBaseline; from src.utils.database import get_session; session = get_session(); session.query(EpicBaseline).delete(); session.commit()"

# Regenerate baselines
python scripts/generate_epic_baselines.py
```

## Known Limitations

1. **Minimum Project Count**: Epics must appear in 3+ projects to be included in baselines
2. **Fuzzy Matching**: Epic name matching may occasionally mismatch similar names
3. **Static PM Overhead**: Fixed at 25%, doesn't account for project-specific needs
4. **Historical Data Only**: Estimates based on past projects, may not reflect future changes

## Future Enhancements

1. **Machine Learning**: Predict custom epic hours using project characteristics
2. **Dynamic PM Overhead**: Calculate based on project size and complexity
3. **Risk Scoring**: Quantitative risk scores for projects
4. **Real-time Updates**: Auto-update baselines as new project data arrives
5. **Export Capabilities**: PDF/CSV export of forecasts
6. **Saved Scenarios**: Save and compare multiple forecast scenarios

## Support

For questions or issues:
- Check API logs: `src/api/analytics.py`
- Review database: `src/models/epic_baselines.py`
- Test CLI scripts: `scripts/forecast_project.py`
