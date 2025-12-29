"""Datetime utilities for persistence layer."""

from datetime import datetime, timezone


def normalize_to_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC and timezone-aware.

    SQLite stores datetimes without timezone info. This function:
    - Adds UTC timezone to naive datetimes (treating them as UTC).
    - Converts timezone-aware datetimes to UTC.

    Args:
        dt: datetime to process

    Returns:
        timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
