"""
Timezone utilities for handling UTC storage and display conversion.
Uses Python's built-in zoneinfo (Python 3.9+) for maximum compatibility.
"""

from datetime import datetime, timezone
from typing import Optional

# Try to import zoneinfo, fall back to backports.zoneinfo if not available
try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        raise ImportError(
            "This application requires Python 3.9+ with zoneinfo or backports.zoneinfo package"
        )


# Common timezone mappings from string names to IANA timezone identifiers
TIMEZONE_CHOICES = [
    ("UTC", "UTC"),
    ("US/Eastern", "America/New_York"),
    ("US/Central", "America/Chicago"),
    ("US/Mountain", "America/Denver"),
    ("US/Pacific", "America/Los_Angeles"),
    ("Europe/London", "Europe/London"),
    ("Europe/Dublin", "Europe/Dublin"),
    ("Europe/Paris", "Europe/Paris"),
    ("Europe/Berlin", "Europe/Berlin"),
    ("Australia/Sydney", "Australia/Sydney"),
    ("Asia/Kolkata", "Asia/Kolkata"),  # India Standard Time
    ("Asia/Tokyo", "Asia/Tokyo"),
]

# Map legacy timezone strings to IANA identifiers
LEGACY_TIMEZONE_MAP = {
    "UTC": "UTC",
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "Europe/London": "Europe/London",
    "Europe/Dublin": "Europe/Dublin",
    "Europe/Paris": "Europe/Paris",
    "Europe/Berlin": "Europe/Berlin",
    "Australia/Sydney": "Australia/Sydney",
}


def get_utc_offset_minutes(timezone_name: str, dt: Optional[datetime] = None) -> int:
    """
    Get UTC offset in minutes for a timezone at a specific datetime.

    Args:
        timezone_name: IANA timezone identifier (e.g., 'America/New_York')
        dt: Datetime to check offset for (defaults to now)

    Returns:
        UTC offset in minutes (positive for east of UTC, negative for west)
    """
    if dt is None:
        dt = datetime.now()

    # Handle legacy timezone names
    if timezone_name in LEGACY_TIMEZONE_MAP:
        timezone_name = LEGACY_TIMEZONE_MAP[timezone_name]

    try:
        tz = ZoneInfo(timezone_name)
        # Make datetime timezone-aware in the target timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)

        offset = dt.utcoffset()
        return int(offset.total_seconds() / 60) if offset else 0
    except Exception:
        # Fallback to UTC if timezone is invalid
        return 0


def utc_to_local(utc_dt: datetime, timezone_name: str) -> datetime:
    """
    Convert UTC datetime to local timezone.

    Args:
        utc_dt: UTC datetime (should be timezone-aware or will be treated as UTC)
        timezone_name: IANA timezone identifier

    Returns:
        Datetime in local timezone
    """
    # Handle legacy timezone names
    if timezone_name in LEGACY_TIMEZONE_MAP:
        timezone_name = LEGACY_TIMEZONE_MAP[timezone_name]

    try:
        # Ensure UTC datetime is timezone-aware
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        elif utc_dt.tzinfo != timezone.utc:
            utc_dt = utc_dt.astimezone(timezone.utc)

        # Convert to target timezone
        target_tz = ZoneInfo(timezone_name)
        return utc_dt.astimezone(target_tz)
    except Exception:
        # Fallback: return as-is if conversion fails
        return utc_dt


def local_to_utc(local_dt: datetime, timezone_name: str) -> datetime:
    """
    Convert local datetime to UTC.

    Args:
        local_dt: Local datetime (timezone-naive, interpreted in given timezone)
        timezone_name: IANA timezone identifier for the local datetime

    Returns:
        UTC datetime
    """
    # Handle legacy timezone names
    if timezone_name in LEGACY_TIMEZONE_MAP:
        timezone_name = LEGACY_TIMEZONE_MAP[timezone_name]

    try:
        # If datetime is already timezone-aware, convert it
        if local_dt.tzinfo is not None:
            return local_dt.astimezone(timezone.utc)

        # Make timezone-aware in local timezone, then convert to UTC
        local_tz = ZoneInfo(timezone_name)
        local_aware = local_dt.replace(tzinfo=local_tz)
        return local_aware.astimezone(timezone.utc)
    except Exception:
        # Fallback: treat as UTC if conversion fails
        if local_dt.tzinfo is None:
            return local_dt.replace(tzinfo=timezone.utc)
        return local_dt


def format_datetime_with_timezone(
    dt: datetime, timezone_name: str, format_str: str = "%Y-%m-%d %H:%M"
) -> str:
    """
    Format datetime in local timezone with timezone abbreviation.

    Args:
        dt: UTC datetime
        timezone_name: Target timezone name
        format_str: strftime format string

    Returns:
        Formatted datetime string with timezone abbreviation
    """
    local_dt = utc_to_local(dt, timezone_name)

    # Get timezone abbreviation (EST, PST, etc.)
    try:
        tz_abbrev = local_dt.strftime("%Z")
        if not tz_abbrev:
            # Fallback: show UTC offset instead
            offset_mins = get_utc_offset_minutes(timezone_name, local_dt)
            hours, mins = divmod(abs(offset_mins), 60)
            sign = "+" if offset_mins >= 0 else "-"
            tz_abbrev = f"UTC{sign}{hours:02d}:{mins:02d}"
    except Exception:
        tz_abbrev = "UTC"

    formatted_time = local_dt.strftime(format_str)
    return f"{formatted_time} {tz_abbrev}"


