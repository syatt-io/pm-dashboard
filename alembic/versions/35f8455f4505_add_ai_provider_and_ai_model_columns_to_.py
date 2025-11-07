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
    # Add ai_provider column (e.g., "openai", "anthropic", "google")
    op.add_column('processed_meetings', sa.Column('ai_provider', sa.String(length=50), nullable=True))

    # Add ai_model column (e.g., "gpt-4", "claude-3-5-sonnet", etc.)
    op.add_column('processed_meetings', sa.Column('ai_model', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Remove ai_provider and ai_model columns from processed_meetings table."""
    op.drop_column('processed_meetings', 'ai_model')
    op.drop_column('processed_meetings', 'ai_provider')
