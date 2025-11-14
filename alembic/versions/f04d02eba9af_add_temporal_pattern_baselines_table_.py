"""Add temporal_pattern_baselines table for learned temporal patterns

Revision ID: f04d02eba9af
Revises: 65756603a42a
Create Date: 2025-11-13 22:55:24.403329

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f04d02eba9af"
down_revision: Union[str, Sequence[str], None] = "65756603a42a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create temporal_pattern_baselines table."""
    op.create_table(
        "temporal_pattern_baselines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timeline_start_pct", sa.Integer(), nullable=False),
        sa.Column("timeline_end_pct", sa.Integer(), nullable=False),
        sa.Column("team", sa.String(50), nullable=False),
        sa.Column("work_pct", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # Create indexes for efficient queries
    op.create_index(
        "ix_temporal_pattern_timeline",
        "temporal_pattern_baselines",
        ["timeline_start_pct", "timeline_end_pct"],
    )
    op.create_index("ix_temporal_pattern_team", "temporal_pattern_baselines", ["team"])

    # Create unique constraint to prevent duplicate entries
    op.create_index(
        "ix_temporal_pattern_unique",
        "temporal_pattern_baselines",
        ["timeline_start_pct", "timeline_end_pct", "team"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema - drop temporal_pattern_baselines table."""
    op.drop_index("ix_temporal_pattern_unique", table_name="temporal_pattern_baselines")
    op.drop_index("ix_temporal_pattern_team", table_name="temporal_pattern_baselines")
    op.drop_index(
        "ix_temporal_pattern_timeline", table_name="temporal_pattern_baselines"
    )
    op.drop_table("temporal_pattern_baselines")
