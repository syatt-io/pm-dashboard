"""
Calculate actual lifecycle distributions from historical data.

This script analyzes real project data to determine how hours are actually
distributed across project phases for each team, rather than using assumptions.
"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

# Read the monthly trends data
data_path = Path(__file__).parent.parent / 'analysis_results' / 'deep_insights' / '5_monthly_trends.csv'
df = pd.read_csv(data_path)

# Group by project and team to analyze each project's lifecycle
projects_analyzed = defaultdict(lambda: defaultdict(list))

for project in df['Project'].unique():
    project_data = df[df['Project'] == project].copy()

    # Sort by year and month
    # Month column already contains YYYY-MM format
    project_data['Date'] = pd.to_datetime(project_data['Month'], format='%Y-%m')
    project_data = project_data.sort_values('Date')

    for team in project_data['Team'].unique():
        team_data = project_data[project_data['Team'] == team].copy()

        if len(team_data) < 3:
            continue  # Need at least 3 months for lifecycle analysis

        total_hours = team_data['Hours'].sum()

        if total_hours < 10:  # Skip teams with minimal involvement
            continue

        # Determine lifecycle phases based on position in project
        num_months = len(team_data)

        # Calculate thirds for ramp up, busy, ramp down
        ramp_up_months = max(1, int(num_months * 0.33))
        ramp_down_months = max(1, int(num_months * 0.33))
        busy_months = num_months - ramp_up_months - ramp_down_months

        # Get hours for each phase
        team_data_reset = team_data.reset_index(drop=True)

        ramp_up_hours = team_data_reset.iloc[:ramp_up_months]['Hours'].sum()
        ramp_down_hours = team_data_reset.iloc[-ramp_down_months:]['Hours'].sum()

        if busy_months > 0:
            busy_hours = team_data_reset.iloc[ramp_up_months:-ramp_down_months]['Hours'].sum()
        else:
            busy_hours = 0

        # Calculate percentages
        ramp_up_pct = (ramp_up_hours / total_hours) * 100
        busy_pct = (busy_hours / total_hours) * 100
        ramp_down_pct = (ramp_down_hours / total_hours) * 100

        projects_analyzed[team]['ramp_up'].append(ramp_up_pct)
        projects_analyzed[team]['busy'].append(busy_pct)
        projects_analyzed[team]['ramp_down'].append(ramp_down_pct)

        # Store details for inspection
        projects_analyzed[team]['examples'].append({
            'project': project,
            'months': num_months,
            'total_hours': total_hours,
            'ramp_up': ramp_up_pct,
            'busy': busy_pct,
            'ramp_down': ramp_down_pct
        })

# Calculate averages and display results
print("=" * 80)
print("ACTUAL LIFECYCLE DISTRIBUTIONS FROM HISTORICAL DATA")
print("=" * 80)
print()

for team in ['BE Devs', 'FE Devs', 'Design', 'UX', 'PMs', 'Data']:
    if team not in projects_analyzed:
        print(f"{team}: No sufficient data")
        continue

    data = projects_analyzed[team]

    avg_ramp_up = sum(data['ramp_up']) / len(data['ramp_up'])
    avg_busy = sum(data['busy']) / len(data['busy'])
    avg_ramp_down = sum(data['ramp_down']) / len(data['ramp_down'])

    print(f"\n{team}:")
    print(f"  Sample size: {len(data['ramp_up'])} projects")
    print(f"  Ramp Up:   {avg_ramp_up:5.1f}% (range: {min(data['ramp_up']):.1f}% - {max(data['ramp_up']):.1f}%)")
    print(f"  Busy Peak: {avg_busy:5.1f}% (range: {min(data['busy']):.1f}% - {max(data['busy']):.1f}%)")
    print(f"  Ramp Down: {avg_ramp_down:5.1f}% (range: {min(data['ramp_down']):.1f}% - {max(data['ramp_down']):.1f}%)")

    # Show a few examples
    if 'examples' in data:
        print(f"\n  Example projects:")
        for ex in data['examples'][:3]:
            print(f"    {ex['project']}: {ex['months']} months, {ex['total_hours']:.0f}h total")
            print(f"      → {ex['ramp_up']:.1f}% / {ex['busy']:.1f}% / {ex['ramp_down']:.1f}%")

print("\n" + "=" * 80)
print("CURRENT CODED VALUES (for comparison):")
print("=" * 80)

current_values = {
    'BE Devs': {'ramp_up': 20.0, 'busy': 60.0, 'ramp_down': 20.0},
    'FE Devs': {'ramp_up': 15.0, 'busy': 65.0, 'ramp_down': 20.0},
    'Design': {'ramp_up': 85.0, 'busy': 10.0, 'ramp_down': 5.0},
    'UX': {'ramp_up': 80.0, 'busy': 15.0, 'ramp_down': 5.0},
    'PMs': {'ramp_up': 40.0, 'busy': 40.0, 'ramp_down': 20.0},
    'Data': {'ramp_up': 25.0, 'busy': 50.0, 'ramp_down': 25.0}
}

for team, values in current_values.items():
    print(f"\n{team}: {values['ramp_up']:.1f}% / {values['busy']:.1f}% / {values['ramp_down']:.1f}%")
