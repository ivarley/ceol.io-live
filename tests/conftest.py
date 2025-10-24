"""
Test configuration and fixtures for Flask testing suite.

This file contains shared fixtures and configuration for all tests.
"""

import os
import sys
import tempfile
import pytest
import psycopg2
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add project root to Python path so we can import app modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set test environment before importing app
os.environ["FLASK_ENV"] = "testing"
os.environ["FLASK_SESSION_SECRET_KEY"] = "test-secret-key"
os.environ["PGHOST"] = "localhost"
os.environ["PGDATABASE"] = "ceol_test"
os.environ["PGUSER"] = "test_user"
os.environ["PGPASSWORD"] = "test_password"
os.environ["PGPORT"] = "5432"
os.environ["SENDGRID_API_KEY"] = "test-sendgrid-key"
os.environ["MAIL_DEFAULT_SENDER"] = "test@ceol.io"

from app import app
from database import get_db_connection
from auth import User


@pytest.fixture(scope="session")
def db_setup():
    """Set up test database schema once per test session."""
    # This would typically create test database tables
    # For now, assume test database exists with same schema
    yield
    # Cleanup would go here


@pytest.fixture
def db_conn():
    """Provide a database connection for tests."""
    conn = get_db_connection()
    # Start a transaction but don't commit it - let rollback clean up
    conn.autocommit = False
    yield conn
    # Always rollback to undo any changes made during the test
    try:
        conn.rollback()
    except Exception:
        pass  # Connection might already be closed
    conn.close()


