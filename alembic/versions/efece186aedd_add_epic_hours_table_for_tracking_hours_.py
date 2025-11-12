"""Add epic_hours table for tracking hours by epic and month

Revision ID: efece186aedd
Revises: 1cb7dec79db2
Create Date: 2025-11-06 08:47:39.803926

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "efece186aedd"
down_revision: Union[str, Sequence[str], None] = "1cb7dec79db2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "epic_hours",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("epic_key", sa.String(length=50), nullable=False),
        sa.Column("epic_summary", sa.String(length=500), nullable=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_key", "epic_key", "month", name="uq_project_epic_month"
        ),
    )

    # Create indexes for efficient querying
    op.create_index("ix_epic_hours_project_key", "epic_hours", ["project_key"])
    op.create_index("ix_epic_hours_epic_key", "epic_hours", ["epic_key"])
    op.create_index("ix_epic_hours_month", "epic_hours", ["month"])
    op.create_index(
        "ix_epic_hours_project_month", "epic_hours", ["project_key", "month"]
    )
    op.create_index("ix_epic_hours_epic_month", "epic_hours", ["epic_key", "month"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_epic_hours_epic_month", "epic_hours")
    op.drop_index("ix_epic_hours_project_month", "epic_hours")
    op.drop_index("ix_epic_hours_month", "epic_hours")
    op.drop_index("ix_epic_hours_epic_key", "epic_hours")
    op.drop_index("ix_epic_hours_project_key", "epic_hours")
    op.drop_table("epic_hours")
