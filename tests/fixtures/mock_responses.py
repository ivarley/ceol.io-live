"""
Mock responses for external services and APIs.

This module provides realistic mock responses for thesession.org API,
SendGrid email service, and other external integrations.
"""

import json
from datetime import datetime, date
from unittest.mock import MagicMock
from timezone_utils import now_utc


class MockTheSessionAPI:
    """Mock responses for thesession.org API calls."""

    @staticmethod
    def get_tune_response(
        tune_id=1001, name="The Butterfly", tune_type="slip jig", tunebooks=156
    ):
        """Generate mock response for tune lookup."""
        return {
            "tune": {
                "id": tune_id,
                "name": name,
                "type": tune_type,
                "tunebooks": tunebooks,
                "date": "2023-01-15",
                "submitter": {"id": 12345, "name": "Traditional"},
                "settings": [
                    {
                        "id": 1,
                        "key": "G",
                        "abc": "X:1\nT:"
                        + name
                        + "\nR:"
                        + tune_type
                        + "\nK:G\n|:GABc dBAG|...",
                        "date": "2023-01-15",
                    }
                ],
            }
        }

    @staticmethod
    def get_session_response(
        session_id=1, name="Austin Session", city="Austin", country="USA"
    ):
        """Generate mock response for session lookup."""
        return {
            "session": {
                "id": session_id,
                "name": name,
                "town": city,
                "country": country,
                "date": "2023-01-01",
                "submitter": {"id": 67890, "name": "SessionAdmin"},
                "venue": {
                    "name": "The Celtic Pub",
                    "phone": "555-123-4567",
                    "website": "https://celticpub.com",
                },
                "schedule": "Every Tuesday 7:30pm",
                "details": "Traditional Irish music session. All levels welcome!",
            }
        }

    @staticmethod
    def get_error_response(error_code=404, message="Not found"):
        """Generate mock error response."""
        return {"error": {"code": error_code, "message": message}}

    @staticmethod
    def create_mock_requests_get(responses_map):
        """Create a mock requests.get function with predefined responses."""

        def mock_get(url, **kwargs):
            mock_response = MagicMock()

            # Determine response based on URL
            if "tunes/" in url:
                tune_id = url.split("tunes/")[-1].split("/")[0]
                if tune_id in responses_map:
                    mock_response.status_code = 200
                    mock_response.json.return_value = responses_map[tune_id]
                else:
                    mock_response.status_code = 404
                    mock_response.json.return_value = (
                        MockTheSessionAPI.get_error_response()
                    )
            elif "sessions/" in url:
                session_id = url.split("sessions/")[-1].split("/")[0]
                if session_id in responses_map:
                    mock_response.status_code = 200
                    mock_response.json.return_value = responses_map[session_id]
                else:
                    mock_response.status_code = 404
                    mock_response.json.return_value = (
                        MockTheSessionAPI.get_error_response()
                    )
            else:
                mock_response.status_code = 404
                mock_response.json.return_value = MockTheSessionAPI.get_error_response()

            return mock_response

        return mock_get


