"""add_system_settings_table

Revision ID: 2f3e386f9b02
Revises: 27603eea68e9
Create Date: 2025-10-21 11:15:02.288481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f3e386f9b02'
down_revision: Union[str, Sequence[str], None] = '27603eea68e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ai_provider', sa.String(length=50), nullable=False),
        sa.Column('ai_model', sa.String(length=100), nullable=True),
        sa.Column('ai_temperature', sa.Float(), nullable=False),
        sa.Column('ai_max_tokens', sa.Integer(), nullable=False),
        sa.Column('openai_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('anthropic_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('google_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('system_settings')
