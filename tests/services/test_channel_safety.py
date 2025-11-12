"""Unit tests for ChannelSafetyValidator service."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.services.channel_safety import ChannelSafetyValidator


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
def sample_projects(db_session):
    """Create sample projects with channel configurations."""
    # Project with internal channels configured
    db_session.execute(
        text(
            """
        INSERT INTO project_resource_mappings
        (project_key, project_name, slack_channel_ids, internal_slack_channels)
        VALUES
        ('SUBS', 'Subscriptions', 'C1234567890,C0987654321', 'C1234567890'),
        ('BC', 'Black Card', 'C1111111111,C2222222222,C3333333333', 'C1111111111,C2222222222'),
        ('TEST', 'Test Project', 'C9999999999', NULL)
    """
        )
    )
    db_session.commit()
    return {
        "SUBS": {"all": ["C1234567890", "C0987654321"], "internal": ["C1234567890"]},
        "BC": {
            "all": ["C1111111111", "C2222222222", "C3333333333"],
            "internal": ["C1111111111", "C2222222222"],
        },
        "TEST": {"all": ["C9999999999"], "internal": []},
    }


def test_is_channel_safe_with_internal_channel(db_session, sample_projects):
    """Test that internal channels are marked as safe."""
    validator = ChannelSafetyValidator(db_session)

    # Test SUBS internal channel
    assert validator.is_channel_safe("C1234567890", "SUBS") is True

    # Test BC internal channels
    assert validator.is_channel_safe("C1111111111", "BC") is True
    assert validator.is_channel_safe("C2222222222", "BC") is True


def test_is_channel_safe_with_non_internal_channel(db_session, sample_projects):
    """Test that non-internal channels are marked as unsafe."""
    validator = ChannelSafetyValidator(db_session)

    # Test SUBS non-internal channel (client channel)
    assert validator.is_channel_safe("C0987654321", "SUBS") is False

    # Test BC non-internal channel
    assert validator.is_channel_safe("C3333333333", "BC") is False


def test_is_channel_safe_with_no_internal_channels_configured(
    db_session, sample_projects
):
    """Test that channels are unsafe when no internal channels are configured."""
    validator = ChannelSafetyValidator(db_session)

    # TEST project has no internal channels configured
    assert validator.is_channel_safe("C9999999999", "TEST") is False


def test_is_channel_safe_with_unknown_channel(db_session, sample_projects):
    """Test that unknown channels are marked as unsafe."""
    validator = ChannelSafetyValidator(db_session)

    # Unknown channel ID
    assert validator.is_channel_safe("C0000000000", "SUBS") is False
    assert validator.is_channel_safe("INVALID", "BC") is False


def test_is_channel_safe_with_empty_channel_id(db_session, sample_projects):
    """Test that empty channel IDs are marked as unsafe."""
    validator = ChannelSafetyValidator(db_session)

    assert validator.is_channel_safe("", "SUBS") is False
    assert validator.is_channel_safe(None, "SUBS") is False


def test_is_channel_safe_without_project_key(db_session, sample_projects):
    """Test validation without specifying a project key (checks all projects)."""
    validator = ChannelSafetyValidator(db_session)

    # Channel that's internal in SUBS
    assert validator.is_channel_safe("C1234567890") is True

    # Channel that's internal in BC
    assert validator.is_channel_safe("C1111111111") is True

    # Channel that's not internal anywhere
    assert validator.is_channel_safe("C0987654321") is False


def test_get_safe_channels_for_project(db_session, sample_projects):
    """Test getting list of safe channels for a project."""
    validator = ChannelSafetyValidator(db_session)

    # SUBS should have 1 internal channel
    subs_channels = validator.get_safe_channels_for_project("SUBS")
    assert len(subs_channels) == 1
    assert "C1234567890" in subs_channels

    # BC should have 2 internal channels
    bc_channels = validator.get_safe_channels_for_project("BC")
    assert len(bc_channels) == 2
    assert "C1111111111" in bc_channels
    assert "C2222222222" in bc_channels

    # TEST should have 0 internal channels
    test_channels = validator.get_safe_channels_for_project("TEST")
    assert len(test_channels) == 0


def test_get_safe_channels_for_nonexistent_project(db_session):
    """Test getting safe channels for a project that doesn't exist."""
    validator = ChannelSafetyValidator(db_session)

    channels = validator.get_safe_channels_for_project("NONEXISTENT")
    assert len(channels) == 0


def test_validate_and_filter_channels(db_session, sample_projects):
    """Test filtering a list of channels to only safe ones."""
    validator = ChannelSafetyValidator(db_session)

    # Mix of safe and unsafe channels for SUBS
    channels = ["C1234567890", "C0987654321", "C0000000000"]
    safe = validator.validate_and_filter_channels(channels, "SUBS")

    assert len(safe) == 1
    assert "C1234567890" in safe
    assert "C0987654321" not in safe  # Client channel filtered out
    assert "C0000000000" not in safe  # Unknown channel filtered out


