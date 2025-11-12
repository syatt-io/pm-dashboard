#!/usr/bin/env python3
"""
Visualize hours analysis data from CSV export.

Creates charts and graphs for analyzing tracked hours by epic and month.

Usage:
    python scripts/visualize_hours.py /tmp/coop_hours_by_epic.csv
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 8)


def load_data(csv_path):
    """Load CSV data into pandas DataFrame."""
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nData shape: {df.shape}")
    return df


def create_monthly_trend(df, output_dir):
    """Create monthly hours trend chart."""
    monthly_totals = df.groupby("Month")["Hours"].sum().sort_index()

    plt.figure(figsize=(14, 6))
    plt.plot(
        monthly_totals.index,
        monthly_totals.values,
        marker="o",
        linewidth=2,
        markersize=8,
    )
    plt.title(
        f'{df["Project"].iloc[0]} - Monthly Hours Trend', fontsize=16, fontweight="bold"
    )
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Total Hours", fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)

    # Add value labels
    for x, y in zip(monthly_totals.index, monthly_totals.values):
        plt.text(x, y + 5, f"{y:.0f}h", ha="center", fontsize=9)

    plt.tight_layout()
    output_path = output_dir / "monthly_trend.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Saved: {output_path}")
    plt.close()


def create_epic_breakdown(df, output_dir, top_n=10):
    """Create epic breakdown chart (top N epics by hours)."""
    epic_totals = (
        df.groupby(["Epic", "Epic_Summary"])["Hours"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )

    plt.figure(figsize=(12, 8))
    colors = sns.color_palette("husl", len(epic_totals))
    bars = plt.barh(range(len(epic_totals)), epic_totals.values, color=colors)

    # Create labels with epic key and summary
    labels = [
        (
            f"{epic[0]}\n{epic[1][:50]}..."
            if len(epic[1]) > 50
            else f"{epic[0]}\n{epic[1]}"
        )
        for epic in epic_totals.index
    ]
    plt.yticks(range(len(epic_totals)), labels, fontsize=9)

    plt.xlabel("Total Hours", fontsize=12)
    plt.title(
        f'{df["Project"].iloc[0]} - Top {top_n} Epics by Hours',
        fontsize=16,
        fontweight="bold",
    )

    # Add value labels
    for i, (bar, value) in enumerate(zip(bars, epic_totals.values)):
        plt.text(value + 5, i, f"{value:.1f}h", va="center", fontsize=10)

    plt.tight_layout()
    output_path = output_dir / "epic_breakdown.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Saved: {output_path}")
    plt.close()


def create_heatmap(df, output_dir):
    """Create heatmap of hours by month and epic."""
    # Pivot data for heatmap
    pivot = df.pivot_table(
        values="Hours", index="Epic", columns="Month", aggfunc="sum", fill_value=0
    )

    # Only show top 15 epics by total hours
    epic_totals = pivot.sum(axis=1).sort_values(ascending=False).head(15)
    pivot_filtered = pivot.loc[epic_totals.index]

    plt.figure(figsize=(16, 10))
    sns.heatmap(
        pivot_filtered,
        annot=True,
        fmt=".0f",
        cmap="YlOrRd",
        cbar_kws={"label": "Hours"},
        linewidths=0.5,
    )
    plt.title(
        f'{df["Project"].iloc[0]} - Hours Heatmap (Top 15 Epics)',
        fontsize=16,
        fontweight="bold",
    )
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Epic", fontsize=12)
    plt.xticks(rotation=45)
    plt.yticks(rotation=0, fontsize=9)

    plt.tight_layout()
    output_path = output_dir / "hours_heatmap.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Saved: {output_path}")
    plt.close()


def create_stacked_area(df, output_dir, top_n=10):
    """Create stacked area chart showing top epics over time."""
    # Get top N epics by total hours
    epic_totals = (
        df.groupby("Epic")["Hours"].sum().sort_values(ascending=False).head(top_n)
    )
    top_epics = epic_totals.index.tolist()

    # Filter to top epics and pivot
    df_filtered = df[df["Epic"].isin(top_epics)]
    pivot = df_filtered.pivot_table(
        values="Hours", index="Month", columns="Epic", aggfunc="sum", fill_value=0
    )
    pivot = pivot.sort_index()

    plt.figure(figsize=(14, 8))
    pivot.plot(kind="area", stacked=True, alpha=0.7, ax=plt.gca())

    plt.title(
        f'{df["Project"].iloc[0]} - Hours Distribution Over Time (Top {top_n} Epics)',
        fontsize=16,
        fontweight="bold",
    )
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Hours", fontsize=12)
    plt.xticks(rotation=45)
    plt.legend(title="Epic", bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "stacked_area.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"✅ Saved: {output_path}")
    plt.close()


def create_summary_stats(df, output_dir):
    """Create summary statistics text file."""
    project = df["Project"].iloc[0]

    summary = []
    summary.append("=" * 80)
    summary.append(f"SUMMARY STATISTICS: {project}")
    summary.append("=" * 80)
    summary.append("")

    # Overall stats
    total_hours = df["Hours"].sum()
    num_months = df["Month"].nunique()
    num_epics = df["Epic"].nunique()
    avg_monthly = total_hours / num_months

    summary.append(f"Total Hours: {total_hours:.2f}h")
    summary.append(f"Months Covered: {num_months}")
    summary.append(f"Unique Epics: {num_epics}")
    summary.append(f"Average Monthly Hours: {avg_monthly:.2f}h")
    summary.append("")

    # Top 5 months by hours
    summary.append("-" * 80)
    summary.append("TOP 5 MONTHS BY HOURS")
    summary.append("-" * 80)
    top_months = df.groupby("Month")["Hours"].sum().sort_values(ascending=False).head(5)
    for month, hours in top_months.items():
        summary.append(f"  {month}: {hours:.2f}h")
    summary.append("")

    # Top 10 epics by hours
    summary.append("-" * 80)
    summary.append("TOP 10 EPICS BY HOURS")
    summary.append("-" * 80)
    top_epics = (
        df.groupby(["Epic", "Epic_Summary"])["Hours"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    for i, ((epic, summary_text), hours) in enumerate(top_epics.items(), 1):
        summary.append(f"  {i}. {epic} ({hours:.2f}h): {summary_text}")
    summary.append("")

    # Month-by-month breakdown
    summary.append("-" * 80)
    summary.append("MONTH-BY-MONTH BREAKDOWN")
    summary.append("-" * 80)
    for month in sorted(df["Month"].unique()):
        month_df = df[df["Month"] == month]
        month_total = month_df["Hours"].sum()
        num_epics_in_month = month_df["Epic"].nunique()
        summary.append(
            f"\n{month}: {month_total:.2f}h across {num_epics_in_month} epics"
        )

        # Top 3 epics for this month
        top_3 = (
            month_df.groupby(["Epic", "Epic_Summary"])["Hours"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
        )
        for (epic, summary_text), hours in top_3.items():
            pct = (hours / month_total * 100) if month_total > 0 else 0
            summary.append(f"    {epic}: {hours:.2f}h ({pct:.1f}%) - {summary_text}")

    summary.append("\n" + "=" * 80)

    output_path = output_dir / "summary_stats.txt"
    with open(output_path, "w") as f:
        f.write("\n".join(summary))

    print(f"✅ Saved: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/visualize_hours.py <csv_file>")
        print("Example: python scripts/visualize_hours.py /tmp/coop_hours_by_epic.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Create output directory
    output_dir = csv_path.parent / f"{csv_path.stem}_visualizations"
    output_dir.mkdir(exist_ok=True)
    print(f"\n📁 Output directory: {output_dir}\n")

    # Load data
    df = load_data(csv_path)

    # Create visualizations
    print("\n📊 Creating visualizations...\n")
    create_monthly_trend(df, output_dir)
    create_epic_breakdown(df, output_dir, top_n=10)
    create_heatmap(df, output_dir)
    create_stacked_area(df, output_dir, top_n=8)
    create_summary_stats(df, output_dir)

    print(f"\n✅ All visualizations saved to: {output_dir}")
    print(f"\nFiles created:")
    for file in sorted(output_dir.iterdir()):
        print(f"  - {file.name}")


if __name__ == "__main__":
    main()
