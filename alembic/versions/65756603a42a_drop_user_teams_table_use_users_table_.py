"""Drop user_teams table - use users table as single source of truth

Revision ID: 65756603a42a
Revises: 128f39fae2ea
Create Date: 2025-11-13 13:57:16.341234

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "65756603a42a"
down_revision: Union[str, Sequence[str], None] = "128f39fae2ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - drop user_teams table, use users table instead."""
    # Drop indexes first
    op.drop_index("ix_user_teams_team", table_name="user_teams")
    op.drop_index("ix_user_teams_account_id", table_name="user_teams")

    # Drop the table
    op.drop_table("user_teams")


def downgrade() -> None:
    """Downgrade schema - recreate user_teams table."""
    # Recreate table
    op.create_table(
        "user_teams",
        sa.Column("account_id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("team", sa.String(length=50), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("account_id"),
    )

    # Recreate indexes
    op.create_index("ix_user_teams_account_id", "user_teams", ["account_id"])
    op.create_index("ix_user_teams_team", "user_teams", ["team"])
