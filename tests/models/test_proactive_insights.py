"""Unit tests for proactive insights models."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import (
    Base,
    ProactiveInsight,
    User,
    UserNotificationPreferences,
    MeetingMetadata,
)


@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id=1,
        email="test@example.com",
        name="Test User",
        google_id="test-google-id-123",
        is_active=True,
        slack_user_id="U12345",
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_proactive_insight_creation(db_session, test_user):
    """Test creating a proactive insight."""
    insight = ProactiveInsight(
        id="test-insight-1",
        user_id=test_user.id,
        project_key="TEST",
        insight_type="stale_pr",
        title="Test Insight",
        description="This is a test insight",
        severity="warning",
        metadata_json={"pr_number": 123, "days_open": 5},
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(insight)
    db_session.commit()

    # Query it back
    retrieved = (
        db_session.query(ProactiveInsight).filter_by(id="test-insight-1").first()
    )
    assert retrieved is not None
    assert retrieved.title == "Test Insight"
    assert retrieved.severity == "warning"
    assert retrieved.metadata_json["pr_number"] == 123
    assert retrieved.dismissed_at is None


def test_proactive_insight_to_dict(db_session, test_user):
    """Test ProactiveInsight to_dict method."""
    insight = ProactiveInsight(
        id="test-insight-2",
        user_id=test_user.id,
        project_key="TEST",
        insight_type="budget_alert",
        title="Budget Alert",
        description="Budget exceeded",
        severity="critical",
        metadata_json={"budget_used_pct": 95.5},
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(insight)
    db_session.commit()

    # Test to_dict
    data = insight.to_dict()
    assert data["id"] == "test-insight-2"
    assert data["insight_type"] == "budget_alert"
    assert data["severity"] == "critical"
    assert "metadata" in data  # Should use 'metadata' key (not insight_metadata)
    assert data["metadata"]["budget_used_pct"] == 95.5


def test_user_notification_preferences_creation(db_session, test_user):
    """Test creating user notification preferences."""
    prefs = UserNotificationPreferences(
        user_id=test_user.id,
        daily_brief_slack=True,
        daily_brief_email=False,
        enable_stale_pr_alerts=True,
        enable_budget_alerts=True,
        daily_brief_time="09:00",
        timezone="America/New_York",
    )

    db_session.add(prefs)
    db_session.commit()

    # Query it back
    retrieved = (
        db_session.query(UserNotificationPreferences)
        .filter_by(user_id=test_user.id)
        .first()
    )
    assert retrieved is not None
    assert retrieved.daily_brief_slack is True
    assert retrieved.daily_brief_email is False
    assert retrieved.timezone == "America/New_York"


def test_user_notification_preferences_to_dict(db_session, test_user):
    """Test UserNotificationPreferences to_dict method."""
    prefs = UserNotificationPreferences(
        user_id=test_user.id,
        daily_brief_slack=False,
        daily_brief_email=True,
        enable_stale_pr_alerts=False,
        enable_budget_alerts=True,
        daily_brief_time="10:00",
        timezone="UTC",
    )

    db_session.add(prefs)
    db_session.commit()

    # Test to_dict
    data = prefs.to_dict()
    assert data["daily_brief_slack"] is False
    assert data["daily_brief_email"] is True
    assert data["enable_stale_pr_alerts"] is False
    assert data["daily_brief_time"] == "10:00"


def test_meeting_metadata_creation(db_session):
    """Test creating meeting metadata."""
    metadata = MeetingMetadata(
        meeting_title="Sprint Planning",
        normalized_title="sprint planning",
        meeting_type="planning",
        project_key="TEST",
        recurrence_pattern="weekly",
        last_occurrence=datetime.now(timezone.utc),
        participants=["user1@example.com", "user2@example.com"],
    )

    db_session.add(metadata)
    db_session.commit()

    # Query it back
    retrieved = (
        db_session.query(MeetingMetadata)
        .filter_by(meeting_title="Sprint Planning")
        .first()
    )
    assert retrieved is not None
    assert retrieved.meeting_title == "Sprint Planning"
    assert retrieved.normalized_title == "sprint planning"
    assert retrieved.meeting_type == "planning"
    assert len(retrieved.participants) == 2


def test_meeting_metadata_normalize_title():
    """Test MeetingMetadata.normalize_title() static method."""
    from src.models import MeetingMetadata

    # Note: normalize_title removes dates (YYYY-MM-DD format) but keeps year-only
    result = MeetingMetadata.normalize_title("Sprint Planning - Q1 2024")
    assert result == "sprint planning - q1 2024" or result == "sprint planning - q1"

    assert MeetingMetadata.normalize_title("Daily Standup (Team A)").startswith(
        "daily standup"
    )

    # Times are removed
    assert "11:00" not in MeetingMetadata.normalize_title("Meeting 11:00 AM")


def test_meeting_metadata_detect_meeting_type():
    """Test MeetingMetadata.detect_meeting_type() static method."""
    from src.models import MeetingMetadata

    assert MeetingMetadata.detect_meeting_type("Daily Standup") == "standup"
    assert MeetingMetadata.detect_meeting_type("Sprint Planning") == "planning"
    # Note: "review" maps to "client", not "retrospective"
    assert MeetingMetadata.detect_meeting_type("Sprint Review") == "client"
    assert MeetingMetadata.detect_meeting_type("Weekly Sync") == "weekly_sync"
    assert MeetingMetadata.detect_meeting_type("Random Meeting") == "other"


def test_insight_dismissal(db_session, test_user):
    """Test dismissing an insight."""
    insight = ProactiveInsight(
        id="test-insight-3",
        user_id=test_user.id,
        project_key="TEST",
        insight_type="stale_pr",
        title="PR Needs Review",
        description="PR #123 needs review",
        severity="info",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(insight)
    db_session.commit()

    # Dismiss it
    now = datetime.now(timezone.utc)
    insight.dismissed_at = now
    db_session.commit()

    # Verify
    retrieved = (
        db_session.query(ProactiveInsight).filter_by(id="test-insight-3").first()
    )
    assert retrieved.dismissed_at is not None
    # SQLite may strip timezone info, just check it's not None
    assert isinstance(retrieved.dismissed_at, datetime)


def test_insight_action_taken(db_session, test_user):
    """Test marking an insight as acted upon."""
    insight = ProactiveInsight(
        id="test-insight-4",
        user_id=test_user.id,
        project_key="TEST",
        insight_type="budget_alert",
        title="Budget Alert",
        description="Budget exceeded",
        severity="warning",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(insight)
    db_session.commit()

    # Mark as acted on
    now = datetime.now(timezone.utc)
    insight.acted_on_at = now
    insight.action_taken = "created_ticket"
    db_session.commit()

    # Verify
    retrieved = (
        db_session.query(ProactiveInsight).filter_by(id="test-insight-4").first()
    )
    assert retrieved.acted_on_at is not None
    assert retrieved.action_taken == "created_ticket"


def test_insight_delivery_tracking(db_session, test_user):
    """Test tracking insight delivery via Slack and Email."""
    insight = ProactiveInsight(
        id="test-insight-5",
        user_id=test_user.id,
        project_key="TEST",
        insight_type="stale_pr",
        title="PR Needs Review",
        description="PR #456 needs review",
        severity="info",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(insight)
    db_session.commit()

    # Mark as delivered via Slack
    slack_time = datetime.now(timezone.utc)
    insight.delivered_via_slack = slack_time
    db_session.commit()

    # Mark as delivered via Email later
    email_time = datetime.now(timezone.utc)
    insight.delivered_via_email = email_time
    db_session.commit()

    # Verify
    retrieved = (
        db_session.query(ProactiveInsight).filter_by(id="test-insight-5").first()
    )
    assert retrieved.delivered_via_slack is not None
    assert retrieved.delivered_via_email is not None
