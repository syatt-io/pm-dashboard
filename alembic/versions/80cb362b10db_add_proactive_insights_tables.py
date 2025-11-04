"""add_proactive_insights_tables

Revision ID: 80cb362b10db
Revises: d8101d785508
Create Date: 2025-11-04 18:40:22.481023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80cb362b10db'
down_revision: Union[str, Sequence[str], None] = 'd8101d785508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create proactive_insights table
    op.create_table(
        'proactive_insights',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('project_key', sa.String(50), nullable=True),
        sa.Column('insight_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('insight_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.Column('acted_on_at', sa.DateTime(), nullable=True),
        sa.Column('action_taken', sa.String(100), nullable=True),
        sa.Column('delivered_via_slack', sa.DateTime(), nullable=True),
        sa.Column('delivered_via_email', sa.DateTime(), nullable=True),
    )

    # Create indexes for proactive_insights
    op.create_index('ix_proactive_insights_project_key', 'proactive_insights', ['project_key'])
    op.create_index('ix_proactive_insights_insight_type', 'proactive_insights', ['insight_type'])
    op.create_index('ix_proactive_insights_created_at', 'proactive_insights', ['created_at'])

    # Create user_notification_preferences table
    op.create_table(
        'user_notification_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('daily_brief_slack', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('daily_brief_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('enable_stale_pr_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_budget_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_missing_ticket_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_anomaly_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_meeting_prep', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('daily_brief_time', sa.String(5), nullable=False, server_default='09:00'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='America/New_York'),
    )

    # Create meeting_metadata table
    op.create_table(
        'meeting_metadata',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('meeting_title', sa.String(255), nullable=False),
        sa.Column('normalized_title', sa.String(255), nullable=False),
        sa.Column('meeting_type', sa.String(50), nullable=True),
        sa.Column('project_key', sa.String(50), nullable=True),
        sa.Column('recurrence_pattern', sa.String(50), nullable=True),
        sa.Column('last_occurrence', sa.DateTime(), nullable=False),
        sa.Column('next_expected', sa.DateTime(), nullable=True),
        sa.Column('participants', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Create indexes for meeting_metadata
    op.create_index('ix_meeting_metadata_normalized_title', 'meeting_metadata', ['normalized_title'])
    op.create_index('ix_meeting_metadata_meeting_type', 'meeting_metadata', ['meeting_type'])
    op.create_index('ix_meeting_metadata_project_key', 'meeting_metadata', ['project_key'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop meeting_metadata table and indexes
    op.drop_index('ix_meeting_metadata_project_key', 'meeting_metadata')
    op.drop_index('ix_meeting_metadata_meeting_type', 'meeting_metadata')
    op.drop_index('ix_meeting_metadata_normalized_title', 'meeting_metadata')
    op.drop_table('meeting_metadata')

    # Drop user_notification_preferences table
    op.drop_table('user_notification_preferences')

    # Drop proactive_insights table and indexes
    op.drop_index('ix_proactive_insights_created_at', 'proactive_insights')
    op.drop_index('ix_proactive_insights_insight_type', 'proactive_insights')
    op.drop_index('ix_proactive_insights_project_key', 'proactive_insights')
    op.drop_table('proactive_insights')