@pytest.fixture
def db_cursor(db_conn):
    """Provide a database cursor for tests."""
    cursor = db_conn.cursor()
    yield cursor
    cursor.close()


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["LOGIN_DISABLED"] = False

    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def app_context():
    """Provide Flask application context."""
    with app.app_context():
        yield app


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests."""
    with patch("database.get_db_connection") as mock_conn:
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        yield {
            "connection": mock_connection,
            "cursor": mock_cursor,
            "get_connection": mock_conn,
        }


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    with patch("email_utils.SendGridAPIClient") as mock_sg:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response
        mock_sg.return_value = mock_client
        yield mock_sg


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "user_id": 1,
        "person_id": 2,  # Match the sample_person_data person_id for self check-in tests
        "username": "testuser",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_system_admin": True,
        "timezone": "America/New_York",
        "email_verified": True,
        "auto_save_tunes": False,
    }


@pytest.fixture
def sample_user_data_with_password():
    """Sample user data including hashed password for database tests."""
    return {
        "user_id": 1,
        "person_id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "hashed_password": "$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im",  # 'password123'
        "is_active": True,
        "is_system_admin": False,
        "timezone": "America/New_York",
        "email_verified": True,
        "auto_save_tunes": False,
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        "session_id": 1,
        "name": "Test Session",
        "path": "test-session",
        "city": "Austin",
        "state": "TX",
        "country": "USA",
        "location_name": "Test Venue",
        "location_street": "123 Main St",
        "location_website": "https://testvenue.com",
        "location_phone": "555-123-4567",
        "timezone": "America/Chicago",
        "initiation_date": datetime(2023, 1, 1),
        "termination_date": None,
        "recurrence": "weekly",
        "comments": "Test session for music lovers",
        "unlisted_address": False,
    }


@pytest.fixture
def sample_tune_data():
    """Sample tune data for testing."""
    return {
        "tune_id": 1001,
        "name": "The Test Reel",
        "tune_type": "reel",
        "tunebook_count_cached": 42,
        "tunebook_count_cached_date": datetime(2023, 6, 1),
    }


@pytest.fixture
def sample_session_instance_data():
    """Sample session instance data for testing."""
    return {
        "session_instance_id": 1,
        "session_id": 1,
        "date": datetime(2023, 8, 15).date(),
        "start_time": datetime(2023, 8, 15, 19, 0),
        "end_time": datetime(2023, 8, 15, 22, 0),
        "is_cancelled": False,
        "comments": "Great session tonight!",
        "location_override": None,
        "log_complete_date": None,
    }


@pytest.fixture
def sample_person_data():
    """Sample person data for testing."""
    return {
        "person_id": 2,
        "first_name": "Test",
        "last_name": "Person",
        "email": "testperson@example.com",
    }


@pytest.fixture
def sample_regular_attendee():
    """Sample regular attendee data for testing."""
    return {
        "person_id": 3,
        "first_name": "Regular",
        "last_name": "Player",
        "email": "regular@example.com",
        "is_regular": True,
        "instruments": ["fiddle", "tin whistle"],
    }


@pytest.fixture
def sample_person_no_instruments():
    """Sample person data with no instruments for testing."""
    return {
        "person_id": 4,
        "first_name": "No",
        "last_name": "Instruments",
        "email": "noinstruments@example.com",
        "instruments": [],
    }


@pytest.fixture
def sample_person_with_instruments():
    """Sample person data with instruments for testing."""
    return {
        "person_id": 5,
        "first_name": "Has",
        "last_name": "Instruments",
        "email": "hasinstruments@example.com",
        "instruments": ["fiddle", "tin whistle"],
    }


@pytest.fixture
def sample_person_with_multiple_instruments():
    """Sample person data with multiple instruments for testing."""
    return {
        "person_id": 6,
        "first_name": "Many",
        "last_name": "Instruments",
        "email": "manyinstruments@example.com",
        "instruments": ["zither", "bodhrán", "accordion", "flute"],
    }


@pytest.fixture
def authenticated_non_admin_user(client, sample_user_data):
    """Create an authenticated non-admin user session. This is the same as authenticated_user."""
    # This fixture is identical to authenticated_user since sample_user_data already has is_system_admin=False
    class AuthenticatedUserContext:
        def __init__(self, client, user_data):
            self.client = client
            self.user_data = user_data
            self.user = None
            self.mock_get_user = None
            # Set attributes that tests expect to be available outside context
            self.person_id = user_data["person_id"]
            self.user_id = user_data["user_id"]
            self.is_system_admin = user_data.get("is_system_admin", False)

        def __enter__(self):
            self.mock_get_user = patch("auth.User.get_by_id")
            mock_get_user = self.mock_get_user.start()
            self.user = User(**self.user_data)
            mock_get_user.return_value = self.user
            
            # Add attributes that tests expect
            self.person_id = self.user_data["person_id"]
            self.user_id = self.user_data["user_id"]

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_data["user_id"])
                sess["_fresh"] = True
                sess["is_system_admin"] = self.user_data["is_system_admin"]
                sess["admin_session_ids"] = []
                
            return self.user
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.mock_get_user:
                self.mock_get_user.stop()
    
    return AuthenticatedUserContext(client, sample_user_data)


@pytest.fixture  
def sample_person_not_attending():
    """Sample person data who is not attending for testing."""
    return {
        "person_id": 7,
        "first_name": "Not",
        "last_name": "Attending", 
        "email": "notattending@example.com",
    }


@pytest.fixture
def authenticated_user(client, sample_user_data):
    """Create an authenticated user session."""
    class AuthenticatedUserContext:
        def __init__(self, client, user_data):
            self.client = client
            self.user_data = user_data
            self.user = None
            self.mock_get_user = None
            # Set attributes that tests expect to be available outside context
            self.person_id = user_data["person_id"]
            self.user_id = user_data["user_id"]
            self.is_system_admin = user_data.get("is_system_admin", False)

        def __enter__(self):
            self.mock_get_user = patch("auth.User.get_by_id")
            mock_get_user = self.mock_get_user.start()
            self.user = User(**self.user_data)
            mock_get_user.return_value = self.user
            
            # Add attributes that tests expect
            self.person_id = self.user_data["person_id"]
            self.user_id = self.user_data["user_id"]

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_data["user_id"])
                sess["_fresh"] = True
                sess["is_system_admin"] = self.user_data["is_system_admin"]
                sess["admin_session_ids"] = []
                
            return self.user
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.mock_get_user:
                self.mock_get_user.stop()
    
    return AuthenticatedUserContext(client, sample_user_data)


@pytest.fixture
def admin_user(client, sample_user_data):
    """Create an authenticated admin user session."""
    admin_data = sample_user_data.copy()
    admin_data["is_system_admin"] = True
    admin_data["username"] = "admin"
    admin_data["user_id"] = 2

    class AuthenticatedAdminContext:
        def __init__(self, client, user_data):
            self.client = client
            self.user_data = user_data
            self.user = None
            self.mock_get_user = None
            # Set attributes that tests expect to be available outside context
            self.person_id = user_data["person_id"]
            self.user_id = user_data["user_id"]
            self.is_system_admin = user_data.get("is_system_admin", False)

        def __enter__(self):
            self.mock_get_user = patch("auth.User.get_by_id")
            mock_get_user = self.mock_get_user.start()
            self.user = User(**self.user_data)
            mock_get_user.return_value = self.user
            
            # Add attributes that tests expect
            self.person_id = self.user_data["person_id"]
            self.user_id = self.user_data["user_id"]

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_data["user_id"])
                sess["_fresh"] = True
                sess["is_system_admin"] = True
                sess["admin_session_ids"] = [1, 2, 3]
                
            return self.user
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.mock_get_user:
                self.mock_get_user.stop()
    
    return AuthenticatedAdminContext(client, admin_data)


@pytest.fixture
def authenticated_admin_user(client, sample_user_data):
    """Create an authenticated admin user session - alias for admin_user for compatibility."""
    # This is an alias for admin_user to maintain compatibility with existing tests
    admin_data = sample_user_data.copy()
    admin_data["is_system_admin"] = True
    admin_data["username"] = "admin"
    admin_data["user_id"] = 2

    class AuthenticatedAdminContext:
        def __init__(self, client, user_data):
            self.client = client
            self.user_data = user_data
            self.user = None
            self.mock_get_user = None
            # Set attributes that tests expect to be available outside context
            self.person_id = user_data["person_id"]
            self.user_id = user_data["user_id"]
            self.is_system_admin = user_data.get("is_system_admin", False)

        def __enter__(self):
            self.mock_get_user = patch("auth.User.get_by_id")
            mock_get_user = self.mock_get_user.start()
            self.user = User(**self.user_data)
            mock_get_user.return_value = self.user
            
            # Add attributes that tests expect
            self.person_id = self.user_data["person_id"]
            self.user_id = self.user_data["user_id"]

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_data["user_id"])
                sess["_fresh"] = True
                sess["is_system_admin"] = True
                sess["admin_session_ids"] = [1, 2, 3]
                
            return self.user
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.mock_get_user:
                self.mock_get_user.stop()
    
    return AuthenticatedAdminContext(client, admin_data)


@pytest.fixture
def authenticated_regular_user(client, sample_user_data, sample_regular_attendee):
    """Create an authenticated regular user session (non-admin)."""
    # Use regular attendee data to ensure proper person_id matching
    regular_data = sample_user_data.copy()
    regular_data["is_system_admin"] = False  # Explicitly ensure non-admin
    regular_data["username"] = "regular_user"
    regular_data["user_id"] = 3
    regular_data["person_id"] = sample_regular_attendee["person_id"]  # Use regular attendee person_id
    regular_data["first_name"] = sample_regular_attendee["first_name"]
    regular_data["last_name"] = sample_regular_attendee["last_name"]

    class AuthenticatedUserContext:
        def __init__(self, client, user_data):
            self.client = client
            self.user_data = user_data
            self.user = None
            self.mock_get_user = None
            # Set attributes that tests expect to be available outside context
            self.person_id = user_data["person_id"]
            self.user_id = user_data["user_id"]
            self.is_system_admin = user_data.get("is_system_admin", False)

        def __enter__(self):
            self.mock_get_user = patch("auth.User.get_by_id")
            mock_get_user = self.mock_get_user.start()
            self.user = User(**self.user_data)
            mock_get_user.return_value = self.user
            
            # Add attributes that tests expect
            self.person_id = self.user_data["person_id"]
            self.user_id = self.user_data["user_id"]

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_data["user_id"])
                sess["_fresh"] = True
                sess["is_system_admin"] = self.user_data["is_system_admin"]
                sess["admin_session_ids"] = []
                
            return self.user
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.mock_get_user:
                self.mock_get_user.stop()
    
    return AuthenticatedUserContext(client, regular_data)


@pytest.fixture
def session_with_multiple_instances(sample_session_data):
    """Create session data with multiple instances for testing."""
    return {
        "session_id": sample_session_data["session_id"],
        "instances": [
            {
                "session_instance_id": 1,
                "date": "2023-08-15",
                "start_time": "19:00",
                "end_time": "22:00"
            },
            {
                "session_instance_id": 2, 
                "date": "2023-08-22",
                "start_time": "19:00",
                "end_time": "22:00"
            },
            {
                "session_instance_id": 3,
                "date": "2023-08-29", 
                "start_time": "19:00",
                "end_time": "22:00"
            }
        ]
    }


@pytest.fixture
def multiple_sessions_data(sample_session_data):
    """Create multiple session data for testing cross-session functionality."""
    return {
        "sessions": [
            sample_session_data,
            {
                "session_id": sample_session_data["session_id"] + 1,
                "name": "Another Test Session",
                "path": "another-test-session",
                "city": "Boston",
                "state": "MA",
                "country": "USA"
            }
        ]
    }


@pytest.fixture
def mock_thesession_api():
    """Mock external thesession.org API responses."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tune": {
                "id": 1001,
                "name": "The Test Reel",
                "type": "reel",
                "tunebooks": 42,
            }
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture(autouse=True)
def cleanup_database_state():
    """Ensure clean database state for each test."""
    yield
    # This would clean up any test data created during tests
    # For now, we rely on transaction rollback in db_conn fixture


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "functional: Functional tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")