def test_validate_and_filter_channels_all_safe(db_session, sample_projects):
    """Test filtering when all channels are safe."""
    validator = ChannelSafetyValidator(db_session)

    channels = ["C1111111111", "C2222222222"]
    safe = validator.validate_and_filter_channels(channels, "BC")

    assert len(safe) == 2
    assert "C1111111111" in safe
    assert "C2222222222" in safe


def test_validate_and_filter_channels_none_safe(db_session, sample_projects):
    """Test filtering when no channels are safe."""
    validator = ChannelSafetyValidator(db_session)

    # All channels are non-internal
    channels = ["C0987654321", "C3333333333", "C0000000000"]
    safe = validator.validate_and_filter_channels(channels, "SUBS")

    assert len(safe) == 0


def test_validate_and_filter_channels_empty_list(db_session):
    """Test filtering an empty channel list."""
    validator = ChannelSafetyValidator(db_session)

    safe = validator.validate_and_filter_channels([], "SUBS")
    assert len(safe) == 0


def test_cache_mechanism(db_session, sample_projects):
    """Test that caching works correctly."""
    validator = ChannelSafetyValidator(db_session)

    # First call - should populate cache
    assert validator.is_channel_safe("C1234567890") is True
    assert validator._internal_channels_cache is not None

    # Cache should contain the channel
    assert "C1234567890" in validator._internal_channels_cache

    # Second call - should use cache
    assert validator.is_channel_safe("C1234567890") is True


def test_clear_cache(db_session, sample_projects):
    """Test that cache clearing works correctly."""
    validator = ChannelSafetyValidator(db_session)

    # Populate cache
    validator.is_channel_safe("C1234567890")
    assert validator._internal_channels_cache is not None

    # Clear cache
    validator.clear_cache()
    assert validator._internal_channels_cache is None

    # Next call should repopulate cache
    validator.is_channel_safe("C1234567890")
    assert validator._internal_channels_cache is not None


def test_get_channel_safety_report_safe_channel(db_session, sample_projects):
    """Test safety report for a safe channel."""
    validator = ChannelSafetyValidator(db_session)

    report = validator.get_channel_safety_report("C1234567890")

    assert report["channel_id"] == "C1234567890"
    assert report["is_safe"] is True
    assert report["status"] == "safe"
    assert "SUBS" in report["safe_for_projects"]
    assert "message" in report


def test_get_channel_safety_report_unsafe_channel(db_session, sample_projects):
    """Test safety report for an unsafe channel."""
    validator = ChannelSafetyValidator(db_session)

    report = validator.get_channel_safety_report("C0987654321")

    assert report["channel_id"] == "C0987654321"
    assert report["is_safe"] is False
    assert report["status"] == "unsafe"
    assert len(report["safe_for_projects"]) == 0
    assert "NOT marked as internal" in report["message"]


def test_get_channel_safety_report_multi_project_channel(db_session, sample_projects):
    """Test safety report for a channel that's internal in multiple projects."""
    # Add a channel that's internal in both projects
    db_session.execute(
        text(
            """
        INSERT INTO project_resource_mappings
        (project_key, project_name, slack_channel_ids, internal_slack_channels)
        VALUES ('SHARED', 'Shared Project', 'C5555555555', 'C5555555555')
    """
        )
    )
    db_session.commit()

    # Update SUBS to also have this channel as internal
    db_session.execute(
        text(
            """
        UPDATE project_resource_mappings
        SET internal_slack_channels = 'C1234567890,C5555555555'
        WHERE project_key = 'SUBS'
    """
        )
    )
    db_session.commit()

    validator = ChannelSafetyValidator(db_session)
    report = validator.get_channel_safety_report("C5555555555")

    assert report["is_safe"] is True
    assert len(report["safe_for_projects"]) == 2
    assert "SUBS" in report["safe_for_projects"]
    assert "SHARED" in report["safe_for_projects"]


def test_fail_safe_behavior_on_db_error(db_session):
    """Test that validator fails safe (rejects) on database errors."""
    # Close the session to simulate a database error
    db_session.close()

    validator = ChannelSafetyValidator(db_session)

    # Should return False (unsafe) on error
    result = validator.is_channel_safe("C1234567890", "SUBS")
    assert result is False


def test_whitespace_handling_in_channel_ids(db_session):
    """Test that whitespace in channel IDs is handled correctly."""
    # Insert project with whitespace in channel list
    db_session.execute(
        text(
            """
        INSERT INTO project_resource_mappings
        (project_key, project_name, slack_channel_ids, internal_slack_channels)
        VALUES ('WS', 'Whitespace Test', 'C1111111111, C2222222222 ,  C3333333333  ',
                'C1111111111 , C2222222222')
    """
        )
    )
    db_session.commit()

    validator = ChannelSafetyValidator(db_session)

    # Should handle whitespace correctly
    assert validator.is_channel_safe("C1111111111", "WS") is True
    assert validator.is_channel_safe("C2222222222", "WS") is True
    assert validator.is_channel_safe("C3333333333", "WS") is False
