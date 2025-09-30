"""add_processed_meeting_columns

Revision ID: 27603eea68e9
Revises: 
Create Date: 2025-09-30 18:02:42.837674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27603eea68e9'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from alembic import context
    conn = context.get_bind()

    # Get existing columns
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('processed_meetings')}

    # Add new columns only if they don't exist
    if 'key_decisions' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('key_decisions', sa.Text(), nullable=True))
    if 'blockers' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('blockers', sa.Text(), nullable=True))
    if 'analyzed_at' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('analyzed_at', sa.DateTime(), nullable=True))
    if 'processed_at' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('processed_at', sa.DateTime(), nullable=True))
    if 'tickets_created' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('tickets_created', sa.Text(), nullable=True))
    if 'todos_created' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('todos_created', sa.Text(), nullable=True))
    if 'success' not in existing_columns:
        op.add_column('processed_meetings', sa.Column('success', sa.Boolean(), nullable=True, server_default='true'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from processed_meetings table
    op.drop_column('processed_meetings', 'success')
    op.drop_column('processed_meetings', 'todos_created')
    op.drop_column('processed_meetings', 'tickets_created')
    op.drop_column('processed_meetings', 'processed_at')
    op.drop_column('processed_meetings', 'analyzed_at')
    op.drop_column('processed_meetings', 'blockers')
    op.drop_column('processed_meetings', 'key_decisions')
