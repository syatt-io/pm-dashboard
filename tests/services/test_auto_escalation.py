"""Unit tests for AutoEscalationService."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models.user import User
from src.models.proactive_insight import ProactiveInsight
from src.models.escalation import EscalationHistory, EscalationPreferences
from src.services.auto_escalation import AutoEscalationService


@pytest.fixture
def db_engine():
    """Create in-memory database engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    # Create project_resource_mappings table (not in Base.metadata)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS project_resource_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_key TEXT NOT NULL UNIQUE,
                project_name TEXT NOT NULL,
                slack_channel_ids TEXT,
                internal_slack_channels TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.commit()

    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user with Slack ID."""
    user = User(
        id=1,
        email="test@example.com",
        name="Test User",
        google_id="google_test_123",
        slack_user_id="U123456789",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_project(db_session):
    """Create a sample project with internal channels."""
    db_session.execute(
        text(
            """
        INSERT INTO project_resource_mappings
        (project_key, project_name, slack_channel_ids, internal_slack_channels)
        VALUES ('SUBS', 'Subscriptions', 'C1234567890,C0987654321', 'C1234567890')
    """
        )
    )
    db_session.commit()
    return {"key": "SUBS", "internal_channel": "C1234567890"}


@pytest.fixture
def user_notification_prefs(db_session, sample_user):
    """Create user notification preferences (required for escalations)."""
    from src.models import UserNotificationPreferences

    prefs = UserNotificationPreferences(
        user_id=sample_user.id,
        enable_escalations=True,  # Required for auto-escalation to work
    )
    db_session.add(prefs)
    db_session.commit()
    return prefs


@pytest.fixture
def escalation_prefs(db_session, sample_user, user_notification_prefs):
    """Create escalation preferences for user."""
    prefs = EscalationPreferences(
        user_id=sample_user.id,
        enable_auto_escalation=True,
        enable_dm_escalation=True,
        enable_channel_escalation=True,
        enable_github_escalation=True,
        dm_threshold_days=3,
        channel_threshold_days=5,
        critical_threshold_days=7,
    )
    db_session.add(prefs)
    db_session.commit()
    return prefs


@pytest.fixture
def mock_slack_client():
    """Create mock Slack WebClient."""
    mock = Mock()
    mock.chat_postMessage = Mock(return_value={"ok": True, "ts": "1234567890.123456"})
    return mock


@pytest.fixture
def mock_github_client():
    """Create mock GitHubClient."""
    mock = Mock()
    mock.add_pr_comment = Mock()
    return mock


def create_insight(
    db_session,
    user_id,
    days_old,
    project_key="SUBS",
    insight_type="stale_pr",
    escalation_level=0,
    last_escalated_at=None,
    pr_url="https://github.com/org/repo/pull/123",
):
    """Helper to create a test insight."""
    created_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    insight = ProactiveInsight(
        id=f"insight-{days_old}",
        user_id=user_id,
        project_key=project_key,
        insight_type=insight_type,
        title=f"Stale PR: Test PR #{days_old}",
        description=f"This PR has been open for {days_old} days",
        severity="warning",
        metadata_json={"pr_url": pr_url, "project_key": project_key},
        created_at=created_at,
        escalation_level=escalation_level,
        escalation_count=0,
        last_escalated_at=last_escalated_at,
    )
    db_session.add(insight)
    db_session.commit()
    return insight


def test_determine_escalation_level(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test escalation level determination based on age."""
    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    # 2 days old - no escalation
    assert service._determine_escalation_level(2, escalation_prefs) == 0

    # 3 days old - DM escalation
    assert service._determine_escalation_level(3, escalation_prefs) == 1

    # 5 days old - Channel escalation
    assert service._determine_escalation_level(5, escalation_prefs) == 2

    # 7 days old - Critical escalation
    assert service._determine_escalation_level(7, escalation_prefs) == 3

    # 10 days old - Still critical (level 3 is max)
    assert service._determine_escalation_level(10, escalation_prefs) == 3


