"""Restore project_resource_mappings and project_monthly_forecast tables

Revision ID: def376e3c089
Revises: 9391760ed2b5
Create Date: 2025-11-09 23:58:38.024471

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "def376e3c089"
down_revision: Union[str, Sequence[str], None] = "9391760ed2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - restore dropped tables."""
    # Restore project_resource_mappings table
    op.create_table(
        "project_resource_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_key", sa.Text(), nullable=False),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("slack_channel_ids", sa.Text(), nullable=True),
        sa.Column("notion_page_ids", sa.Text(), nullable=True),
        sa.Column("github_repos", sa.Text(), nullable=True),
        sa.Column("jira_project_keys", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("internal_slack_channels", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key"),
    )
    op.create_index(
        "idx_project_resource_mappings_key",
        "project_resource_mappings",
        ["project_key"],
        unique=False,
    )

    # Restore project_monthly_forecast table
    op.create_table(
        "project_monthly_forecast",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("month_year", sa.Date(), nullable=False),
        sa.Column(
            "forecasted_hours",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "actual_monthly_hours",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["project_key"], ["projects.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "month_year", name="unique_project_month"),
    )
    op.create_index(
        "idx_project_monthly_forecast_project_key",
        "project_monthly_forecast",
        ["project_key"],
        unique=False,
    )
    op.create_index(
        "idx_project_monthly_forecast_month_year",
        "project_monthly_forecast",
        ["month_year"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema - drop the restored tables."""
    op.drop_index(
        "idx_project_monthly_forecast_month_year", table_name="project_monthly_forecast"
    )
    op.drop_index(
        "idx_project_monthly_forecast_project_key",
        table_name="project_monthly_forecast",
    )
    op.drop_table("project_monthly_forecast")

    op.drop_index(
        "idx_project_resource_mappings_key", table_name="project_resource_mappings"
    )
    op.drop_table("project_resource_mappings")
