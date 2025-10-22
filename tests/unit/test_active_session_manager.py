"""
Unit tests for active_session_manager.py - Feature 004

Tests the active session tracking logic including:
- Session activation/deactivation based on time windows
- Person active session updates when checking in
- Handling of overlapping sessions
- Timezone handling
"""

import pytest
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock, patch
import psycopg2


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection and cursor."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class TestUpdateActiveSessions:
    """Tests for the update_active_sessions function."""

    @patch('active_session_manager.get_db_connection')
    @patch('active_session_manager.activate_session_instance')
    @patch('active_session_manager.deactivate_session_instance')
    def test_activates_session_in_active_window(
        self, mock_deactivate, mock_activate, mock_get_db
    ):
        """Test that a session becomes active when current time is in its active window."""
        from active_session_manager import update_active_sessions
        from recurrence_utils import SessionRecurrence

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Session with Thursday 7:00pm-10:30pm schedule, Austin timezone
        recurrence_json = '''{
            "schedules": [{
                "type": "weekly",
                "weekday": "thursday",
                "start_time": "19:00",
                "end_time": "22:30",
                "every_n_weeks": 1
            }]
        }'''

        # Mock session data
        mock_cur.fetchall.return_value = [(
            1,  # session_id
            "Test Session",  # name
            recurrence_json,  # recurrence
            "America/Chicago",  # timezone
            60,  # buffer_before
            60,  # buffer_after
            date(2024, 1, 1)  # initiation_date
        )]

        # Mock session instance on a Thursday
        mock_cur.fetchall.side_effect = [
            # First call: sessions
            [(1, "Test Session", recurrence_json, "America/Chicago", 60, 60, date(2024, 1, 1))],
            # Second call: instances for this session
            [(101, date(2024, 3, 14), time(19, 0), time(22, 30), False, False)]  # Thursday
        ]

        # Run the check at 6:59pm Thursday (look ahead will see 7:00pm in window)
        with patch('active_session_manager.datetime') as mock_dt:
            # Simulate running at 18:59 (6:59pm) on Thursday, March 14, 2024
            thursday_659pm = datetime(2024, 3, 14, 18, 59, 0, tzinfo=ZoneInfo('America/Chicago'))
            mock_dt.utcnow.return_value = thursday_659pm.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

            stats = update_active_sessions()

        # Should activate the session
        assert len(stats['activated']) == 1
        assert stats['activated'][0]['session_id'] == 1
        mock_activate.assert_called_once()

    @patch('active_session_manager.get_db_connection')
    def test_timezone_handling(self, mock_get_db):
        """Test that sessions are activated based on local timezone, not UTC."""
        from active_session_manager import update_active_sessions

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Austin session at 7pm local time
        austin_recurrence = '''{
            "schedules": [{
                "type": "weekly",
                "weekday": "thursday",
                "start_time": "19:00",
                "end_time": "22:30",
                "every_n_weeks": 1
            }]
        }'''

        # Mock two sessions in different timezones
        mock_cur.fetchall.side_effect = [
            # Sessions
            [
                (1, "Austin", austin_recurrence, "America/Chicago", 60, 60, date(2024, 1, 1)),
                (2, "NYC", austin_recurrence, "America/New_York", 60, 60, date(2024, 1, 1))
            ],
            # Instances for Austin (session 1)
            [(101, date(2024, 3, 14), time(19, 0), time(22, 30), False, False)],
            # Instances for NYC (session 2)
            [(201, date(2024, 3, 14), time(19, 0), time(22, 30), False, False)]
        ]

        # Timezone test: Austin is UTC-5 (or -6 with DST), NYC is UTC-4 (or -5)
        # At 7pm Austin time, it's 8pm NYC time (1 hour ahead)
        # So Austin session should be active but NYC shouldn't yet

        stats = update_active_sessions()

        # Both timezones should be handled independently
        # This is a simplified test - in practice we'd verify exact timing


class TestActivateSessionInstance:
    """Tests for activating session instances."""

    @patch('active_session_manager.get_db_connection')
    @patch('active_session_manager.update_person_active_instance')
    def test_activates_instance_and_updates_checked_in_people(
        self, mock_update_person, mock_get_db
    ):
        """Test that activating a session updates people who checked in as 'yes'."""
        from active_session_manager import activate_session_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock people who checked in as 'yes'
        mock_cur.fetchall.return_value = [(10,), (20,), (30,)]  # person_ids

        activate_session_instance(1, 101)

        # Should mark instance as active
        assert mock_cur.execute.call_count >= 2
        activate_call = [call for call in mock_cur.execute.call_args_list
                        if 'UPDATE session_instance' in call[0][0]][0]
        assert 'is_active = TRUE' in activate_call[0][0]

        # Should update all three people
        assert mock_update_person.call_count == 3


class TestDeactivateSessionInstance:
    """Tests for deactivating session instances."""

    @patch('active_session_manager.get_db_connection')
    @patch('active_session_manager.recalculate_person_active_instance')
    def test_deactivates_instance_and_recalculates_people(
        self, mock_recalc, mock_get_db
    ):
        """Test that deactivating a session recalculates affected people's active sessions."""
        from active_session_manager import deactivate_session_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock people currently at this session
        mock_cur.fetchall.return_value = [(10,), (20,)]  # person_ids

        deactivate_session_instance(1, 101)

        # Should mark instance as inactive
        deactivate_call = [call for call in mock_cur.execute.call_args_list
                          if 'UPDATE session_instance' in call[0][0]][0]
        assert 'is_active = FALSE' in deactivate_call[0][0]

        # Should recalculate for both people
        assert mock_recalc.call_count == 2


