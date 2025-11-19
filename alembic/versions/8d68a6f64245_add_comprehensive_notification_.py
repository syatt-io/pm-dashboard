"""Add comprehensive notification preferences with opt-in defaults

Revision ID: 8d68a6f64245
Revises: 8ed38e72174e
Create Date: 2025-11-18 18:28:53.356233

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8d68a6f64245"
down_revision: Union[str, Sequence[str], None] = "8ed38e72174e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add notification preference columns with nullable=True first
    # to allow for existing data, then update defaults and set NOT NULL

    # Step 1: Add all columns as nullable
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_todo_reminders", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_urgent_notifications", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_weekly_reports", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_escalations", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_meeting_notifications", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("enable_pm_reports", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("todo_reminders_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("urgent_notifications_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("urgent_notifications_email", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("weekly_summary_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("weekly_summary_email", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("weekly_hours_reports_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("weekly_hours_reports_email", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("meeting_analysis_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("meeting_analysis_email", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("pm_reports_slack", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column("pm_reports_email", sa.Boolean(), nullable=True),
    )

    # Step 2: Set default values for existing rows (opt-in system - all False by default)
    op.execute(
        """
        UPDATE user_notification_preferences SET
            enable_todo_reminders = FALSE,
            enable_urgent_notifications = FALSE,
            enable_weekly_reports = FALSE,
            enable_escalations = FALSE,
            enable_meeting_notifications = FALSE,
            enable_pm_reports = FALSE,
            todo_reminders_slack = FALSE,
            urgent_notifications_slack = FALSE,
            urgent_notifications_email = FALSE,
            weekly_summary_slack = FALSE,
            weekly_summary_email = FALSE,
            weekly_hours_reports_slack = FALSE,
            weekly_hours_reports_email = FALSE,
            meeting_analysis_slack = FALSE,
            meeting_analysis_email = FALSE,
            pm_reports_slack = FALSE,
            pm_reports_email = FALSE
        WHERE enable_todo_reminders IS NULL
    """
    )

    # Step 3: Alter columns to NOT NULL
    op.alter_column(
        "user_notification_preferences", "enable_todo_reminders", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "enable_urgent_notifications", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "enable_weekly_reports", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "enable_escalations", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "enable_meeting_notifications", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "enable_pm_reports", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "todo_reminders_slack", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "urgent_notifications_slack", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "urgent_notifications_email", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "weekly_summary_slack", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "weekly_summary_email", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "weekly_hours_reports_slack", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "weekly_hours_reports_email", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "meeting_analysis_slack", nullable=False
    )
    op.alter_column(
        "user_notification_preferences", "meeting_analysis_email", nullable=False
    )
    op.alter_column("user_notification_preferences", "pm_reports_slack", nullable=False)
    op.alter_column("user_notification_preferences", "pm_reports_email", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("user_notification_preferences", "pm_reports_email")
    op.drop_column("user_notification_preferences", "pm_reports_slack")
    op.drop_column("user_notification_preferences", "meeting_analysis_email")
    op.drop_column("user_notification_preferences", "meeting_analysis_slack")
    op.drop_column("user_notification_preferences", "weekly_hours_reports_email")
    op.drop_column("user_notification_preferences", "weekly_hours_reports_slack")
    op.drop_column("user_notification_preferences", "weekly_summary_email")
    op.drop_column("user_notification_preferences", "weekly_summary_slack")
    op.drop_column("user_notification_preferences", "urgent_notifications_email")
    op.drop_column("user_notification_preferences", "urgent_notifications_slack")
    op.drop_column("user_notification_preferences", "todo_reminders_slack")
    op.drop_column("user_notification_preferences", "enable_pm_reports")
    op.drop_column("user_notification_preferences", "enable_meeting_notifications")
    op.drop_column("user_notification_preferences", "enable_escalations")
    op.drop_column("user_notification_preferences", "enable_weekly_reports")
    op.drop_column("user_notification_preferences", "enable_urgent_notifications")
    op.drop_column("user_notification_preferences", "enable_todo_reminders")
    op.add_column(
        "todo_items",
        sa.Column("source", sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "show_budget_tab",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "cumulative_hours",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "send_meeting_emails",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "total_hours",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "project_work_type",
            sa.VARCHAR(length=50),
            server_default=sa.text("'project-based'::character varying"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column("lead", sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("description", sa.TEXT(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("start_date", sa.DATE(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("launch_date", sa.DATE(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "weekly_meeting_day",
            sa.VARCHAR(length=20),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "retainer_hours",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.create_index(
        op.f("idx_projects_project_work_type"),
        "projects",
        ["project_work_type"],
        unique=False,
    )
    op.create_index(
        op.f("idx_project_resource_mappings_key"),
        "project_resource_mappings",
        ["project_key"],
        unique=False,
    )
    op.drop_index(
        "idx_job_executions_recent",
        table_name="job_executions",
        postgresql_using="btree",
        postgresql_ops={"started_at": "DESC"},
    )
    op.create_index(
        op.f("idx_job_executions_recent"),
        "job_executions",
        [sa.literal_column("started_at DESC")],
        unique=False,
    )
    op.create_table(
        "meeting_prep_deliveries",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "project_key", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column(
            "delivered_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "delivered_via_slack", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "delivered_via_email", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "digest_cache_id", sa.VARCHAR(length=36), autoincrement=False, nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("meeting_prep_deliveries_user_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("meeting_prep_deliveries_pkey")),
    )
    op.create_index(
        op.f("idx_meeting_prep_user_project"),
        "meeting_prep_deliveries",
        ["user_id", "project_key"],
        unique=False,
    )
    op.create_index(
        op.f("idx_meeting_prep_delivered_at"),
        "meeting_prep_deliveries",
        ["delivered_at"],
        unique=False,
    )
    op.create_table(
        "celery_taskmeta",
        sa.Column("id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "task_id", sa.VARCHAR(length=155), autoincrement=False, nullable=True
        ),
        sa.Column("status", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("result", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column(
            "date_done", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.Column("traceback", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("name", sa.VARCHAR(length=155), autoincrement=False, nullable=True),
        sa.Column("args", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column("kwargs", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column("worker", sa.VARCHAR(length=155), autoincrement=False, nullable=True),
        sa.Column("retries", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("queue", sa.VARCHAR(length=155), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("celery_taskmeta_pkey")),
        sa.UniqueConstraint(
            "task_id",
            name=op.f("celery_taskmeta_task_id_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_table(
        "slack_sessions",
        sa.Column(
            "session_id", sa.VARCHAR(length=32), autoincrement=False, nullable=False
        ),
        sa.Column("data", postgresql.BYTEA(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "expires_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("slack_sessions_pkey")),
    )
    op.create_table(
        "celery_tasksetmeta",
        sa.Column("id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "taskset_id", sa.VARCHAR(length=155), autoincrement=False, nullable=True
        ),
        sa.Column("result", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column(
            "date_done", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("celery_tasksetmeta_pkey")),
        sa.UniqueConstraint(
            "taskset_id",
            name=op.f("celery_tasksetmeta_taskset_id_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    # ### end Alembic commands ###