@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing."""
    from freezegun import freeze_time as ft

    test_time = datetime(2023, 8, 15, 12, 0, 0)
    with ft(test_time) as frozen_time:
        yield frozen_time


@pytest.fixture
def session_instance_user_not_associated(sample_session_data):
    """Session instance that the authenticated user is NOT associated with."""
    # Create a separate session instance that the user isn't associated with
    return {
        "session_instance_id": 999,  # Different from main test session instance
        "session_id": 999,  # Different from main test session
        "date": "2023-09-01",
        "comments": "Test session user is not associated with"
    }


@pytest.fixture  
def session_instance_with_user_attending(sample_session_instance_data, authenticated_user):
    """Session instance where the authenticated user is already attending."""
    # Return the same session instance, but the test should check in the user first
    return sample_session_instance_data


@pytest.fixture
def multiple_session_instances(sample_session_data):
    """Multiple session instances for testing permission inheritance."""
    session_id = sample_session_data['session_id']
    return {
        "instances": [
            {
                "session_instance_id": sample_session_data.get('session_instance_id', 1),
                "session_id": session_id,
                "date": "2023-08-15",
                "comments": "First instance"
            },
            {
                "session_instance_id": 998,
                "session_id": session_id, 
                "date": "2023-08-22",
                "comments": "Second instance"
            }
        ]
    }


@pytest.fixture
def different_session_instance():
    """Session instance from a completely different session for isolation testing."""
    return {
        "session_instance_id": 997,
        "session_id": 997,  # Different session entirely
        "date": "2023-09-01",
        "comments": "Different session for isolation testing"
    }