def test_get_active_insights(
    db_session, sample_user, mock_slack_client, mock_github_client
):
    """Test fetching active insights."""
    # Create insights with different states
    active1 = create_insight(db_session, sample_user.id, 3)
    active2 = create_insight(db_session, sample_user.id, 5)

    # Dismissed insight
    dismissed = create_insight(db_session, sample_user.id, 7)
    dismissed.dismissed_at = datetime.now(timezone.utc)
    db_session.commit()

    # Acted-on insight
    acted_on = create_insight(db_session, sample_user.id, 8)
    acted_on.acted_on_at = datetime.now(timezone.utc)
    db_session.commit()

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    active_insights = service._get_active_insights()

    # Should only return non-dismissed, non-acted-on insights
    assert len(active_insights) == 2
    insight_ids = [i.id for i in active_insights]
    assert active1.id in insight_ids
    assert active2.id in insight_ids
    assert dismissed.id not in insight_ids
    assert acted_on.id not in insight_ids


def test_skip_insight_no_preferences(
    db_session, sample_user, mock_slack_client, mock_github_client
):
    """Test that insight is skipped when user has no UserNotificationPreferences."""
    insight = create_insight(db_session, sample_user.id, 5)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is False
    assert (
        result["skipped_reason"] == "disabled"
    )  # Changed from "no_prefs" to match new behavior
    mock_slack_client.chat_postMessage.assert_not_called()


def test_skip_insight_auto_escalation_disabled(
    db_session,
    sample_user,
    user_notification_prefs,
    escalation_prefs,
    mock_slack_client,
    mock_github_client,
):
    """Test that insight is skipped when auto-escalation is disabled."""
    # Disable auto-escalation via user notification preferences
    user_notification_prefs.enable_escalations = False
    db_session.commit()

    insight = create_insight(db_session, sample_user.id, 5)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is False
    assert result["skipped_reason"] == "disabled"
    mock_slack_client.chat_postMessage.assert_not_called()


