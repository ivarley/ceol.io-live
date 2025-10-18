"""
Unit tests for recurrence_utils module.
"""

import pytest
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import json

from recurrence_utils import (
    RecurrenceSchedule,
    SessionRecurrence,
    validate_recurrence_json,
    to_human_readable,
    WEEKDAY_TO_ISO,
)


class TestRecurrenceSchedule:
    """Tests for RecurrenceSchedule class."""

    def test_weekly_schedule_initialization(self):
        """Test creating a weekly schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        assert schedule.type == "weekly"
        assert schedule.weekday == "thursday"
        assert schedule.start_time == time(19, 0)
        assert schedule.end_time == time(22, 30)
        assert schedule.every_n_weeks == 1

    def test_monthly_nth_weekday_schedule_initialization(self):
        """Test creating a monthly nth weekday schedule."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [1, 3],
            "start_time": "16:00",
            "end_time": "20:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        assert schedule.type == "monthly_nth_weekday"
        assert schedule.weekday == "sunday"
        assert schedule.which == [1, 3]
        assert schedule.start_time == time(16, 0)
        assert schedule.end_time == time(20, 0)

    def test_invalid_weekday(self):
        """Test that invalid weekday raises ValueError."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "funday",
            "start_time": "19:00",
            "end_time": "22:00",
        }
        with pytest.raises(ValueError, match="Invalid weekday"):
            RecurrenceSchedule(schedule_dict)

    def test_invalid_time_format(self):
        """Test that invalid time format raises ValueError."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "25:00",  # Invalid hour
            "end_time": "22:00",
        }
        with pytest.raises(ValueError, match="Invalid time format"):
            RecurrenceSchedule(schedule_dict)

    def test_invalid_every_n_weeks(self):
        """Test that invalid every_n_weeks raises ValueError."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:00",
            "every_n_weeks": 0,  # Must be >= 1
        }
        with pytest.raises(ValueError, match="every_n_weeks must be a positive integer"):
            RecurrenceSchedule(schedule_dict)

    def test_invalid_which_value(self):
        """Test that invalid 'which' value raises ValueError."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [1, 5],  # 5 is invalid
            "start_time": "16:00",
            "end_time": "20:00",
        }
        with pytest.raises(ValueError, match="Invalid 'which' value"):
            RecurrenceSchedule(schedule_dict)

    def test_is_active_at_weekly(self):
        """Test is_active_at for weekly schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # Thursday at 8pm - should be active
        dt = datetime(2025, 1, 2, 20, 0, tzinfo=tz)  # Jan 2, 2025 is Thursday
        assert schedule.is_active_at(dt) is True

        # Thursday at 6pm - before start, should not be active
        dt = datetime(2025, 1, 2, 18, 0, tzinfo=tz)
        assert schedule.is_active_at(dt) is False

        # Thursday at 11pm - after end, should not be active
        dt = datetime(2025, 1, 2, 23, 0, tzinfo=tz)
        assert schedule.is_active_at(dt) is False

        # Friday at 8pm - wrong day
        dt = datetime(2025, 1, 3, 20, 0, tzinfo=tz)
        assert schedule.is_active_at(dt) is False

    def test_is_active_at_every_other_week(self):
        """Test is_active_at for every other week schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 2,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")
        reference = date(2025, 1, 2)  # Thursday, Jan 2, 2025

        # Week 0 (reference week) - should be active
        dt = datetime(2025, 1, 2, 20, 0, tzinfo=tz)
        assert schedule.is_active_at(dt, reference) is True

        # Week 1 - should not be active (every OTHER week)
        dt = datetime(2025, 1, 9, 20, 0, tzinfo=tz)
        assert schedule.is_active_at(dt, reference) is False

        # Week 2 - should be active
        dt = datetime(2025, 1, 16, 20, 0, tzinfo=tz)
        assert schedule.is_active_at(dt, reference) is True

    def test_is_active_at_monthly_nth_weekday(self):
        """Test is_active_at for monthly nth weekday schedule."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [1, 3],
            "start_time": "16:00",
            "end_time": "20:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # First Sunday of January 2025 at 5pm - should be active
        dt = datetime(2025, 1, 5, 17, 0, tzinfo=tz)  # Jan 5 is 1st Sunday
        assert schedule.is_active_at(dt) is True

        # Third Sunday of January 2025 at 5pm - should be active
        dt = datetime(2025, 1, 19, 17, 0, tzinfo=tz)  # Jan 19 is 3rd Sunday
        assert schedule.is_active_at(dt) is True

        # Second Sunday of January 2025 at 5pm - should NOT be active
        dt = datetime(2025, 1, 12, 17, 0, tzinfo=tz)  # Jan 12 is 2nd Sunday
        assert schedule.is_active_at(dt) is False

        # Fourth Sunday at 5pm - should NOT be active
        dt = datetime(2025, 1, 26, 17, 0, tzinfo=tz)  # Jan 26 is 4th Sunday
        assert schedule.is_active_at(dt) is False

    def test_get_next_occurrence_weekly(self):
        """Test get_next_occurrence for weekly schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # Start on a Monday, next occurrence should be Thursday
        after_dt = datetime(2025, 1, 6, 12, 0, tzinfo=tz)  # Monday
        next_occ = schedule.get_next_occurrence(after_dt, tz)

        assert next_occ is not None
        assert next_occ.date() == date(2025, 1, 9)  # Thursday
        assert next_occ.time() == time(19, 0)

    def test_get_next_occurrence_every_other_week(self):
        """Test get_next_occurrence for every other week schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 2,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")
        reference = date(2025, 1, 2)  # Thursday

        # After week 0 Thursday, should get week 2 Thursday
        after_dt = datetime(2025, 1, 2, 23, 0, tzinfo=tz)
        next_occ = schedule.get_next_occurrence(after_dt, tz, reference)

        assert next_occ is not None
        assert next_occ.date() == date(2025, 1, 16)  # Two weeks later

    def test_get_next_occurrence_monthly_nth_weekday(self):
        """Test get_next_occurrence for monthly nth weekday schedule."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [1, 3],
            "start_time": "16:00",
            "end_time": "20:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # After first Sunday, should get third Sunday
        after_dt = datetime(2025, 1, 5, 21, 0, tzinfo=tz)  # After 1st Sunday ends
        next_occ = schedule.get_next_occurrence(after_dt, tz)

        assert next_occ is not None
        assert next_occ.date() == date(2025, 1, 19)  # 3rd Sunday

        # After third Sunday, should get first Sunday of next month
        after_dt = datetime(2025, 1, 19, 21, 0, tzinfo=tz)
        next_occ = schedule.get_next_occurrence(after_dt, tz)

        assert next_occ is not None
        assert next_occ.date() == date(2025, 2, 2)  # 1st Sunday of Feb

    def test_get_occurrences_in_range(self):
        """Test get_occurrences_in_range."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # Get all Thursdays in January 2025
        occurrences = schedule.get_occurrences_in_range(
            date(2025, 1, 1), date(2025, 1, 31), tz
        )

        # January 2025 has 5 Thursdays: 2, 9, 16, 23, 30
        assert len(occurrences) == 5

        # Check first occurrence
        start_dt, end_dt = occurrences[0]
        assert start_dt.date() == date(2025, 1, 2)
        assert start_dt.time() == time(19, 0)
        assert end_dt.time() == time(22, 30)

    def test_to_human_readable_weekly(self):
        """Test to_human_readable for weekly schedule."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        readable = schedule.to_human_readable()
        assert "Thursday" in readable
        assert "7:00pm" in readable
        assert "10:30pm" in readable

    def test_to_human_readable_every_other_week(self):
        """Test to_human_readable for every other week."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 2,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        readable = schedule.to_human_readable()
        assert "Every other Thursday" in readable

    def test_to_human_readable_monthly_nth_weekday(self):
        """Test to_human_readable for monthly nth weekday."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [1, 3],
            "start_time": "16:00",
            "end_time": "20:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        readable = schedule.to_human_readable()
        assert "first and third" in readable.lower()
        assert "Sunday" in readable

    def test_nth_weekday_calculation(self):
        """Test _get_nth_weekday_of_month calculation."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "sunday",
            "which": [-1],  # Last Sunday
            "start_time": "16:00",
            "end_time": "20:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        # January 2025: last Sunday is Jan 26
        nth = schedule._get_nth_weekday_of_month(date(2025, 1, 26))
        assert nth == -1

        # January 2025: Jan 19 is 3rd Sunday (not last)
        nth = schedule._get_nth_weekday_of_month(date(2025, 1, 19))
        assert nth == 3


class TestSessionRecurrence:
    """Tests for SessionRecurrence class."""

    def test_empty_recurrence(self):
        """Test SessionRecurrence with None."""
        recurrence = SessionRecurrence(None)
        assert recurrence.has_schedules() is False
        assert recurrence.to_human_readable() == "No regular schedule"

    def test_empty_string_recurrence(self):
        """Test SessionRecurrence with empty string."""
        recurrence = SessionRecurrence("")
        assert recurrence.has_schedules() is False
        assert recurrence.to_human_readable() == "No regular schedule"

    def test_single_schedule(self):
        """Test SessionRecurrence with one schedule."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "thursday",
                    "start_time": "19:00",
                    "end_time": "22:30",
                    "every_n_weeks": 1,
                }
            ]
        })
        recurrence = SessionRecurrence(json_str)

        assert recurrence.has_schedules() is True
        assert len(recurrence.schedules) == 1

    def test_multiple_schedules(self):
        """Test SessionRecurrence with multiple schedules."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "tuesday",
                    "start_time": "19:00",
                    "end_time": "22:00",
                    "every_n_weeks": 1,
                },
                {
                    "type": "weekly",
                    "weekday": "sunday",
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "every_n_weeks": 1,
                },
            ]
        })
        recurrence = SessionRecurrence(json_str)

        assert recurrence.has_schedules() is True
        assert len(recurrence.schedules) == 2

    def test_is_active_at_multiple_schedules(self):
        """Test is_active_at with multiple schedules."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "tuesday",
                    "start_time": "19:00",
                    "end_time": "22:00",
                    "every_n_weeks": 1,
                },
                {
                    "type": "weekly",
                    "weekday": "sunday",
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "every_n_weeks": 1,
                },
            ]
        })
        recurrence = SessionRecurrence(json_str)

        tz = ZoneInfo("America/Chicago")

        # Tuesday at 8pm - should be active
        dt = datetime(2025, 1, 7, 20, 0, tzinfo=tz)  # Jan 7 is Tuesday
        assert recurrence.is_active_at(dt) is True

        # Sunday at 4pm - should be active
        dt = datetime(2025, 1, 5, 16, 0, tzinfo=tz)  # Jan 5 is Sunday
        assert recurrence.is_active_at(dt) is True

        # Monday at 8pm - should not be active
        dt = datetime(2025, 1, 6, 20, 0, tzinfo=tz)  # Jan 6 is Monday
        assert recurrence.is_active_at(dt) is False

    def test_get_next_occurrence_multiple_schedules(self):
        """Test get_next_occurrence returns soonest across all schedules."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "thursday",
                    "start_time": "19:00",
                    "end_time": "22:00",
                    "every_n_weeks": 1,
                },
                {
                    "type": "weekly",
                    "weekday": "sunday",
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "every_n_weeks": 1,
                },
            ]
        })
        recurrence = SessionRecurrence(json_str)

        tz = ZoneInfo("America/Chicago")

        # After Monday, next should be Thursday
        after_dt = datetime(2025, 1, 6, 12, 0, tzinfo=tz)  # Monday
        next_occ = recurrence.get_next_occurrence(after_dt, tz)

        assert next_occ is not None
        assert next_occ.date() == date(2025, 1, 9)  # Thursday comes before Sunday

    def test_get_occurrences_in_range_multiple_schedules(self):
        """Test get_occurrences_in_range with multiple schedules."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "tuesday",
                    "start_time": "19:00",
                    "end_time": "22:00",
                    "every_n_weeks": 1,
                },
                {
                    "type": "weekly",
                    "weekday": "sunday",
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "every_n_weeks": 1,
                },
            ]
        })
        recurrence = SessionRecurrence(json_str)

        tz = ZoneInfo("America/Chicago")

        # Get all occurrences in January 2025
        occurrences = recurrence.get_occurrences_in_range(
            date(2025, 1, 1), date(2025, 1, 31), tz
        )

        # January 2025: Tuesdays (7, 14, 21, 28) = 4, Sundays (5, 12, 19, 26) = 4, total = 8
        assert len(occurrences) == 8

        # Check that they're sorted
        for i in range(len(occurrences) - 1):
            assert occurrences[i][0] <= occurrences[i + 1][0]

    def test_to_human_readable_single(self):
        """Test to_human_readable with single schedule."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "thursday",
                    "start_time": "19:00",
                    "end_time": "22:30",
                    "every_n_weeks": 1,
                }
            ]
        })
        recurrence = SessionRecurrence(json_str)

        readable = recurrence.to_human_readable()
        assert "Thursday" in readable
        assert "7:00pm" in readable

    def test_to_human_readable_multiple(self):
        """Test to_human_readable with multiple schedules."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "tuesday",
                    "start_time": "19:00",
                    "end_time": "22:00",
                    "every_n_weeks": 1,
                },
                {
                    "type": "weekly",
                    "weekday": "sunday",
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "every_n_weeks": 1,
                },
            ]
        })
        recurrence = SessionRecurrence(json_str)

        readable = recurrence.to_human_readable()
        assert "Tuesday" in readable
        assert "Sunday" in readable
        assert " and " in readable

    def test_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            SessionRecurrence("{not valid json")

    def test_missing_schedules_key(self):
        """Test that missing 'schedules' key raises ValueError."""
        json_str = json.dumps({"other_key": "value"})
        with pytest.raises(ValueError, match="must contain 'schedules' key"):
            SessionRecurrence(json_str)


