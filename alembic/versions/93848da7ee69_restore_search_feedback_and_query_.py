"""Restore search_feedback and query_expansions tables

Revision ID: 93848da7ee69
Revises: 1923d6037f6e
Create Date: 2025-11-09 23:19:11.328978

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93848da7ee69'
down_revision: Union[str, Sequence[str], None] = '1923d6037f6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create search_feedback table
    op.create_table(
        'search_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('slack_user_id', sa.String(length=50), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=True),
        sa.Column('result_sources', sa.JSON(), nullable=True),
        sa.Column('top_result_source', sa.String(length=50), nullable=True),
        sa.Column('detail_level', sa.String(length=20), nullable=True),
        sa.Column('project_key', sa.String(length=10), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('summary_length', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create query_expansions table
    op.create_table(
        'query_expansions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('original_term', sa.String(length=100), nullable=False),
        sa.Column('expanded_term', sa.String(length=100), nullable=False),
        sa.Column('expansion_type', sa.String(length=20), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('project_key', sa.String(length=10), nullable=True),
        sa.Column('domain', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on original_term for query_expansions
    op.create_index('ix_query_expansions_original_term', 'query_expansions', ['original_term'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index('ix_query_expansions_original_term', table_name='query_expansions')
    op.drop_table('query_expansions')
    op.drop_table('search_feedback')