def get_timezone_display_name(timezone_name: str) -> str:
    """
    Get human-readable display name for timezone.

    Args:
        timezone_name: IANA timezone identifier

    Returns:
        Display name for the timezone
    """
    # Handle legacy names
    if timezone_name in LEGACY_TIMEZONE_MAP:
        timezone_name = LEGACY_TIMEZONE_MAP[timezone_name]

    display_names = {
        "UTC": "UTC",
        "America/New_York": "US Eastern",
        "America/Chicago": "US Central",
        "America/Denver": "US Mountain",
        "America/Los_Angeles": "US Pacific",
        "America/Anchorage": "US Alaska",
        "Pacific/Honolulu": "US Hawaii",
        "America/Toronto": "Canada Eastern",
        "America/Vancouver": "Canada Pacific",
        "America/Mexico_City": "Mexico City",
        "America/Buenos_Aires": "Argentina",
        "America/Sao_Paulo": "Brazil (São Paulo)",
        "Europe/London": "UK/London",
        "Europe/Dublin": "Ireland/Dublin",
        "Europe/Paris": "France/Paris",
        "Europe/Berlin": "Germany/Berlin",
        "Europe/Rome": "Italy/Rome",
        "Europe/Madrid": "Spain/Madrid",
        "Europe/Amsterdam": "Netherlands",
        "Europe/Brussels": "Belgium",
        "Europe/Zurich": "Switzerland",
        "Europe/Stockholm": "Sweden",
        "Europe/Oslo": "Norway",
        "Europe/Copenhagen": "Denmark",
        "Europe/Helsinki": "Finland",
        "Europe/Athens": "Greece",
        "Europe/Moscow": "Russia/Moscow",
        "Africa/Cairo": "Egypt/Cairo",
        "Africa/Johannesburg": "South Africa",
        "Africa/Lagos": "Nigeria/Lagos",
        "Asia/Dubai": "UAE/Dubai",
        "Asia/Jerusalem": "Israel",
        "Asia/Kolkata": "India",
        "Asia/Bangkok": "Thailand",
        "Asia/Singapore": "Singapore",
        "Asia/Hong_Kong": "Hong Kong",
        "Asia/Shanghai": "China/Shanghai",
        "Asia/Tokyo": "Japan/Tokyo",
        "Asia/Seoul": "South Korea",
        "Australia/Sydney": "Australia/Sydney",
        "Australia/Melbourne": "Australia/Melbourne",
        "Australia/Perth": "Australia/Perth",
        "Pacific/Auckland": "New Zealand",
    }

    return display_names.get(timezone_name, timezone_name)


def get_timezone_display_with_offset(timezone_name: str) -> str:
    """
    Get timezone display name with current UTC offset.

    Args:
        timezone_name: IANA timezone identifier

    Returns:
        Display name with UTC offset (e.g., "US Eastern (UTC-05:00)")
    """
    display_name = get_timezone_display_name(timezone_name)

    # Get current offset
    offset_minutes = get_utc_offset_minutes(timezone_name)
    hours, mins = divmod(abs(offset_minutes), 60)
    sign = "+" if offset_minutes >= 0 else "-"
    offset_str = f"UTC{sign}{hours:02d}:{mins:02d}"

    return f"{display_name} ({offset_str})"


def now_utc() -> datetime:
    """
    Get current datetime in UTC.

    Returns:
        Current UTC datetime (timezone-aware)
    """
    return datetime.now(timezone.utc)


def migrate_legacy_timezone(legacy_tz: str) -> str:
    """
    Migrate legacy timezone string to IANA identifier.

    Args:
        legacy_tz: Legacy timezone string

    Returns:
        IANA timezone identifier
    """
    return LEGACY_TIMEZONE_MAP.get(legacy_tz, "UTC")


def get_today_in_timezone(timezone_name: str = "UTC"):
    """
    Get today's date in a specific timezone.

    Args:
        timezone_name: IANA timezone identifier (defaults to UTC)

    Returns:
        date object representing today in the specified timezone
    """
    # Handle legacy timezone names
    if timezone_name in LEGACY_TIMEZONE_MAP:
        timezone_name = LEGACY_TIMEZONE_MAP[timezone_name]

    try:
        # Get current time in the target timezone
        target_tz = ZoneInfo(timezone_name)
        now_in_tz = datetime.now(target_tz)
        return now_in_tz.date()
    except Exception:
        # Fallback to UTC if timezone is invalid
        return datetime.now(timezone.utc).date()
