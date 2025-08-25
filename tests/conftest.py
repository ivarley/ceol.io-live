"""
Test configuration and fixtures for Flask testing suite.

This file contains shared fixtures and configuration for all tests.
"""

import os
import tempfile
import pytest
import psycopg2
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Set test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['FLASK_SESSION_SECRET_KEY'] = 'test-secret-key'
os.environ['PGHOST'] = 'localhost'
os.environ['PGDATABASE'] = 'ceol_test'
os.environ['PGUSER'] = 'test_user'
os.environ['PGPASSWORD'] = 'test_password'
os.environ['PGPORT'] = '5432'
os.environ['SENDGRID_API_KEY'] = 'test-sendgrid-key'
os.environ['MAIL_DEFAULT_SENDER'] = 'test@ceol.io'

from app import app
from database import get_db_connection
from auth import User


@pytest.fixture(scope='session')
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
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = False
    
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
    with patch('database.get_db_connection') as mock_conn:
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection
        
        yield {
            'connection': mock_connection,
            'cursor': mock_cursor,
            'get_connection': mock_conn
        }


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    with patch('email_utils.SendGridAPIClient') as mock_sg:
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
        'user_id': 1,
        'person_id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'is_active': True,
        'is_system_admin': False,
        'timezone': 'America/New_York',
        'email_verified': True,
        'auto_save_tunes': False
    }

@pytest.fixture
def sample_user_data_with_password():
    """Sample user data including hashed password for database tests."""
    return {
        'user_id': 1,
        'person_id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'hashed_password': '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im',  # 'password123'
        'is_active': True,
        'is_system_admin': False,
        'timezone': 'America/New_York',
        'email_verified': True,
        'auto_save_tunes': False
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        'session_id': 1,
        'name': 'Test Session',
        'path': 'test-session',
        'city': 'Austin',
        'state': 'TX',
        'country': 'USA',
        'location_name': 'Test Venue',
        'location_street': '123 Main St',
        'location_website': 'https://testvenue.com',
        'location_phone': '555-123-4567',
        'timezone': 'America/Chicago',
        'initiation_date': datetime(2023, 1, 1),
        'termination_date': None,
        'recurrence': 'weekly',
        'comments': 'Test session for music lovers',
        'unlisted_address': False
    }


@pytest.fixture
def sample_tune_data():
    """Sample tune data for testing."""
    return {
        'tune_id': 1001,
        'name': 'The Test Reel',
        'tune_type': 'reel',
        'tunebook_count_cached': 42,
        'tunebook_count_cached_date': datetime(2023, 6, 1)
    }


@pytest.fixture
def sample_session_instance_data():
    """Sample session instance data for testing."""
    return {
        'session_instance_id': 1,
        'session_id': 1,
        'date': datetime(2023, 8, 15).date(),
        'start_time': datetime(2023, 8, 15, 19, 0),
        'end_time': datetime(2023, 8, 15, 22, 0),
        'is_cancelled': False,
        'comments': 'Great session tonight!',
        'location_override': None,
        'log_complete_date': None
    }


@pytest.fixture
def authenticated_user(client, sample_user_data):
    """Create an authenticated user session."""
    with patch('auth.User.get_by_username') as mock_get_user:
        user = User(**sample_user_data)
        mock_get_user.return_value = user
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(sample_user_data['user_id'])
            sess['_fresh'] = True
            sess['is_system_admin'] = sample_user_data['is_system_admin']
            sess['admin_session_ids'] = []
        
        yield user


@pytest.fixture
def admin_user(client, sample_user_data):
    """Create an authenticated admin user session."""
    admin_data = sample_user_data.copy()
    admin_data['is_system_admin'] = True
    admin_data['username'] = 'admin'
    admin_data['user_id'] = 2
    
    with patch('auth.User.get_by_username') as mock_get_user:
        user = User(**admin_data)
        mock_get_user.return_value = user
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_data['user_id'])
            sess['_fresh'] = True
            sess['is_system_admin'] = True
            sess['admin_session_ids'] = [1, 2, 3]
        
        yield user


@pytest.fixture
def mock_thesession_api():
    """Mock external thesession.org API responses."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'tune': {
                'id': 1001,
                'name': 'The Test Reel',
                'type': 'reel',
                'tunebooks': 42
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