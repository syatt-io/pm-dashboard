"""Add epic_allocation_baselines table for learned epic ranges

Revision ID: 5b25d1d9a8fa
Revises: f449f47a0a61
Create Date: 2025-11-14 07:07:42.289188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b25d1d9a8fa'
down_revision: Union[str, Sequence[str], None] = 'f449f47a0a61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create epic_allocation_baselines table for learned epic category ranges."""
    # Create the epic_allocation_baselines table
    op.create_table(
        'epic_allocation_baselines',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('epic_category', sa.String(100), nullable=False,
                  comment='Epic category name (e.g., FE Dev, BE Dev, Design)'),
        sa.Column('min_allocation_pct', sa.Float(), nullable=False,
                  comment='Minimum allocation percentage seen historically'),
        sa.Column('max_allocation_pct', sa.Float(), nullable=False,
                  comment='Maximum allocation percentage seen historically'),
        sa.Column('avg_allocation_pct', sa.Float(), nullable=False,
                  comment='Average allocation percentage across all projects'),
        sa.Column('std_dev', sa.Float(), nullable=True,
                  comment='Standard deviation of allocation percentage'),
        sa.Column('sample_size', sa.Integer(), nullable=False,
                  comment='Number of historical projects in this category'),
        sa.Column('last_updated', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
                  comment='When this baseline was last recalculated'),
    )

    # Create unique index on epic_category
    op.create_index(
        'ix_epic_allocation_category',
        'epic_allocation_baselines',
        ['epic_category'],
        unique=True
    )


def downgrade() -> None:
    """Drop epic_allocation_baselines table."""
    # Drop index first
    op.drop_index('ix_epic_allocation_category', table_name='epic_allocation_baselines')

    # Drop the table
    op.drop_table('epic_allocation_baselines')
