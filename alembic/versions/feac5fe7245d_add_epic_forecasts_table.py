"""add_epic_forecasts_table

Revision ID: feac5fe7245d
Revises: b34beaa75066
Create Date: 2025-11-06 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "feac5fe7245d"
down_revision: Union[str, Sequence[str], None] = "b34beaa75066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create epic_forecasts table for storing project hour forecasts."""
    op.create_table(
        "epic_forecasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("epic_name", sa.String(length=200), nullable=False),
        sa.Column("epic_description", sa.Text(), nullable=True),
        sa.Column("be_integrations", sa.Boolean(), nullable=False),
        sa.Column("custom_theme", sa.Boolean(), nullable=False),
        sa.Column("custom_designs", sa.Boolean(), nullable=False),
        sa.Column("ux_research", sa.Boolean(), nullable=False),
        sa.Column("estimated_months", sa.Integer(), nullable=False),
        sa.Column(
            "teams_selected", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "forecast_data", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("total_hours", sa.Float(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_epic_forecasts_project_key", "epic_forecasts", ["project_key"])


def downgrade() -> None:
    """Drop epic_forecasts table."""
    op.drop_index("ix_epic_forecasts_project_key", "epic_forecasts")
    op.drop_table("epic_forecasts")
