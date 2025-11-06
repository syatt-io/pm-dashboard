"""add_epic_baselines_table_for_forecasting

Revision ID: 1f57a748f792
Revises: efece186aedd
Create Date: 2025-11-06 14:55:34.163613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f57a748f792'
down_revision: Union[str, Sequence[str], None] = 'efece186aedd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'epic_baselines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('epic_category', sa.String(length=200), nullable=False),
        sa.Column('median_hours', sa.Float(), nullable=False),
        sa.Column('mean_hours', sa.Float(), nullable=False),
        sa.Column('p75_hours', sa.Float(), nullable=False),
        sa.Column('p90_hours', sa.Float(), nullable=False),
        sa.Column('min_hours', sa.Float(), nullable=False),
        sa.Column('max_hours', sa.Float(), nullable=False),
        sa.Column('project_count', sa.Integer(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False),
        sa.Column('coefficient_of_variation', sa.Float(), nullable=False),
        sa.Column('variance_level', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('epic_category')
    )

    # Create indexes for efficient querying
    op.create_index('ix_epic_baselines_epic_category', 'epic_baselines', ['epic_category'])
    op.create_index('ix_epic_baselines_variance_level', 'epic_baselines', ['variance_level'])
    op.create_index('ix_epic_baselines_project_count', 'epic_baselines', ['project_count'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_epic_baselines_project_count', 'epic_baselines')
    op.drop_index('ix_epic_baselines_variance_level', 'epic_baselines')
    op.drop_index('ix_epic_baselines_epic_category', 'epic_baselines')
    op.drop_table('epic_baselines')
