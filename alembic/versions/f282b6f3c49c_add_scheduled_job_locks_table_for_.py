"""Add scheduled_job_locks table for deduplication

Revision ID: f282b6f3c49c
Revises: 23560ab97a47
Create Date: 2025-11-19 07:15:12.554267

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f282b6f3c49c"
down_revision: Union[str, Sequence[str], None] = "23560ab97a47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create scheduled_job_locks table for deduplication
    op.create_table(
        "scheduled_job_locks",
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("job_name"),
    )
    op.create_index(
        "idx_scheduled_job_locks_is_locked",
        "scheduled_job_locks",
        ["is_locked"],
        unique=False,
    )
    op.create_index(
        "idx_scheduled_job_locks_last_run_at",
        "scheduled_job_locks",
        ["last_run_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop scheduled_job_locks table
    op.drop_index(
        "idx_scheduled_job_locks_last_run_at", table_name="scheduled_job_locks"
    )
    op.drop_index("idx_scheduled_job_locks_is_locked", table_name="scheduled_job_locks")
    op.drop_table("scheduled_job_locks")
