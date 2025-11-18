"""Add meeting_prep_deliveries table for deduplication

Revision ID: 8ed38e72174e
Revises: cd46b52e1b7a
Create Date: 2025-11-18 11:00:52.866843

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8ed38e72174e"
down_revision: Union[str, Sequence[str], None] = "cd46b52e1b7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "meeting_prep_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_via_slack", sa.Boolean(), nullable=True, default=False),
        sa.Column("delivered_via_email", sa.Boolean(), nullable=True, default=False),
        sa.Column("digest_cache_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_meeting_prep_user_project",
        "meeting_prep_deliveries",
        ["user_id", "project_key"],
    )
    op.create_index(
        "idx_meeting_prep_delivered_at", "meeting_prep_deliveries", ["delivered_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_meeting_prep_delivered_at", table_name="meeting_prep_deliveries")
    op.drop_index("idx_meeting_prep_user_project", table_name="meeting_prep_deliveries")
    op.drop_table("meeting_prep_deliveries")
