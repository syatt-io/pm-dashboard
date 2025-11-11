"""add epic categories table

Revision ID: b74d972657e5
Revises: d810ed090520
Create Date: 2025-11-11 10:18:31.568384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b74d972657e5'
down_revision: Union[str, Sequence[str], None] = 'd810ed090520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create epic_categories table
    op.create_table(
        'epic_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create index on display_order for efficient sorting
    op.create_index('ix_epic_categories_display_order', 'epic_categories', ['display_order'])

    # Seed with default categories (matching the hardcoded list)
    op.execute("""
        INSERT INTO epic_categories (name, display_order, created_at, updated_at)
        VALUES
            ('Project Oversight', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('UX', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('Design', 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('FE Dev', 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('BE Dev', 4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_epic_categories_display_order', table_name='epic_categories')
    op.drop_table('epic_categories')
