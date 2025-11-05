"""add_escalation_and_channel_safety_tables

Revision ID: 3b36763ff547
Revises: 80cb362b10db
Create Date: 2025-11-04 21:23:33.640097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b36763ff547'
down_revision: Union[str, Sequence[str], None] = '80cb362b10db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add internal_slack_channels field to project_resource_mappings
    # This field stores comma-separated list of internal-only channel IDs
    # that are safe for escalation notifications (no client channels)
    op.add_column(
        'project_resource_mappings',
        sa.Column('internal_slack_channels', sa.Text(), nullable=True)
    )

    # 2. Add escalation tracking fields to proactive_insights
    op.add_column(
        'proactive_insights',
        sa.Column('last_escalated_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'proactive_insights',
        sa.Column('escalation_count', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'proactive_insights',
        sa.Column('escalation_level', sa.Integer(), nullable=False, server_default='0')
    )

    # Create index for escalation queries
    op.create_index('ix_proactive_insights_last_escalated_at', 'proactive_insights', ['last_escalated_at'])

    # 3. Create escalation_history table for audit trail
    op.create_table(
        'escalation_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('insight_id', sa.String(36), sa.ForeignKey('proactive_insights.id'), nullable=False),
        sa.Column('escalation_type', sa.String(50), nullable=False),  # 'dm', 'channel', 'github_comment'
        sa.Column('escalation_level', sa.Integer(), nullable=False),  # 1, 2, 3
        sa.Column('target', sa.String(255), nullable=False),  # User ID, channel ID, or PR URL
        sa.Column('message_sent', sa.Text(), nullable=True),  # Copy of message for audit
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Create indexes for escalation_history
    op.create_index('ix_escalation_history_insight_id', 'escalation_history', ['insight_id'])
    op.create_index('ix_escalation_history_created_at', 'escalation_history', ['created_at'])
    op.create_index('ix_escalation_history_escalation_type', 'escalation_history', ['escalation_type'])

    # 4. Create escalation_preferences table for user opt-in control
    op.create_table(
        'escalation_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('enable_auto_escalation', sa.Boolean(), nullable=False, server_default='false'),  # Opt-in only
        sa.Column('enable_dm_escalation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_channel_escalation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_github_escalation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('dm_threshold_days', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('channel_threshold_days', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('critical_threshold_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop escalation_preferences table
    op.drop_table('escalation_preferences')

    # Drop escalation_history table and indexes
    op.drop_index('ix_escalation_history_escalation_type', 'escalation_history')
    op.drop_index('ix_escalation_history_created_at', 'escalation_history')
    op.drop_index('ix_escalation_history_insight_id', 'escalation_history')
    op.drop_table('escalation_history')

    # Drop escalation tracking fields from proactive_insights
    op.drop_index('ix_proactive_insights_last_escalated_at', 'proactive_insights')
    op.drop_column('proactive_insights', 'escalation_level')
    op.drop_column('proactive_insights', 'escalation_count')
    op.drop_column('proactive_insights', 'last_escalated_at')

    # Drop internal_slack_channels from project_resource_mappings
    op.drop_column('project_resource_mappings', 'internal_slack_channels')
