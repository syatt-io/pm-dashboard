"""drop_forecasted_hours_month_from_projects

Revision ID: 1cb7dec79db2
Revises: 0c8e7c36384c
Create Date: 2025-11-05 09:40:15.303871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cb7dec79db2'
down_revision: Union[str, Sequence[str], None] = '0c8e7c36384c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop forecasted_hours_month column from projects table.

    All forecasted hours data is now stored in project_monthly_forecast table only.
    """
    # Drop the column if it exists (using raw SQL for IF EXISTS support)
    op.execute('ALTER TABLE projects DROP COLUMN IF EXISTS forecasted_hours_month')


def downgrade() -> None:
    """Re-add forecasted_hours_month column to projects table."""
    # Re-add the column if we need to rollback
    op.add_column('projects',
        sa.Column('forecasted_hours_month', sa.NUMERIC(precision=10, scale=2), nullable=True)
    )
