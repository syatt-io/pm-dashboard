"""add ai_provider and ai_model columns to processed_meetings

Revision ID: 35f8455f4505
Revises: feac5fe7245d
Create Date: 2025-11-07 11:46:33.785778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35f8455f4505'
down_revision: Union[str, Sequence[str], None] = 'feac5fe7245d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_provider and ai_model columns to processed_meetings table."""
    # Check if columns already exist (idempotent migration)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('processed_meetings')]

    # Add ai_provider column if it doesn't exist
    if 'ai_provider' not in columns:
        op.add_column('processed_meetings', sa.Column('ai_provider', sa.String(length=50), nullable=True))

    # Add ai_model column if it doesn't exist
    if 'ai_model' not in columns:
        op.add_column('processed_meetings', sa.Column('ai_model', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Remove ai_provider and ai_model columns from processed_meetings table."""
    # Check if columns exist before trying to drop them (idempotent migration)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('processed_meetings')]

    # Drop ai_model column if it exists
    if 'ai_model' in columns:
        op.drop_column('processed_meetings', 'ai_model')

    # Drop ai_provider column if it exists
    if 'ai_provider' in columns:
        op.drop_column('processed_meetings', 'ai_provider')
