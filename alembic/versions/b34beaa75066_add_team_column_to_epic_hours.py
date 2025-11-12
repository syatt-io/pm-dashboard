"""add_team_column_to_epic_hours

Revision ID: b34beaa75066
Revises: 45917e2f1229
Create Date: 2025-11-06 17:36:39.420259

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b34beaa75066"
down_revision: Union[str, Sequence[str], None] = "45917e2f1229"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add team column to epic_hours."""
    # Step 1: Delete all existing epic_hours records
    # (necessary because we can't backfill team data for existing records)
    op.execute("DELETE FROM epic_hours")

    # Step 2: Drop old unique constraint
    op.drop_constraint("uq_project_epic_month", "epic_hours", type_="unique")

    # Step 3: Add team column (NOT NULL)
    op.add_column("epic_hours", sa.Column("team", sa.String(length=50), nullable=False))

    # Step 4: Create new unique constraint with team
    op.create_unique_constraint(
        "uq_project_epic_month_team",
        "epic_hours",
        ["project_key", "epic_key", "month", "team"],
    )

    # Step 5: Add index for team column
    op.create_index("ix_epic_hours_team", "epic_hours", ["team"])


def downgrade() -> None:
    """Downgrade schema - remove team column from epic_hours."""
    # Step 1: Drop team index
    op.drop_index("ix_epic_hours_team", "epic_hours")

    # Step 2: Drop new unique constraint
    op.drop_constraint("uq_project_epic_month_team", "epic_hours", type_="unique")

    # Step 3: Remove team column
    op.drop_column("epic_hours", "team")

    # Step 4: Restore old unique constraint
    op.create_unique_constraint(
        "uq_project_epic_month", "epic_hours", ["project_key", "epic_key", "month"]
    )
