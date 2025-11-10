"""
Timezone utilities for handling America/Mexico_City timezone conversions.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Tuple


# Mexico City timezone
MEXICO_CITY_TZ = ZoneInfo("America/Mexico_City")
UTC_TZ = ZoneInfo("UTC")


def get_date_boundaries_mexico_city(date_str: str) -> Tuple[datetime, datetime]:
    """
    Get start and end of day boundaries for a date in Mexico City timezone.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Tuple of (start_datetime, end_datetime) in Mexico City timezone
        - start_datetime: 00:00:00 Mexico City time
        - end_datetime: 23:59:59 Mexico City time
    """
    # Parse date
    date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Create start of day (00:00:00)
    start_datetime = datetime.combine(date, time.min, tzinfo=MEXICO_CITY_TZ)

    # Create end of day (23:59:59)
    end_datetime = datetime.combine(date, time(23, 59, 59), tzinfo=MEXICO_CITY_TZ)

    return start_datetime, end_datetime


def convert_utc_to_mexico_city(utc_datetime: datetime) -> datetime:
    """
    Convert UTC datetime to Mexico City timezone.

    Args:
        utc_datetime: Datetime in UTC (can be naive or aware)

    Returns:
        Datetime in Mexico City timezone
    """
    # Ensure datetime is timezone-aware (assume UTC if naive)
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=UTC_TZ)

    # Convert to Mexico City timezone
    return utc_datetime.astimezone(MEXICO_CITY_TZ)


def is_within_range_mexico_city(
    timestamp: datetime,
    from_date: str,
    to_date: str
) -> bool:
    """
    Check if a timestamp falls within date range in Mexico City timezone.

    Args:
        timestamp: UTC timestamp to check
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format

    Returns:
        True if timestamp is within range (inclusive)
    """
    # Get boundaries in Mexico City timezone
    start_boundary, _ = get_date_boundaries_mexico_city(from_date)
    _, end_boundary = get_date_boundaries_mexico_city(to_date)

    # Convert timestamp to Mexico City timezone
    mx_timestamp = convert_utc_to_mexico_city(timestamp)

    # Check if within range
    return start_boundary <= mx_timestamp <= end_boundary


def format_mexico_city_datetime(dt: datetime) -> str:
    """
    Format datetime in Mexico City timezone for display.

    Args:
        dt: Datetime to format

    Returns:
        Formatted string: "YYYY-MM-DD HH:MM:SS CST/CDT"
    """
    mx_dt = convert_utc_to_mexico_city(dt)
    return mx_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
