"""add_user_teams_table_for_discipline_tracking

Revision ID: 45917e2f1229
Revises: 1f57a748f792
Create Date: 2025-11-06 17:18:30.805548

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "45917e2f1229"
down_revision: Union[str, Sequence[str], None] = "1f57a748f792"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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

    # Create indexes for efficient querying
    op.create_index("ix_user_teams_account_id", "user_teams", ["account_id"])
    op.create_index("ix_user_teams_team", "user_teams", ["team"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_teams_team", "user_teams")
    op.drop_index("ix_user_teams_account_id", "user_teams")
    op.drop_table("user_teams")
