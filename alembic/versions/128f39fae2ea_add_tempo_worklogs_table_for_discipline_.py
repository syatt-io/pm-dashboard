"""Add tempo_worklogs table for discipline-based forecasting

Revision ID: 128f39fae2ea
Revises: 2fc716c492ed
Create Date: 2025-11-13 13:15:38.577423

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "128f39fae2ea"
down_revision: Union[str, Sequence[str], None] = "2fc716c492ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create tempo_worklogs table for discipline-based forecasting analysis
    op.create_table(
        "tempo_worklogs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("worklog_id", sa.String(length=100), nullable=False),
        sa.Column("account_id", sa.String(length=100), nullable=False),
        sa.Column("issue_id", sa.String(length=100), nullable=False),
        sa.Column("issue_key", sa.String(length=50), nullable=False),
        sa.Column("epic_key", sa.String(length=50), nullable=True),
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False),
        sa.Column("user_display_name", sa.String(length=200), nullable=True),
        sa.Column("team", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_tempo_account_team", "tempo_worklogs", ["account_id", "team"], unique=False
    )
    op.create_index(
        "ix_tempo_epic_date", "tempo_worklogs", ["epic_key", "start_date"], unique=False
    )
    op.create_index(
        "ix_tempo_project_date",
        "tempo_worklogs",
        ["project_key", "start_date"],
        unique=False,
    )
    op.create_index(
        "ix_tempo_team_date", "tempo_worklogs", ["team", "start_date"], unique=False
    )
    op.create_index(
        op.f("ix_tempo_worklogs_account_id"),
        "tempo_worklogs",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tempo_worklogs_epic_key"), "tempo_worklogs", ["epic_key"], unique=False
    )
    op.create_index(
        op.f("ix_tempo_worklogs_issue_key"),
        "tempo_worklogs",
        ["issue_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tempo_worklogs_project_key"),
        "tempo_worklogs",
        ["project_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tempo_worklogs_start_date"),
        "tempo_worklogs",
        ["start_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tempo_worklogs_team"), "tempo_worklogs", ["team"], unique=False
    )
    op.create_index(
        op.f("ix_tempo_worklogs_worklog_id"),
        "tempo_worklogs",
        ["worklog_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tempo_worklogs table and all indexes
    op.drop_index(op.f("ix_tempo_worklogs_worklog_id"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_team"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_start_date"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_project_key"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_issue_key"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_epic_key"), table_name="tempo_worklogs")
    op.drop_index(op.f("ix_tempo_worklogs_account_id"), table_name="tempo_worklogs")
    op.drop_index("ix_tempo_team_date", table_name="tempo_worklogs")
    op.drop_index("ix_tempo_project_date", table_name="tempo_worklogs")
    op.drop_index("ix_tempo_epic_date", table_name="tempo_worklogs")
    op.drop_index("ix_tempo_account_team", table_name="tempo_worklogs")
    op.drop_table("tempo_worklogs")
