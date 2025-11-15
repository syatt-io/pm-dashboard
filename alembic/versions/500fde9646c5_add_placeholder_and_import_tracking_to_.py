"""add placeholder and import tracking to epic_budgets

Revision ID: 500fde9646c5
Revises: 5b25d1d9a8fa
Create Date: 2025-11-14 18:56:43.966696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '500fde9646c5'
down_revision: Union[str, Sequence[str], None] = '5b25d1d9a8fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to epic_budgets table for tracking placeholder and imported epics
    op.add_column('epic_budgets', sa.Column('is_placeholder', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('epic_budgets', sa.Column('imported_at', sa.DateTime(), nullable=True))
    op.add_column('epic_budgets', sa.Column('import_source', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from epic_budgets table
    op.drop_column('epic_budgets', 'import_source')
    op.drop_column('epic_budgets', 'imported_at')
    op.drop_column('epic_budgets', 'is_placeholder')