class MockSendGridAPI:
    """Mock responses for SendGrid email API."""

    @staticmethod
    def get_success_response():
        """Generate mock successful email response."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.body = b"Success"
        mock_response.headers = {"X-Message-Id": "mock-message-id-123"}
        return mock_response

    @staticmethod
    def get_failure_response(status_code=400, error_message="Bad Request"):
        """Generate mock failed email response."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.body = json.dumps(
            {
                "errors": [
                    {
                        "message": error_message,
                        "field": "to",
                        "help": "Please check the email address.",
                    }
                ]
            }
        ).encode()
        return mock_response

    @staticmethod
    def get_unauthorized_response():
        """Generate mock unauthorized response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.body = json.dumps(
            {
                "errors": [
                    {
                        "message": "The provided authorization grant is invalid, expired, or revoked."
                    }
                ]
            }
        ).encode()
        return mock_response

    @staticmethod
    def create_mock_sendgrid_client(success=True, status_code=202):
        """Create a mock SendGrid client."""
        mock_client = MagicMock()

        if success:
            mock_client.send.return_value = MockSendGridAPI.get_success_response()
        else:
            mock_client.send.return_value = MockSendGridAPI.get_failure_response(
                status_code
            )

        return mock_client


class MockDatabaseResponses:
    """Mock database responses for testing."""

    @staticmethod
    def get_user_data():
        """Generate mock user data from database."""
        return (
            1,  # user_id
            42,  # person_id
            "testuser",  # username
            "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.6LQ7nXV6",  # hashed_password
            True,  # is_active
            False,  # is_system_admin
            "America/New_York",  # timezone
            True,  # email_verified
            "Test",  # first_name
            "User",  # last_name
            "test@example.com",  # email
            False,  # auto_save_tunes
            60,  # auto_save_interval
        )

    @staticmethod
    def get_person_data():
        """Generate mock person data from database."""
        return (
            42,  # person_id
            "Test",  # first_name
            "User",  # last_name
            "test@example.com",  # email
            "555-123-4567",  # sms_number
            "Austin",  # city
            "TX",  # state
            "USA",  # country
            12345,  # thesession_user_id
        )

    @staticmethod
    def get_session_data():
        """Generate mock session data from database."""
        return (
            1,  # session_id
            101,  # thesession_id
            "Test Session",  # name
            "test-session",  # path
            "The Celtic Pub",  # location_name
            "https://celticpub.com",  # location_website
            "555-123-4567",  # location_phone
            "123 Music Street",  # location_street
            "Austin",  # city
            "TX",  # state
            "USA",  # country
            "Weekly traditional Irish session",  # comments
            False,  # unlisted_address
            date(2023, 1, 1),  # initiation_date
            None,  # termination_date
            "weekly",  # recurrence
            "America/Chicago",  # timezone
        )

    @staticmethod
    def get_session_instance_data():
        """Generate mock session instance data from database."""
        return (
            1,  # session_instance_id
            1,  # session_id
            date(2023, 8, 15),  # date
            now_utc().replace(
                year=2023, month=8, day=15, hour=19, minute=30, second=0, microsecond=0
            ),  # start_time
            now_utc().replace(
                year=2023, month=8, day=15, hour=22, minute=30, second=0, microsecond=0
            ),  # end_time
            None,  # location_override
            False,  # is_cancelled
            "Great session tonight!",  # comments
            now_utc(),  # created_date
            now_utc(),  # last_modified_date
            None,  # log_complete_date
        )

    @staticmethod
    def get_tune_data():
        """Generate mock tune data from database."""
        return (
            1001,  # tune_id
            "The Butterfly",  # name
            "Slip Jig",  # tune_type
            156,  # tunebook_count_cached
            date(2023, 6, 1),  # tunebook_count_cached_date
            now_utc().replace(
                year=2023, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            ),  # created_date
            now_utc().replace(
                year=2023, month=6, day=1, hour=0, minute=0, second=0, microsecond=0
            ),  # last_modified_date
        )

    @staticmethod
    def get_session_instance_tune_data():
        """Generate mock session instance tune data from database."""
        return (
            1,  # session_instance_tune_id
            1,  # session_instance_id
            1001,  # tune_id
            "The Butterfly",  # name
            "V",  # order_position
            False,  # continues_set
            now_utc().replace(
                year=2023, month=8, day=15, hour=20, minute=15, second=0, microsecond=0
            ),  # played_timestamp
            now_utc().replace(
                year=2023, month=8, day=15, hour=20, minute=20, second=0, microsecond=0
            ),  # inserted_timestamp
            None,  # key_override
            None,  # setting_override
            now_utc(),  # created_date
            now_utc(),  # last_modified_date
        )

    @staticmethod
    def create_mock_cursor(
        fetchone_data=None, fetchall_data=None, execute_side_effect=None
    ):
        """Create a mock database cursor with predefined responses."""
        mock_cursor = MagicMock()

        if fetchone_data is not None:
            if isinstance(fetchone_data, list):
                mock_cursor.fetchone.side_effect = fetchone_data
            else:
                mock_cursor.fetchone.return_value = fetchone_data

        if fetchall_data is not None:
            if isinstance(fetchall_data, list) and isinstance(fetchall_data[0], list):
                mock_cursor.fetchall.side_effect = fetchall_data
            else:
                mock_cursor.fetchall.return_value = fetchall_data

        if execute_side_effect is not None:
            mock_cursor.execute.side_effect = execute_side_effect

        return mock_cursor


class MockFlaskResponses:
    """Mock Flask application responses for testing."""

    @staticmethod
    def get_login_history_data():
        """Generate mock login history data."""
        return [
            (
                1,  # login_history_id
                1,  # user_id
                "testuser",  # username
                "LOGIN_SUCCESS",  # event_type
                "127.0.0.1",  # ip_address
                "Mozilla/5.0 (Test Browser)",  # user_agent
                "session123",  # session_id
                None,  # failure_reason
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=10,
                    minute=30,
                    second=0,
                    microsecond=0,
                ),  # timestamp
                None,  # additional_data
                "Test",  # first_name
                "User",  # last_name
            ),
            (
                2,  # login_history_id
                None,  # user_id
                "baduser",  # username
                "LOGIN_FAILURE",  # event_type
                "192.168.1.100",  # ip_address
                "Mozilla/5.0 (Test Browser)",  # user_agent
                None,  # session_id
                "USER_NOT_FOUND",  # failure_reason
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=9,
                    minute=45,
                    second=0,
                    microsecond=0,
                ),  # timestamp
                None,  # additional_data
                None,  # first_name
                None,  # last_name
            ),
        ]

    @staticmethod
    def get_active_sessions_data():
        """Generate mock active sessions data for admin view."""
        return [
            (
                1,  # user_id
                "Test",  # first_name
                "User",  # last_name
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=9,
                    minute=0,
                    second=0,
                    microsecond=0,
                ),  # created_date
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=12,
                    minute=30,
                    second=0,
                    microsecond=0,
                ),  # last_accessed
                "127.0.0.1",  # ip_address
            ),
            (
                2,  # user_id
                "Another",  # first_name
                "User",  # last_name
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=10,
                    minute=15,
                    second=0,
                    microsecond=0,
                ),  # created_date
                now_utc().replace(
                    year=2023,
                    month=8,
                    day=15,
                    hour=12,
                    minute=45,
                    second=0,
                    microsecond=0,
                ),  # last_accessed
                "192.168.1.50",  # ip_address
            ),
        ]


# Predefined response collections for common test scenarios
COMMON_THESESSION_RESPONSES = {
    "1001": MockTheSessionAPI.get_tune_response(1001, "The Butterfly", "slip jig", 156),
    "1002": MockTheSessionAPI.get_tune_response(1002, "Morrison's Jig", "jig", 203),
    "1003": MockTheSessionAPI.get_tune_response(1003, "The Musical Priest", "reel", 89),
    "404": MockTheSessionAPI.get_error_response(404, "Tune not found"),
}

COMMON_SESSION_RESPONSES = {
    "1": MockTheSessionAPI.get_session_response(1, "Austin Session", "Austin", "USA"),
    "2": MockTheSessionAPI.get_session_response(2, "Boston Session", "Boston", "USA"),
    "404": MockTheSessionAPI.get_error_response(404, "Session not found"),
}

# Test data for various authentication states
AUTHENTICATION_TEST_DATA = {
    "verified_user": {
        "user_id": 1,
        "username": "verified_user",
        "email": "verified@example.com",
        "email_verified": True,
        "is_active": True,
        "password_correct": True,
    },
    "unverified_user": {
        "user_id": 2,
        "username": "unverified_user",
        "email": "unverified@example.com",
        "email_verified": False,
        "is_active": True,
        "password_correct": True,
    },
    "inactive_user": {
        "user_id": 3,
        "username": "inactive_user",
        "email": "inactive@example.com",
        "email_verified": True,
        "is_active": False,
        "password_correct": True,
    },
    "admin_user": {
        "user_id": 4,
        "username": "admin_user",
        "email": "admin@example.com",
        "email_verified": True,
        "is_active": True,
        "is_system_admin": True,
        "password_correct": True,
    },
}

# Form validation test data
FORM_VALIDATION_TEST_DATA = {
    "valid_registration": {
        "username": "newuser123",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "first_name": "New",
        "last_name": "User",
        "email": "newuser@example.com",
        "time_zone": "America/New_York",
    },
    "invalid_registration_cases": [
        {
            "name": "missing_username",
            "data": {
                "password": "pass123",
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            },
            "error": "required",
        },
        {
            "name": "short_password",
            "data": {
                "username": "test",
                "password": "short",
                "confirm_password": "short",
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            },
            "error": "8 characters",
        },
        {
            "name": "password_mismatch",
            "data": {
                "username": "test",
                "password": "password123",
                "confirm_password": "different123",
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            },
            "error": "match",
        },
    ],
}

# API endpoint test data
API_TEST_RESPONSES = {
    "sessions_data": {
        "sessions": [
            {
                "session_id": 1,
                "name": "Austin Session",
                "path": "austin-session",
                "city": "Austin",
                "state": "TX",
                "country": "USA",
                "termination_date": None,
            },
            {
                "session_id": 2,
                "name": "Boston Session",
                "path": "boston-session",
                "city": "Boston",
                "state": "MA",
                "country": "USA",
                "termination_date": None,
            },
        ]
    },
    "username_availability": {
        "available": {"available": True},
        "taken": {"available": False},
    },
    "api_success": {"success": True},
    "api_failure": {"success": False, "error": "Something went wrong"},
}
