"""Add characteristic_impact_baselines table for learned multipliers

Revision ID: f449f47a0a61
Revises: f04d02eba9af
Create Date: 2025-11-13 23:27:53.290951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f449f47a0a61'
down_revision: Union[str, Sequence[str], None] = 'f04d02eba9af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create characteristic_impact_baselines table for learned team allocation multipliers."""
    # Create the characteristic_impact_baselines table
    op.create_table(
        'characteristic_impact_baselines',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('characteristic_name', sa.String(50), nullable=False,
                  comment='Name of the characteristic (e.g., custom_designs, be_integrations)'),
        sa.Column('characteristic_value', sa.Integer(), nullable=False,
                  comment='Value of the characteristic (1-5 scale)'),
        sa.Column('team', sa.String(50), nullable=False,
                  comment='Team name (e.g., Design, FE Devs, BE Devs)'),
        sa.Column('avg_allocation_pct', sa.Float(), nullable=False,
                  comment='Average percentage of total project hours this team used'),
        sa.Column('std_dev', sa.Float(), nullable=True,
                  comment='Standard deviation of allocation percentage'),
        sa.Column('sample_size', sa.Integer(), nullable=False,
                  comment='Number of historical projects in this category'),
        sa.Column('last_updated', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
                  comment='When this baseline was last recalculated'),
    )

    # Create composite index for efficient lookups
    op.create_index(
        'ix_characteristic_impact_lookup',
        'characteristic_impact_baselines',
        ['characteristic_name', 'characteristic_value', 'team'],
        unique=False
    )

    # Create index on characteristic name for queries
    op.create_index(
        'ix_characteristic_impact_name',
        'characteristic_impact_baselines',
        ['characteristic_name'],
        unique=False
    )

    # Create index on team for queries
    op.create_index(
        'ix_characteristic_impact_team',
        'characteristic_impact_baselines',
        ['team'],
        unique=False
    )


def downgrade() -> None:
    """Drop characteristic_impact_baselines table."""
    # Drop indexes first
    op.drop_index('ix_characteristic_impact_team', table_name='characteristic_impact_baselines')
    op.drop_index('ix_characteristic_impact_name', table_name='characteristic_impact_baselines')
    op.drop_index('ix_characteristic_impact_lookup', table_name='characteristic_impact_baselines')

    # Drop the table
    op.drop_table('characteristic_impact_baselines')