def test_skip_insight_not_ready_for_escalation(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test that insight is skipped when not old enough."""
    # 2 days old - threshold is 3 days for DM
    insight = create_insight(db_session, sample_user.id, 2)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is False
    assert result.get("skipped_reason") is None
    mock_slack_client.chat_postMessage.assert_not_called()


def test_skip_insight_already_escalated_to_level(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test that insight is skipped if already escalated to target level."""
    # 5 days old = level 2, but already at level 2
    insight = create_insight(db_session, sample_user.id, 5, escalation_level=2)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is False
    mock_slack_client.chat_postMessage.assert_not_called()


def test_skip_insight_rate_limited(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test that insight is skipped if escalated within last 24 hours."""
    # Escalated 12 hours ago
    last_escalated = datetime.now(timezone.utc) - timedelta(hours=12)
    insight = create_insight(
        db_session,
        sample_user.id,
        5,
        escalation_level=1,  # Was at level 1
        last_escalated_at=last_escalated,
    )

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is False
    mock_slack_client.chat_postMessage.assert_not_called()


def test_send_dm_escalation_success(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test successful DM escalation."""
    # 3 days old = level 1 (DM)
    insight = create_insight(db_session, sample_user.id, 3)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is True
    assert result["dm_sent"] == 1
    mock_slack_client.chat_postMessage.assert_called_once()

    # Check DM was sent to correct user
    call_args = mock_slack_client.chat_postMessage.call_args
    assert call_args.kwargs["channel"] == sample_user.slack_user_id
    assert "REMINDER" in call_args.kwargs["text"]

    # Check escalation history recorded
    history = (
        db_session.query(EscalationHistory).filter_by(insight_id=insight.id).first()
    )
    assert history is not None
    assert history.escalation_type == "dm"
    assert history.escalation_level == 1
    assert history.success is True


def test_send_channel_escalation_success(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test successful channel escalation."""
    # 5 days old = level 2 (Channel)
    insight = create_insight(db_session, sample_user.id, 5)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is True
    assert result["dm_sent"] == 1  # Also sends DM
    assert result["channel_posts"] == 1

    # Should be called twice (once for DM, once for channel)
    assert mock_slack_client.chat_postMessage.call_count == 2

    # Check channel message (last call should be to channel)
    call_args = mock_slack_client.chat_postMessage.call_args
    assert call_args.kwargs["channel"] == sample_project["internal_channel"]
    assert "URGENT" in call_args.kwargs["text"]
    assert f"<@{sample_user.slack_user_id}>" in call_args.kwargs["text"]

    # Check escalation history recorded
    history = (
        db_session.query(EscalationHistory)
        .filter_by(insight_id=insight.id, escalation_type="channel")
        .first()
    )
    assert history is not None
    assert history.success is True


def test_send_github_escalation_success(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test successful GitHub comment escalation."""
    # 7 days old = level 3 (Critical - includes GitHub)
    pr_url = "https://github.com/org/repo/pull/123"
    insight = create_insight(db_session, sample_user.id, 7, pr_url=pr_url)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is True
    assert result["dm_sent"] == 1
    assert result["channel_posts"] == 1
    assert result["github_comments"] == 1
    mock_github_client.add_pr_comment.assert_called_once()

    # Check comment was added to correct PR
    call_args = mock_github_client.add_pr_comment.call_args
    assert call_args[0][0] == pr_url
    assert "CRITICAL" in call_args[0][1]

    # Check escalation history recorded
    history = (
        db_session.query(EscalationHistory)
        .filter_by(insight_id=insight.id, escalation_type="github_comment")
        .first()
    )
    assert history is not None
    assert history.success is True


def test_channel_escalation_no_safe_channels(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test channel escalation fails safely when no internal channels configured."""
    # 5 days old = level 2 (Channel), but no safe channels
    insight = create_insight(db_session, sample_user.id, 5, project_key="NOSAFE")

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    # Should still escalate DM but not channel
    assert result["escalated"] is True
    assert result["dm_sent"] == 1
    assert result["channel_posts"] == 0

    # DM still sent, so chat_postMessage called once (for DM only)
    assert mock_slack_client.chat_postMessage.call_count == 1
    call_args = mock_slack_client.chat_postMessage.call_args
    assert call_args.kwargs["channel"] == sample_user.slack_user_id  # DM, not channel

    # Check failure recorded in history
    history = (
        db_session.query(EscalationHistory)
        .filter_by(insight_id=insight.id, escalation_type="channel")
        .first()
    )
    assert history is not None
    assert history.success is False
    assert "No safe channels configured" in history.error_message


def test_github_escalation_no_pr_url(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test GitHub escalation fails safely when no PR URL in metadata."""
    # 7 days old = level 3, but no PR URL
    insight = create_insight(db_session, sample_user.id, 7, pr_url=None)
    insight.metadata_json = {"project_key": "SUBS"}  # No pr_url
    db_session.commit()

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    # Should still escalate DM and channel but not GitHub
    assert result["escalated"] is True
    assert result["dm_sent"] == 1
    assert result["channel_posts"] == 1
    assert result["github_comments"] == 0
    mock_github_client.add_pr_comment.assert_not_called()

    # Check failure recorded in history
    history = (
        db_session.query(EscalationHistory)
        .filter_by(insight_id=insight.id, escalation_type="github_comment")
        .first()
    )
    assert history is not None
    assert history.success is False
    assert "No PR URL found" in history.error_message


def test_escalation_respects_user_preferences_dm_disabled(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test that DM escalation is skipped when disabled in preferences."""
    # Disable DM escalation
    escalation_prefs.enable_dm_escalation = False
    db_session.commit()

    # 5 days old = level 2 (should include DM + channel)
    insight = create_insight(db_session, sample_user.id, 5)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is True
    assert result["dm_sent"] == 0  # DM disabled
    assert result["channel_posts"] == 1  # But channel still sent

    # Channel message still sent, so chat_postMessage called once (for channel only)
    assert mock_slack_client.chat_postMessage.call_count == 1
    call_args = mock_slack_client.chat_postMessage.call_args
    assert (
        call_args.kwargs["channel"] == sample_project["internal_channel"]
    )  # Channel, not DM


def test_insight_tracking_updated_after_escalation(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test that insight tracking fields are updated after escalation."""
    # 3 days old = level 1
    insight = create_insight(db_session, sample_user.id, 3)
    original_level = insight.escalation_level
    original_count = insight.escalation_count

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    result = service._process_insight_escalation(insight)

    assert result["escalated"] is True

    # Refresh insight from DB
    db_session.refresh(insight)

    assert insight.escalation_level == 1  # Updated to level 1
    assert insight.escalation_count == original_count + 1
    assert insight.last_escalated_at is not None


def test_run_escalation_check_statistics(
    db_session,
    sample_user,
    escalation_prefs,
    sample_project,
    mock_slack_client,
    mock_github_client,
):
    """Test that run_escalation_check returns correct statistics."""
    import uuid

    # Create insights at different levels with unique IDs
    insight1 = ProactiveInsight(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        project_key="SUBS",
        insight_type="stale_pr",
        title="Stale PR: Test 1",
        description="Test insight 1",
        severity="warning",
        metadata_json={
            "pr_url": "https://github.com/org/repo/pull/1",
            "project_key": "SUBS",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        escalation_level=0,
        escalation_count=0,
    )
    insight2 = ProactiveInsight(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        project_key="SUBS",
        insight_type="stale_pr",
        title="Stale PR: Test 2",
        description="Test insight 2",
        severity="warning",
        metadata_json={
            "pr_url": "https://github.com/org/repo/pull/2",
            "project_key": "SUBS",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
        escalation_level=0,
        escalation_count=0,
    )
    insight3 = ProactiveInsight(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        project_key="SUBS",
        insight_type="stale_pr",
        title="Stale PR: Test 3",
        description="Test insight 3",
        severity="warning",
        metadata_json={
            "pr_url": "https://github.com/org/repo/pull/3",
            "project_key": "SUBS",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        escalation_level=0,
        escalation_count=0,
    )
    insight4 = ProactiveInsight(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        project_key="SUBS",
        insight_type="stale_pr",
        title="Stale PR: Test 4",
        description="Test insight 4",
        severity="warning",
        metadata_json={
            "pr_url": "https://github.com/org/repo/pull/4",
            "project_key": "SUBS",
        },
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        escalation_level=1,
        escalation_count=0,
    )
    db_session.add_all([insight1, insight2, insight3, insight4])
    db_session.commit()

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    stats = service.run_escalation_check()

    assert stats["total_checked"] == 4
    assert stats["escalations_performed"] == 2  # insight1 and insight2
    assert stats["dm_sent"] == 2  # Both levels include DM
    assert stats["channel_posts"] == 1  # Only level 2
    assert stats["github_comments"] == 0  # None at level 3


def test_dm_message_format(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test DM message formatting."""
    insight = create_insight(db_session, sample_user.id, 3)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    message = service._build_dm_message(insight, 3, 1)

    assert "REMINDER" in message
    assert "3 days" in message
    assert insight.title in message
    assert insight.description in message
    assert "Escalation Level 1/3" in message


def test_channel_message_format(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test channel message formatting."""
    insight = create_insight(db_session, sample_user.id, 5)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    message = service._build_channel_message(insight, sample_user, 5, 2)

    assert "URGENT" in message
    assert f"<@{sample_user.slack_user_id}>" in message
    assert "5 days" in message
    assert insight.title in message
    assert "Escalation Level 2/3" in message


def test_github_comment_format(
    db_session, sample_user, escalation_prefs, mock_slack_client, mock_github_client
):
    """Test GitHub comment formatting."""
    insight = create_insight(db_session, sample_user.id, 7)

    service = AutoEscalationService(db_session, mock_slack_client, mock_github_client)

    comment = service._build_github_comment(insight, 7, 3)

    assert "🚨 **CRITICAL**" in comment
    assert "**7 days**" in comment
    assert insight.description in comment
    assert "Level 3/3" in comment
