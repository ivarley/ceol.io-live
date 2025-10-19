"""
Recurrence pattern utilities for session scheduling.

Handles parsing, validation, and calculation of session recurrence patterns.
"""

import json
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple
import calendar
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


# Valid weekday names
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Mapping from weekday name to ISO weekday number (Monday=1, Sunday=7)
WEEKDAY_TO_ISO = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}

# Mapping from ISO weekday to name
ISO_TO_WEEKDAY = {v: k for k, v in WEEKDAY_TO_ISO.items()}


class RecurrenceSchedule:
    """Represents one schedule pattern within a recurrence."""

    def __init__(self, schedule_dict: dict):
        """
        Initialize a RecurrenceSchedule from a dictionary.

        Args:
            schedule_dict: Dictionary containing schedule definition with keys:
                - type: "weekly" or "monthly_nth_weekday"
                - weekday: day name (e.g., "thursday")
                - start_time: time string (e.g., "19:00")
                - end_time: time string (e.g., "22:30")
                - every_n_weeks: (weekly only) interval between occurrences
                - which: (monthly_nth_weekday only) list of nth occurrences [1, 3]
        """
        self.type = schedule_dict.get("type")
        self.weekday = schedule_dict.get("weekday", "").lower()

        # Validate weekday
        if self.weekday not in WEEKDAYS:
            raise ValueError(f"Invalid weekday: {self.weekday}")

        # Parse times
        try:
            self.start_time = time.fromisoformat(schedule_dict["start_time"])
            self.end_time = time.fromisoformat(schedule_dict["end_time"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid time format: {e}")

        # Type-specific attributes
        if self.type == "weekly":
            self.every_n_weeks = schedule_dict.get("every_n_weeks", 1)
            if not isinstance(self.every_n_weeks, int) or self.every_n_weeks < 1:
                raise ValueError(f"every_n_weeks must be a positive integer")
        elif self.type == "monthly_nth_weekday":
            self.which = schedule_dict.get("which", [])
            if not isinstance(self.which, list) or not self.which:
                raise ValueError("which must be a non-empty list for monthly_nth_weekday")
            # Validate which values (1-4 or -1 for last)
            for n in self.which:
                if n not in [1, 2, 3, 4, -1]:
                    raise ValueError(f"Invalid 'which' value: {n}. Must be 1-4 or -1 (last)")
        else:
            raise ValueError(f"Invalid schedule type: {self.type}")

    def is_active_at(self, dt: datetime, reference_date: Optional[date] = None) -> bool:
        """
        Check if this schedule is active at the given datetime.

        Args:
            dt: Datetime to check (should be timezone-aware)
            reference_date: Reference date for calculating week intervals (weekly pattern only)

        Returns:
            True if the schedule is active at the given datetime
        """
        # Check if the weekday matches
        if ISO_TO_WEEKDAY[dt.isoweekday()] != self.weekday:
            return False

        # Check if time is within range
        current_time = dt.time()
        if not (self.start_time <= current_time <= self.end_time):
            return False

        # Type-specific checks
        if self.type == "weekly":
            if self.every_n_weeks == 1:
                return True

            # For every N weeks, we need a reference date to calculate
            if reference_date is None:
                # Without reference, we can't determine week parity
                return True

            # Calculate weeks since reference date
            weeks_diff = (dt.date() - reference_date).days // 7
            return weeks_diff % self.every_n_weeks == 0

        elif self.type == "monthly_nth_weekday":
            # Check if this is the Nth occurrence of this weekday in the month
            nth = self._get_nth_weekday_of_month(dt.date())
            return nth in self.which

        return False

    def get_next_occurrence(
        self, after_dt: datetime, timezone: ZoneInfo, reference_date: Optional[date] = None
    ) -> Optional[datetime]:
        """
        Get the next occurrence of this schedule after the given datetime.

        Args:
            after_dt: Find occurrence after this datetime (timezone-aware)
            timezone: Timezone for the session
            reference_date: Reference date for calculating week intervals (weekly only)

        Returns:
            Datetime of next occurrence, or None if no occurrence found within 1 year
        """
        # Start from the day after after_dt
        search_date = after_dt.date() + timedelta(days=1)
        max_date = search_date + timedelta(days=365)  # Search up to 1 year ahead

        while search_date <= max_date:
            # Check if this date matches the pattern
            if self._date_matches_pattern(search_date, reference_date):
                # Construct datetime with start time
                next_dt = datetime.combine(search_date, self.start_time)
                next_dt = next_dt.replace(tzinfo=timezone)

                # Make sure it's actually after after_dt
                if next_dt > after_dt:
                    return next_dt

            search_date += timedelta(days=1)

        return None

    def get_occurrences_in_range(
        self,
        start_date: date,
        end_date: date,
        timezone: ZoneInfo,
        reference_date: Optional[date] = None,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Get all occurrences of this schedule within a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            timezone: Timezone for the session
            reference_date: Reference date for calculating week intervals (weekly only)

        Returns:
            List of (start_datetime, end_datetime) tuples for each occurrence
        """
        occurrences = []
        current_date = start_date

        while current_date <= end_date:
            if self._date_matches_pattern(current_date, reference_date):
                start_dt = datetime.combine(current_date, self.start_time)
                start_dt = start_dt.replace(tzinfo=timezone)

                end_dt = datetime.combine(current_date, self.end_time)
                end_dt = end_dt.replace(tzinfo=timezone)

                occurrences.append((start_dt, end_dt))

            current_date += timedelta(days=1)

        return occurrences

    def to_human_readable(self) -> str:
        """
        Convert this schedule to a human-readable string.

        Returns:
            Human-readable description (e.g., "Thursdays from 7:00pm-10:30pm")
        """
        # Format times
        start_str = self.start_time.strftime("%I:%M%p").lstrip("0").lower()
        end_str = self.end_time.strftime("%I:%M%p").lstrip("0").lower()

        # Format day
        day_name = self.weekday.capitalize()

        if self.type == "weekly":
            if self.every_n_weeks == 1:
                day_str = f"{day_name}s"
            elif self.every_n_weeks == 2:
                day_str = f"Every other {day_name}"
            else:
                day_str = f"Every {self.every_n_weeks} weeks on {day_name}"

        elif self.type == "monthly_nth_weekday":
            # Convert which numbers to ordinals
            ordinals = {
                1: "first",
                2: "second",
                3: "third",
                4: "fourth",
                -1: "last",
            }
            which_str = " and ".join([ordinals[n] for n in sorted(self.which)])
            day_str = f"{which_str.capitalize()} {day_name}s of the month"

        return f"{day_str} from {start_str}-{end_str}"

    def _date_matches_pattern(self, check_date: date, reference_date: Optional[date] = None) -> bool:
        """
        Check if a date matches this schedule's pattern (ignoring time).

        Args:
            check_date: Date to check
            reference_date: Reference date for week interval calculations

        Returns:
            True if the date matches the pattern
        """
        # Check weekday
        if ISO_TO_WEEKDAY[check_date.isoweekday()] != self.weekday:
            return False

        if self.type == "weekly":
            if self.every_n_weeks == 1:
                return True

            if reference_date is None:
                return True

            weeks_diff = (check_date - reference_date).days // 7
            return weeks_diff % self.every_n_weeks == 0

        elif self.type == "monthly_nth_weekday":
            nth = self._get_nth_weekday_of_month(check_date)
            return nth in self.which

        return False

    def _get_nth_weekday_of_month(self, check_date: date) -> int:
        """
        Get which occurrence of this weekday this is in the month.

        Args:
            check_date: Date to check

        Returns:
            1-4 for first through fourth occurrence, -1 for last occurrence
        """
        # Get all occurrences of this weekday in this month
        year = check_date.year
        month = check_date.month
        target_isoweekday = WEEKDAY_TO_ISO[self.weekday]

        occurrences = []
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            d = date(year, month, day)
            if d.isoweekday() == target_isoweekday:
                occurrences.append(d)

        # Find position
        try:
            position = occurrences.index(check_date) + 1  # 1-indexed
        except ValueError:
            return 0  # Not found

        # Check if it's the last occurrence
        if position == len(occurrences):
            return -1

        return position


class SessionRecurrence:
    """Manages recurrence patterns for a session."""

    def __init__(self, recurrence_json: Optional[str]):
        """
        Initialize SessionRecurrence from JSON string.

        Args:
            recurrence_json: JSON string containing recurrence definition, or None
        """
        self.schedules: List[RecurrenceSchedule] = []

        if recurrence_json is None or recurrence_json.strip() == "":
            return

        try:
            data = json.loads(recurrence_json)
            if not isinstance(data, dict) or "schedules" not in data:
                raise ValueError("Recurrence JSON must contain 'schedules' key")

            for schedule_dict in data["schedules"]:
                self.schedules.append(RecurrenceSchedule(schedule_dict))

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def is_active_at(self, dt: datetime, reference_date: Optional[date] = None) -> bool:
        """
        Check if any schedule is active at the given datetime.

        Args:
            dt: Datetime to check (should be timezone-aware)
            reference_date: Reference date for week interval calculations

        Returns:
            True if any schedule is active
        """
        return any(schedule.is_active_at(dt, reference_date) for schedule in self.schedules)

    def get_next_occurrence(
        self, after_dt: datetime, timezone: ZoneInfo, reference_date: Optional[date] = None
    ) -> Optional[datetime]:
        """
        Get the soonest next occurrence across all schedules.

        Args:
            after_dt: Find occurrence after this datetime
            timezone: Timezone for the session
            reference_date: Reference date for week interval calculations

        Returns:
            Datetime of next occurrence, or None if no schedules or no occurrence found
        """
        occurrences = []
        for schedule in self.schedules:
            next_occ = schedule.get_next_occurrence(after_dt, timezone, reference_date)
            if next_occ:
                occurrences.append(next_occ)

        return min(occurrences) if occurrences else None

    def get_occurrences_in_range(
        self,
        start_date: date,
        end_date: date,
        timezone: ZoneInfo,
        reference_date: Optional[date] = None,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Get all occurrences across all schedules within a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            timezone: Timezone for the session
            reference_date: Reference date for week interval calculations

        Returns:
            Sorted list of (start_datetime, end_datetime) tuples
        """
        all_occurrences = []
        for schedule in self.schedules:
            all_occurrences.extend(
                schedule.get_occurrences_in_range(start_date, end_date, timezone, reference_date)
            )

        # Sort by start time
        all_occurrences.sort(key=lambda x: x[0])
        return all_occurrences

    def to_human_readable(self) -> str:
        """
        Convert all schedules to a human-readable string.

        Returns:
            Human-readable description, or "No regular schedule" if no schedules
        """
        if not self.schedules:
            return "No regular schedule"

        descriptions = [schedule.to_human_readable() for schedule in self.schedules]

        if len(descriptions) == 1:
            return descriptions[0]
        elif len(descriptions) == 2:
            return f"{descriptions[0]} and {descriptions[1]}"
        else:
            # Oxford comma for 3+
            return ", ".join(descriptions[:-1]) + f", and {descriptions[-1]}"

    def has_schedules(self) -> bool:
        """Check if this recurrence has any schedules."""
        return len(self.schedules) > 0


def validate_recurrence_json(recurrence_json: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate recurrence JSON format.

    Args:
        recurrence_json: JSON string to validate, or None

    Returns:
        Tuple of (is_valid, error_message)
    """
    if recurrence_json is None or recurrence_json.strip() == "":
        return (True, None)

    try:
        SessionRecurrence(recurrence_json)
        return (True, None)
    except ValueError as e:
        return (False, str(e))


def to_human_readable(recurrence_json: Optional[str]) -> str:
    """
    Convert recurrence JSON to human-readable string.

    Args:
        recurrence_json: JSON string containing recurrence definition, or None

    Returns:
        Human-readable description
    """
    try:
        recurrence = SessionRecurrence(recurrence_json)
        return recurrence.to_human_readable()
    except ValueError:
        return "Invalid recurrence pattern"