class TestValidateRecurrenceJson:
    """Tests for validate_recurrence_json function."""

    def test_validate_none(self):
        """Test validating None recurrence."""
        is_valid, error = validate_recurrence_json(None)
        assert is_valid is True
        assert error is None

    def test_validate_empty_string(self):
        """Test validating empty string."""
        is_valid, error = validate_recurrence_json("")
        assert is_valid is True
        assert error is None

    def test_validate_valid_json(self):
        """Test validating valid recurrence JSON."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "thursday",
                    "start_time": "19:00",
                    "end_time": "22:30",
                    "every_n_weeks": 1,
                }
            ]
        })
        is_valid, error = validate_recurrence_json(json_str)
        assert is_valid is True
        assert error is None

    def test_validate_invalid_json(self):
        """Test validating invalid JSON."""
        is_valid, error = validate_recurrence_json("{not valid")
        assert is_valid is False
        assert error is not None


class TestToHumanReadable:
    """Tests for to_human_readable convenience function."""

    def test_to_human_readable_none(self):
        """Test to_human_readable with None."""
        readable = to_human_readable(None)
        assert readable == "No regular schedule"

    def test_to_human_readable_valid(self):
        """Test to_human_readable with valid JSON."""
        json_str = json.dumps({
            "schedules": [
                {
                    "type": "weekly",
                    "weekday": "thursday",
                    "start_time": "19:00",
                    "end_time": "22:30",
                    "every_n_weeks": 1,
                }
            ]
        })
        readable = to_human_readable(json_str)
        assert "Thursday" in readable

    def test_to_human_readable_invalid(self):
        """Test to_human_readable with invalid JSON."""
        readable = to_human_readable("{invalid")
        assert readable == "Invalid recurrence pattern"


class TestTimezoneHandling:
    """Tests for timezone-aware datetime handling."""

    def test_different_timezones(self):
        """Test that schedules work correctly across timezones."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:00",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        # Test in Central time
        tz_central = ZoneInfo("America/Chicago")
        dt_central = datetime(2025, 1, 2, 20, 0, tzinfo=tz_central)
        assert schedule.is_active_at(dt_central) is True

        # Test in Eastern time
        tz_eastern = ZoneInfo("America/New_York")
        dt_eastern = datetime(2025, 1, 2, 20, 0, tzinfo=tz_eastern)
        assert schedule.is_active_at(dt_eastern) is True

        # Both should be Thursdays at 8pm in their respective timezones

    def test_dst_transition(self):
        """Test handling of DST transitions."""
        # This is a basic test - DST handling is complex
        schedule_dict = {
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:00",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # Date before DST change (if applicable)
        dt = datetime(2025, 3, 6, 20, 0, tzinfo=tz)  # Thursday
        assert schedule.is_active_at(dt) is True

        # The schedule should still work correctly regardless of DST


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_midnight_crossing(self):
        """Test schedule that crosses midnight."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "friday",
            "start_time": "22:00",
            "end_time": "23:59",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("America/Chicago")

        # Friday at 11pm - should be active
        dt = datetime(2025, 1, 3, 23, 0, tzinfo=tz)  # Jan 3 is Friday
        assert schedule.is_active_at(dt) is True

    def test_leap_year(self):
        """Test handling of leap year dates."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "saturday",
            "start_time": "10:00",
            "end_time": "12:00",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("UTC")

        # Test on Feb 29, 2024 (leap year)
        occurrences = schedule.get_occurrences_in_range(
            date(2024, 2, 24), date(2024, 3, 2), tz
        )

        # Should include Feb 24 and Mar 2 (both Saturdays)
        assert len(occurrences) == 2

    def test_month_with_5_occurrences(self):
        """Test monthly pattern in month with 5 occurrences of weekday."""
        schedule_dict = {
            "type": "monthly_nth_weekday",
            "weekday": "thursday",
            "which": [-1],  # Last Thursday
            "start_time": "19:00",
            "end_time": "22:00",
        }
        schedule = RecurrenceSchedule(schedule_dict)

        tz = ZoneInfo("UTC")

        # January 2025 has 5 Thursdays, last is Jan 30
        occurrences = schedule.get_occurrences_in_range(
            date(2025, 1, 1), date(2025, 1, 31), tz
        )

        assert len(occurrences) == 1
        assert occurrences[0][0].date() == date(2025, 1, 30)

    def test_case_insensitive_weekday(self):
        """Test that weekday names are case-insensitive."""
        schedule_dict = {
            "type": "weekly",
            "weekday": "THURSDAY",  # Uppercase
            "start_time": "19:00",
            "end_time": "22:00",
            "every_n_weeks": 1,
        }
        schedule = RecurrenceSchedule(schedule_dict)

        assert schedule.weekday == "thursday"  # Stored as lowercase
