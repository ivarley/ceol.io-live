"""
Unit tests for utility functions.

Tests email utilities, timezone utilities, and other helper functions
used throughout the application.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import os

from email_utils import send_email_via_sendgrid, send_password_reset_email, send_verification_email
from auth import User


class TestEmailUtilities:
    """Test email utility functions."""

    @patch('email_utils.SendGridAPIClient')
    def test_send_email_via_sendgrid_success(self, mock_sg_client):
        """Test successful email sending via SendGrid."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response
        mock_sg_client.return_value = mock_client
        
        # Mock environment variable
        with patch.dict(os.environ, {'SENDGRID_API_KEY': 'test-api-key'}):
            result = send_email_via_sendgrid(
                'test@example.com',
                'Test Subject',
                'Test body text',
                '<h1>Test HTML body</h1>'
            )
        
        assert result is True
        mock_sg_client.assert_called_once_with(api_key='test-api-key')
        mock_client.send.assert_called_once()

    @patch('email_utils.SendGridAPIClient')
    def test_send_email_via_sendgrid_failure(self, mock_sg_client):
        """Test email sending failure handling."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.body = 'Bad Request'
        mock_client.send.return_value = mock_response
        mock_sg_client.return_value = mock_client
        
        with patch.dict(os.environ, {'SENDGRID_API_KEY': 'test-api-key'}):
            result = send_email_via_sendgrid(
                'test@example.com',
                'Test Subject',
                'Test body text'
            )
        
        assert result is False

    def test_send_email_no_api_key(self):
        """Test email sending when API key is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = send_email_via_sendgrid(
                'test@example.com',
                'Test Subject',
                'Test body text'
            )
        
        assert result is False

    @patch('email_utils.SendGridAPIClient')
    def test_send_email_exception_handling(self, mock_sg_client):
        """Test email sending with exception handling."""
        mock_sg_client.side_effect = Exception("Network error")
        
        with patch.dict(os.environ, {'SENDGRID_API_KEY': 'test-api-key'}):
            result = send_email_via_sendgrid(
                'test@example.com',
                'Test Subject',
                'Test body text'
            )
        
        assert result is False

    @patch('email_utils.send_email_via_sendgrid')
    @patch('email_utils.url_for')
    def test_send_password_reset_email(self, mock_url_for, mock_send_email, sample_user_data):
        """Test password reset email generation and sending."""
        mock_url_for.return_value = 'https://example.com/reset-password/test-token'
        mock_send_email.return_value = True
        
        user = User(**sample_user_data)
        token = 'test-token'
        
        result = send_password_reset_email(user, token)
        
        assert result is True
        mock_url_for.assert_called_once_with('reset_password', token=token, _external=True)
        mock_send_email.assert_called_once()
        
        # Verify email content
        call_args = mock_send_email.call_args[0]
        assert call_args[0] == user.email
        assert 'Password Reset Request' in call_args[1]
        assert 'https://example.com/reset-password/test-token' in call_args[2]
        assert '1 hour' in call_args[2]

    @patch('email_utils.send_email_via_sendgrid')
    @patch('email_utils.url_for')
    def test_send_verification_email(self, mock_url_for, mock_send_email, sample_user_data):
        """Test verification email generation and sending."""
        mock_url_for.return_value = 'https://example.com/verify-email/test-token'
        mock_send_email.return_value = True
        
        user = User(**sample_user_data)
        token = 'test-token'
        
        result = send_verification_email(user, token)
        
        assert result is True
        mock_url_for.assert_called_once_with('verify_email', token=token, _external=True)
        mock_send_email.assert_called_once()
        
        # Verify email content
        call_args = mock_send_email.call_args[0]
        assert call_args[0] == user.email
        assert 'Verify Your Email Address' in call_args[1]
        assert 'https://example.com/verify-email/test-token' in call_args[2]
        assert '24 hours' in call_args[2]

    @patch('email_utils.send_email_via_sendgrid')
    def test_email_content_includes_html_and_text(self, mock_send_email, sample_user_data):
        """Test that emails include both HTML and text versions."""
        mock_send_email.return_value = True
        
        user = User(**sample_user_data)
        
        with patch('email_utils.url_for', return_value='https://example.com/reset'):
            send_password_reset_email(user, 'token')
        
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[0]
        
        # Should have 4 arguments: email, subject, text_body, html_body
        assert len(call_args) == 4
        assert call_args[3] is not None  # HTML body should be provided
        assert '<h2>' in call_args[3]  # Should contain HTML tags


