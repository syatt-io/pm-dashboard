"""Timezone utilities for consistent EST/EDT formatting across the application."""

from datetime import datetime, tzinfo
from typing import Optional
import pytz


# Define EST timezone
EST = pytz.timezone("America/New_York")


def to_est(dt: datetime) -> datetime:
    """
    Convert a datetime to EST/EDT timezone.

    Args:
        dt: Datetime to convert (can be naive or timezone-aware)

    Returns:
        Datetime in EST/EDT timezone
    """
    if dt is None:
        return None

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    # Convert to EST
    return dt.astimezone(EST)


def format_est_datetime(dt: datetime, include_timezone: bool = True) -> str:
    """
    Format datetime as EST/EDT with consistent format.

    Args:
        dt: Datetime to format
        include_timezone: Whether to include timezone abbreviation (EST/EDT)

    Returns:
        Formatted string like "January 15, 2025 at 2:30 PM EST"
    """
    if dt is None:
        return "N/A"

    est_dt = to_est(dt)

    # Format: "January 15, 2025 at 2:30 PM"
    formatted = est_dt.strftime("%B %d, %Y at %I:%M %p")

    if include_timezone:
        # Get timezone abbreviation (EST or EDT depending on daylight saving)
        tz_abbr = est_dt.strftime("%Z")
        formatted += f" {tz_abbr}"

    return formatted


def format_est_date(dt: datetime) -> str:
    """
    Format date as EST/EDT with consistent format (no time).

    Args:
        dt: Datetime to format

    Returns:
        Formatted string like "January 15, 2025"
    """
    if dt is None:
        return "N/A"

    est_dt = to_est(dt)
    return est_dt.strftime("%B %d, %Y")


def format_est_short(dt: datetime) -> str:
    """
    Format datetime as EST/EDT with short format.

    Args:
        dt: Datetime to format

    Returns:
        Formatted string like "Jan 15, 2:30 PM EST"
    """
    if dt is None:
        return "N/A"

    est_dt = to_est(dt)
    tz_abbr = est_dt.strftime("%Z")
    return est_dt.strftime(f"%b %d, %I:%M %p {tz_abbr}")


def now_est() -> datetime:
    """
    Get current time in EST/EDT timezone.

    Returns:
        Current datetime in EST/EDT
    """
    return datetime.now(EST)


def format_est_time_only(dt: datetime) -> str:
    """
    Format time only as EST/EDT.

    Args:
        dt: Datetime to format

    Returns:
        Formatted string like "2:30 PM EST"
    """
    if dt is None:
        return "N/A"

    est_dt = to_est(dt)
    tz_abbr = est_dt.strftime("%Z")
    return est_dt.strftime(f"%I:%M %p {tz_abbr}")
