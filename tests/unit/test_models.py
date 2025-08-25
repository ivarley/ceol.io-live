"""
Unit tests for database models and business logic.

Tests the User model, database utilities, and core business logic functions
without requiring actual database connections.
"""

import pytest
import bcrypt
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from database import normalize_apostrophes, save_to_history, find_matching_tune
from timezone_utils import now_utc

from auth import User, create_session, cleanup_expired_sessions, generate_password_reset_token


class TestUser:
    """Test the User model class."""

    def test_user_initialization(self, sample_user_data):
        """Test User object initialization with all parameters."""
        user = User(**sample_user_data)
        
        assert user.user_id == sample_user_data['user_id']
        assert user.person_id == sample_user_data['person_id']
        assert user.username == sample_user_data['username']
        assert user.email == sample_user_data['email']
        assert user.is_active == sample_user_data['is_active']
        assert user.is_system_admin == sample_user_data['is_system_admin']
        assert user.timezone == sample_user_data['timezone']
        assert user.email_verified == sample_user_data['email_verified']

    def test_user_get_id(self, sample_user_data):
        """Test User.get_id() returns string representation of user_id."""
        user = User(**sample_user_data)
        assert user.get_id() == str(sample_user_data['user_id'])

    def test_user_is_active_property(self, sample_user_data):
        """Test is_active property works correctly."""
        # Test active user
        user = User(**sample_user_data)
        assert user.is_active is True
        
        # Test inactive user
        inactive_data = sample_user_data.copy()
        inactive_data['is_active'] = False
        inactive_user = User(**inactive_data)
        assert inactive_user.is_active is False

    @patch('auth.get_db_connection')
    def test_get_by_id_success(self, mock_get_conn, sample_user_data):
        """Test User.get_by_id() with valid user ID."""
        # Setup mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock fetchone to return user data tuple
        user_tuple = (
            sample_user_data['user_id'],
            sample_user_data['person_id'], 
            sample_user_data['username'],
            sample_user_data['is_active'],
            sample_user_data['is_system_admin'],
            sample_user_data['timezone'],
            sample_user_data['email_verified'],
            sample_user_data['first_name'],
            sample_user_data['last_name'],
            sample_user_data['email'],
            sample_user_data['auto_save_tunes']
        )
        mock_cursor.fetchone.return_value = user_tuple
        
        # Test the method
        user = User.get_by_id(sample_user_data['user_id'])
        
        # Verify database query
        mock_cursor.execute.assert_called_once()
        assert 'SELECT ua.user_id' in mock_cursor.execute.call_args[0][0]
        assert mock_cursor.execute.call_args[0][1] == (sample_user_data['user_id'],)
        
        # Verify returned user object
        assert user is not None
        assert user.user_id == sample_user_data['user_id']
        assert user.username == sample_user_data['username']
        assert user.email == sample_user_data['email']

    @patch('auth.get_db_connection')
    def test_get_by_id_not_found(self, mock_get_conn):
        """Test User.get_by_id() returns None for non-existent user."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchone.return_value = None
        
        user = User.get_by_id(999)
        assert user is None

    @patch('auth.get_db_connection')
    def test_get_by_username_success(self, mock_get_conn, sample_user_data_with_password):
        """Test User.get_by_username() with valid username."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Include hashed_password in the tuple
        user_tuple = (
            sample_user_data_with_password['user_id'],
            sample_user_data_with_password['person_id'],
            sample_user_data_with_password['username'],
            sample_user_data_with_password['hashed_password'],
            sample_user_data_with_password['is_active'],
            sample_user_data_with_password['is_system_admin'],
            sample_user_data_with_password['timezone'],
            sample_user_data_with_password['email_verified'],
            sample_user_data_with_password['first_name'],
            sample_user_data_with_password['last_name'],
            sample_user_data_with_password['email'],
            sample_user_data_with_password['auto_save_tunes']
        )
        mock_cursor.fetchone.return_value = user_tuple
        
        user = User.get_by_username(sample_user_data_with_password['username'])
        
        assert user is not None
        assert user.username == sample_user_data_with_password['username']
        assert hasattr(user, 'hashed_password')

    def test_check_password_valid(self, sample_user_data_with_password):
        """Test password checking with valid password."""
        user_data = sample_user_data_with_password.copy()
        hashed_password = user_data.pop('hashed_password')
        user = User(**user_data)
        user.hashed_password = hashed_password
        
        # The sample password for the hash is 'password123'
        assert user.check_password('password123') is True

    def test_check_password_invalid(self, sample_user_data_with_password):
        """Test password checking with invalid password."""
        user_data = sample_user_data_with_password.copy()
        hashed_password = user_data.pop('hashed_password')
        user = User(**user_data)
        user.hashed_password = hashed_password
        
        assert user.check_password('wrongpassword') is False

    @patch('auth.get_db_connection')
    @patch('auth.bcrypt.hashpw')
    def test_create_user(self, mock_hashpw, mock_get_conn, sample_user_data):
        """Test User.create_user() method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchone.return_value = (123,)  # Mock returned user_id
        mock_hashpw.return_value.decode.return_value = 'hashed_password'
        
        user_id = User.create_user(
            username='newuser',
            password='password123',
            person_id=42,
            timezone='UTC',
            user_email='new@example.com'
        )
        
        assert user_id == 123
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestAuthUtilities:
    """Test authentication utility functions."""

    @patch('auth.get_db_connection')
    @patch('auth.secrets.token_urlsafe')
    @patch('auth.now_utc')
    def test_create_session(self, mock_now, mock_token, mock_get_conn):
        """Test session creation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_token.return_value = 'test-session-token'
        mock_now.return_value = now_utc().replace(year=2023, month=8, day=15, hour=12, minute=0, second=0, microsecond=0)
        
        session_id = create_session(
            user_id=1,
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0'
        )
        
        assert session_id == 'test-session-token'
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('auth.get_db_connection')
    @patch('auth.now_utc')
    def test_cleanup_expired_sessions(self, mock_now, mock_get_conn):
        """Test cleanup of expired sessions."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_now.return_value = now_utc().replace(year=2023, month=8, day=15, hour=12, minute=0, second=0, microsecond=0)
        
        cleanup_expired_sessions()
        
        mock_cursor.execute.assert_called_once_with(
            'DELETE FROM user_session WHERE expires_at < %s',
            (now_utc().replace(year=2023, month=8, day=15, hour=12, minute=0, second=0, microsecond=0),)
        )
        mock_conn.commit.assert_called_once()

    def test_generate_password_reset_token(self):
        """Test password reset token generation."""
        token = generate_password_reset_token()
        assert isinstance(token, str)
        assert len(token) > 20  # URL-safe tokens are typically longer


class TestDatabaseUtilities:
    """Test database utility functions."""

    def test_normalize_apostrophes(self):
        """Test apostrophe normalization function."""
        # Test with various smart quotes and apostrophes
        test_cases = [
            ("Don't Stop", "Don't Stop"),  # Regular apostrophe should stay
            ("Don\u2019t Stop", "Don't Stop"),  # Smart apostrophe should be normalized
            ("Don\u2018t Stop", "Don't Stop"),  # Another smart apostrophe variant
            ("\u201cHello\u201d", "\"Hello\""),      # Smart quotes should be normalized
            ("\u201dWorld\u201c", "\"World\""),      # Another smart quote variant
            ("", ""),                      # Empty string
            (None, None),                  # None should stay None
        ]
        
        for input_text, expected in test_cases:
            result = normalize_apostrophes(input_text)
            assert result == expected, f"Failed for input: {input_text}"

    def test_save_to_history_session(self, mock_db_connection):
        """Test saving session data to history table."""
        cursor = mock_db_connection['cursor']
        
        save_to_history(cursor, 'session', 'UPDATE', 123, 'test_user')
        
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        assert 'INSERT INTO session_history' in call_args[0]
        assert call_args[1] == ('UPDATE', 'test_user', 123)

    def test_save_to_history_user_account(self, mock_db_connection):
        """Test saving user account data to history table."""
        cursor = mock_db_connection['cursor']
        
        save_to_history(cursor, 'user_account', 'DELETE', 456, 'admin_user')
        
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        assert 'INSERT INTO user_account_history' in call_args[0]
        assert call_args[1] == ('DELETE', 'admin_user', 456)

    def test_save_to_history_session_tune(self, mock_db_connection):
        """Test saving session_tune data to history table with composite key."""
        cursor = mock_db_connection['cursor']
        
        save_to_history(cursor, 'session_tune', 'UPDATE', (123, 456), 'test_user')
        
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        assert 'INSERT INTO session_tune_history' in call_args[0]
        assert call_args[1] == ('UPDATE', 'test_user', 123, 456)

    def test_find_matching_tune_exact_alias_match(self, mock_db_connection):
        """Test finding tune by exact session alias match."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [(1001,)],  # session_tune alias match
        ]
        
        tune_id, final_name, error = find_matching_tune(cursor, 1, "Test Reel")
        
        assert tune_id == 1001
        assert final_name == "Test Reel"
        assert error is None
        
        # Should query session_tune table first
        assert cursor.execute.call_count == 1
        call_args = cursor.execute.call_args[0]
        assert 'session_tune' in call_args[0]
        assert 'LOWER(alias) = LOWER(%s)' in call_args[0]

    def test_find_matching_tune_multiple_aliases_error(self, mock_db_connection):
        """Test error handling for multiple alias matches."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [(1001,), (1002,)],  # Multiple session_tune matches
        ]
        
        tune_id, final_name, error = find_matching_tune(cursor, 1, "Test Reel")
        
        assert tune_id is None
        assert final_name == "Test Reel"
        assert "Multiple tunes found" in error

    def test_find_matching_tune_by_tune_name(self, mock_db_connection):
        """Test finding tune by name in tune table."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [],  # No session_tune alias match
            [],  # No session_tune_alias match  
            [(1003, "The Test Reel")],  # tune table match
        ]
        
        tune_id, final_name, error = find_matching_tune(cursor, 1, "Test Reel")
        
        assert tune_id == 1003
        assert final_name == "The Test Reel"
        assert error is None

    def test_find_matching_tune_with_the_prefix(self, mock_db_connection):
        """Test finding tune with 'The' prefix handling."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [],  # No session_tune alias match
            [],  # No session_tune_alias match
            [(1004, "The Big Reel")],  # tune table match with "The"
        ]
        
        tune_id, final_name, error = find_matching_tune(cursor, 1, "Big Reel")
        
        assert tune_id == 1004
        assert final_name == "The Big Reel"
        assert error is None
        
        # Should have tried flexible "The" matching
        call_args = cursor.execute.call_args[0]
        assert "LOWER('The ' || %s)" in call_args[0] or "LOWER(name) = LOWER('The ' || %s)" in call_args[0]

    def test_find_matching_tune_no_match(self, mock_db_connection):
        """Test when no tune matches are found."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [],  # No session_tune alias match
            [],  # No session_tune_alias match
            [],  # No tune table match
        ]
        
        tune_id, final_name, error = find_matching_tune(cursor, 1, "Nonexistent Tune")
        
        assert tune_id is None
        assert final_name == "Nonexistent Tune"
        assert error is None

    def test_find_matching_tune_normalize_apostrophes(self, mock_db_connection):
        """Test that apostrophes are normalized in tune search."""
        cursor = mock_db_connection['cursor']
        cursor.fetchall.side_effect = [
            [(1005,)],  # session_tune alias match
        ]
        
        # Use smart apostrophe in input
        tune_id, final_name, error = find_matching_tune(cursor, 1, "O'Brien's Reel")
        
        assert tune_id == 1005
        # Should have normalized the apostrophe in the query
        call_args = cursor.execute.call_args[0]
        assert call_args[1] == (1, "O'Brien's Reel")  # Regular apostrophe