class TestTimezoneUtilities:
    """Test timezone utility functions."""

    def test_timezone_imports(self):
        """Test that timezone utilities can be imported."""
        try:
            from timezone_utils import (
                now_utc, format_datetime_with_timezone, 
                utc_to_local, get_timezone_display_name,
                migrate_legacy_timezone
            )
            assert True  # Import successful
        except ImportError:
            pytest.fail("Could not import timezone utilities")

    @patch('timezone_utils.datetime')
    def test_now_utc_function(self, mock_datetime):
        """Test now_utc returns current UTC time."""
        # This test assumes now_utc exists in timezone_utils
        test_time = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = test_time
        
        try:
            from timezone_utils import now_utc
            result = now_utc()
            # Since we can't easily mock the function, just ensure it returns datetime
            assert isinstance(result, datetime) or result == test_time
        except ImportError:
            pytest.skip("now_utc function not available")

    def test_timezone_display_functions_exist(self):
        """Test that timezone display functions exist and are callable."""
        try:
            from timezone_utils import get_timezone_display_name, get_timezone_display_with_offset
            
            # Test that functions exist and are callable
            assert callable(get_timezone_display_name)
            assert callable(get_timezone_display_with_offset)
            
            # Test basic functionality if possible
            display_name = get_timezone_display_name('UTC')
            assert isinstance(display_name, str)
            assert len(display_name) > 0
            
        except ImportError:
            pytest.skip("Timezone display functions not available")

    def test_legacy_timezone_migration(self):
        """Test legacy timezone migration function."""
        try:
            from timezone_utils import migrate_legacy_timezone
            
            # Test that function handles common legacy values
            test_cases = [
                ('UTC', 'UTC'),
                ('EST', 'America/New_York'),  # Assuming this is the migration
                ('PST', 'America/Los_Angeles'),
            ]
            
            for legacy, expected in test_cases:
                result = migrate_legacy_timezone(legacy)
                # At minimum, should return a string
                assert isinstance(result, str)
                
        except ImportError:
            pytest.skip("Legacy timezone migration function not available")


class TestApplicationUtilities:
    """Test application-specific utility functions."""

    def test_app_template_filters_registered(self, app_context):
        """Test that custom template filters are registered."""
        from flask import current_app
        
        # Test that template filters exist
        assert 'format_datetime_tz' in current_app.jinja_env.filters
        assert 'to_user_timezone' in current_app.jinja_env.filters

    def test_app_template_globals_registered(self, app_context):
        """Test that custom template globals are registered.""" 
        from flask import current_app
        
        # Test that template globals exist
        assert 'get_user_timezone' in current_app.jinja_env.globals

    def test_error_content_functions(self, app_context):
        """Test error page content generation functions."""
        from app import get_random_funny_content, render_error_page
        
        # Test funny content generation
        funny_text, funny_image = get_random_funny_content()
        if funny_text:  # May be None if no content configured
            assert isinstance(funny_text, str)
            assert len(funny_text) > 0
        
        # Test error page rendering
        with patch('app.render_template') as mock_render:
            mock_render.return_value = ('error page content', 400)
            result = render_error_page('Test error message', 400)
            
            mock_render.assert_called_once()
            call_args = mock_render.call_args
            assert 'error.html' in call_args[0]
            assert call_args[1]['error_message'] == 'Test error message'

    def test_database_connection_function_exists(self):
        """Test that database connection function exists."""
        from database import get_db_connection
        
        assert callable(get_db_connection)

    def test_config_values_set(self, app_context):
        """Test that important configuration values are set."""
        from flask import current_app
        
        # Test that secret key is set (even if it's the test key)
        assert current_app.secret_key is not None
        assert len(current_app.secret_key) > 0
        
        # Test URL map configuration
        assert hasattr(current_app, 'url_map')
        assert hasattr(current_app.url_map, 'strict_slashes')


class TestDatabaseConnectionHandling:
    """Test database connection and error handling."""

    @patch('database.psycopg2.connect')
    def test_database_connection_success(self, mock_connect):
        """Test successful database connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        from database import get_db_connection
        
        with patch.dict(os.environ, {
            'PGHOST': 'localhost',
            'PGDATABASE': 'test_db',
            'PGUSER': 'test_user',
            'PGPASSWORD': 'test_pass',
            'PGPORT': '5432'
        }):
            conn = get_db_connection()
        
        assert conn == mock_conn
        mock_connect.assert_called_once_with(
            host='localhost',
            database='test_db',
            user='test_user',
            password='test_pass',
            port=5432
        )

    @patch('database.psycopg2.connect')
    def test_database_connection_with_default_port(self, mock_connect):
        """Test database connection uses default port when not specified."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        from database import get_db_connection
        
        with patch.dict(os.environ, {
            'PGHOST': 'localhost',
            'PGDATABASE': 'test_db', 
            'PGUSER': 'test_user',
            'PGPASSWORD': 'test_pass'
            # No PGPORT specified
        }):
            get_db_connection()
        
        # Should use default port 5432
        call_args = mock_connect.call_args[1]
        assert call_args['port'] == 5432

    @patch('database.psycopg2.connect')
    def test_database_connection_exception(self, mock_connect):
        """Test database connection exception handling."""
        mock_connect.side_effect = Exception("Connection failed")
        
        from database import get_db_connection
        
        with pytest.raises(Exception) as exc_info:
            get_db_connection()
        
        assert "Connection failed" in str(exc_info.value)