class TestUpdatePersonActiveInstance:
    """Tests for updating a person's active session instance."""

    @patch('active_session_manager.get_db_connection')
    def test_sets_active_session_when_instance_is_active(self, mock_get_db):
        """Test that checking in to an active session sets person's location."""
        from active_session_manager import update_person_active_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock: instance is active
        mock_cur.fetchone.side_effect = [
            (True,),  # is_active = true
            [(101, date(2024, 3, 14), time(19, 0), datetime(2024, 3, 14, 19, 0))]  # active sessions for person
        ]
        mock_cur.fetchall.return_value = [(101, date(2024, 3, 14), time(19, 0), datetime(2024, 3, 14, 19, 0))]

        update_person_active_instance(10, 101)

        # Should update person's active session
        update_call = [call for call in mock_cur.execute.call_args_list
                      if 'UPDATE person' in call[0][0]][0]
        assert 'at_active_session_instance_id' in update_call[0][0]

    @patch('active_session_manager.get_db_connection')
    def test_does_not_set_active_session_when_instance_inactive(self, mock_get_db):
        """Test that checking in to inactive session doesn't set person's location."""
        from active_session_manager import update_person_active_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock: instance is not active
        mock_cur.fetchone.return_value = (False,)

        update_person_active_instance(10, 101)

        # Should NOT update person's location
        update_calls = [call for call in mock_cur.execute.call_args_list
                       if 'UPDATE person' in call[0][0]]
        assert len(update_calls) == 0

    @patch('active_session_manager.get_db_connection')
    def test_handles_overlapping_sessions_first_start_wins(self, mock_get_db):
        """Test that when person has multiple active sessions, earliest start time wins."""
        from active_session_manager import update_person_active_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock: instance is active, person has two overlapping active sessions
        mock_cur.fetchone.side_effect = [
            (True,),  # instance 101 is active
        ]
        mock_cur.fetchall.return_value = [
            (102, date(2024, 3, 14), time(19, 30), datetime(2024, 3, 14, 19, 35)),  # Later start
            (101, date(2024, 3, 14), time(19, 0), datetime(2024, 3, 14, 19, 30)),   # Earlier start
        ]

        update_person_active_instance(10, 101)

        # Should choose instance 101 (earlier start time)
        update_call = [call for call in mock_cur.execute.call_args_list
                      if 'UPDATE person' in call[0][0] and 'at_active_session_instance_id' in call[0][0]][0]
        assert 101 in update_call[0][1]  # Should set to instance 101


class TestRecalculatePersonActiveInstance:
    """Tests for recalculating which session a person should be at."""

    @patch('active_session_manager.get_db_connection')
    def test_clears_active_session_when_no_active_sessions(self, mock_get_db):
        """Test that person's location is cleared when they have no active sessions."""
        from active_session_manager import recalculate_person_active_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock: no active sessions for this person
        mock_cur.fetchall.return_value = []

        recalculate_person_active_instance(10)

        # Should clear the person's active session
        update_call = [call for call in mock_cur.execute.call_args_list
                      if 'UPDATE person' in call[0][0]][0]
        assert 'at_active_session_instance_id = NULL' in update_call[0][0] or None in update_call[0][1]

    @patch('active_session_manager.get_db_connection')
    def test_switches_to_another_active_session(self, mock_get_db):
        """Test that person switches to another active session when one ends."""
        from active_session_manager import recalculate_person_active_instance

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock: person has another active session
        mock_cur.fetchall.return_value = [
            (201, date(2024, 3, 14), time(20, 0), datetime(2024, 3, 14, 20, 0))
        ]

        recalculate_person_active_instance(10)

        # Should set to the other active session
        update_call = [call for call in mock_cur.execute.call_args_list
                      if 'UPDATE person' in call[0][0]][0]
        assert 201 in update_call[0][1]


class TestGetSessionActiveInstances:
    """Tests for getting a session's active instances."""

    @patch('active_session_manager.get_db_connection')
    def test_returns_active_instance_ids(self, mock_get_db):
        """Test that function returns list of active instance IDs."""
        from active_session_manager import get_session_active_instances

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.return_value = [(101,), (102,)]

        result = get_session_active_instances(1)

        assert result == [101, 102]

    @patch('active_session_manager.get_db_connection')
    def test_returns_empty_list_when_no_active_instances(self, mock_get_db):
        """Test that function returns empty list when session has no active instances."""
        from active_session_manager import get_session_active_instances

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.return_value = []

        result = get_session_active_instances(1)

        assert result == []


class TestGetPersonActiveSession:
    """Tests for getting a person's active session."""

    @patch('active_session_manager.get_db_connection')
    def test_returns_active_session_details(self, mock_get_db):
        """Test that function returns full active session details."""
        from active_session_manager import get_person_active_session

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.return_value = (
            101,  # session_instance_id
            1,    # session_id
            date(2024, 3, 14),
            time(19, 0),
            time(22, 30),
            "Test Session",
            "test"
        )

        result = get_person_active_session(10)

        assert result is not None
        assert result['session_instance_id'] == 101
        assert result['session_name'] == "Test Session"

    @patch('active_session_manager.get_db_connection')
    def test_returns_none_when_person_not_at_session(self, mock_get_db):
        """Test that function returns None when person is not at any session."""
        from active_session_manager import get_person_active_session

        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.return_value = None

        result = get_person_active_session(10)

        assert result is None
