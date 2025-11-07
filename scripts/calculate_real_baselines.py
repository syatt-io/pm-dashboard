"""
Calculate REAL baseline hours from actual historical projects.

This replaces the fabricated baseline CSV with actual averages from our project data.
"""

import pandas as pd
from pathlib import Path

# Load the data
data_path = Path(__file__).parent.parent / 'analysis_results' / 'deep_insights' / '5_monthly_trends.csv'
df = pd.read_csv(data_path)

print("=" * 80)
print("CALCULATING REAL BASELINES FROM HISTORICAL DATA")
print("=" * 80)
print()

# Calculate total hours per team per project
project_totals = df.groupby(['Project', 'Team'])['Hours'].sum().reset_index()

print("Project totals by team:")
print(project_totals.pivot(index='Project', columns='Team', values='Hours').fillna(0))
print()

# Calculate average hours per team across all projects
team_averages = project_totals.groupby('Team')['Hours'].mean()

print("=" * 80)
print("AVERAGE HOURS PER TEAM (across all projects)")
print("=" * 80)
for team in ['BE Devs', 'FE Devs', 'Design', 'UX', 'PMs', 'Data']:
    if team in team_averages:
        print(f"{team}: {team_averages[team]:.2f}h")
    else:
        print(f"{team}: No data")

print()
print("=" * 80)
print("ISSUE: All projects are different!")
print("=" * 80)
print()
print("The real problem: Projects vary WILDLY in scope and characteristics.")
print("BIGO/BMBY are FE-heavy (minimal BE), SRLK is balanced.")
print()
print("We CANNOT create meaningful 'with_integration' vs 'no_integration' baselines")
print("from only 3 projects when we don't know which had integrations!")
print()
print("RECOMMENDATION:")
print("  1. Remove the fake baseline CSV entirely")
print("  2. Remove the 'with_integration' / 'no_integration' distinction")
print("  3. Just use team selection + user estimates")
print("  4. Let user adjust ratios manually if needed")
