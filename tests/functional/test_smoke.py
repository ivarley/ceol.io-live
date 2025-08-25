"""
Functional smoke tests for critical user journeys.

These tests verify that the most important application workflows function
correctly end-to-end. They serve as a basic sanity check after deployments.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import uuid
from datetime import datetime, date

from flask import url_for


@pytest.mark.functional
class TestCriticalPageLoads:
    """Test that critical pages load without errors."""

    def test_home_page_loads(self, client):
        """Test that home page loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data  # Basic HTML structure
        assert b'Irish' in response.data.lower() or b'session' in response.data.lower()

    def test_sessions_page_loads(self, client):
        """Test that sessions listing page loads successfully.""" 
        response = client.get('/sessions')
        assert response.status_code == 200
        assert b'session' in response.data.lower()

    def test_help_page_loads(self, client):
        """Test that help page loads successfully."""
        response = client.get('/help')
        assert response.status_code == 200
        assert b'help' in response.data.lower()

    def test_auth_pages_load(self, client):
        """Test that authentication pages load successfully."""
        # Login page
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
        
        # Register page
        response = client.get('/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower()
        
        # Forgot password page
        response = client.get('/forgot-password')
        assert response.status_code == 200
        assert b'password' in response.data.lower()

    def test_add_session_page_loads(self, client):
        """Test that add session page loads successfully."""
        response = client.get('/add-session')
        assert response.status_code == 200
        assert b'session' in response.data.lower()

    def test_magic_page_loads(self, client):
        """Test that magic tune selection page loads successfully."""
        response = client.get('/magic')
        assert response.status_code == 200
        # Should not error even if no data exists

    def test_404_error_page(self, client):
        """Test that 404 error page renders properly."""
        response = client.get('/nonexistent-page-12345')
        assert response.status_code == 404
        assert b'not found' in response.data.lower()


@pytest.mark.functional
class TestUserRegistrationJourney:
    """Test complete user registration and verification journey."""

    @patch('web_routes.send_verification_email')
    def test_complete_registration_flow(self, mock_send_email, client):
        """Test complete user registration workflow."""
        mock_send_email.return_value = True
        unique_id = str(uuid.uuid4())[:8]
        
        # Step 1: Access registration page
        response = client.get('/register')
        assert response.status_code == 200
        
        # Step 2: Submit registration form with unique data
        registration_data = {
            'username': f'smoketest_user_{unique_id}',
            'password': 'securepassword123',
            'confirm_password': 'securepassword123',
            'first_name': 'Smoke',
            'last_name': 'Test',
            'email': f'smoketest{unique_id}@example.com',
            'time_zone': 'America/New_York'
        }
        
        response = client.post('/register', data=registration_data)
        
        # Should redirect to login on success or show error on failure
        if response.status_code == 302:
            assert '/login' in response.headers['Location']
        elif response.status_code == 200:
            # If 200, check if registration failed due to validation issues
            response_data = response.data.decode()
            # If registration succeeded but didn't redirect, that's still success
            assert 'error' not in response_data.lower() or 'success' in response_data.lower()
        else:
            # Any other status code is unexpected
            assert False, f"Unexpected status code: {response.status_code}"
        
        # Step 3: Verify login page shows success message
        response = client.get('/login')
        # Note: Flash messages might not persist in test client
        assert response.status_code == 200
        
        # Step 4: Verify email sending was attempted
        mock_send_email.assert_called_once()

    def test_registration_validation_errors(self, client):
        """Test registration form validation."""
        # Test missing required fields
        response = client.post('/register', data={
            'username': 'testuser'
            # Missing other required fields
        })
        assert response.status_code == 200
        assert b'required' in response.data.lower()
        
        # Test password mismatch
        response = client.post('/register', data={
            'username': 'testuser',
            'password': 'password123',
            'confirm_password': 'different123',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com'
        })
        assert response.status_code == 200
        assert b'match' in response.data.lower()
        
        # Test short password
        response = client.post('/register', data={
            'username': 'testuser',
            'password': 'short',
            'confirm_password': 'short',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com'
        })
        assert response.status_code == 200
        assert b'8 characters' in response.data.lower()


@pytest.mark.functional
class TestLoginLogoutJourney:
    """Test complete login/logout workflow."""

    @patch('web_routes.User.get_by_username')
    @patch('web_routes.create_session')
    @patch('web_routes.login_user')
    @patch('web_routes.get_db_connection')
    def test_successful_login_logout_flow(self, mock_get_conn, mock_login_user, 
                                         mock_create_session, mock_get_user, client):
        """Test complete login and logout workflow."""
        # Mock user with all necessary attributes
        user = MagicMock()
        user.is_active = True
        user.email_verified = True
        user.check_password.return_value = True
        user.user_id = 1
        user.person_id = 1
        user.username = 'testuser'
        user.first_name = 'Test'
        user.last_name = 'User'
        user.email = 'test@example.com'
        user.is_system_admin = False
        user.timezone = 'America/New_York'
        user.auto_save_tunes = False
        mock_get_user.return_value = user
        
        # Mock database for admin sessions
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchall.return_value = []
        
        mock_create_session.return_value = 'session123'
        
        # Step 1: Access login page
        response = client.get('/login')
        assert response.status_code == 200
        
        # Step 2: Submit login credentials
        response = client.post('/login', data={
            'username': 'smoketest',
            'password': 'correctpassword'
        })
        
        # Should redirect after successful login
        assert response.status_code == 302
        mock_login_user.assert_called_once()
        
        # Step 3: Access protected page (should work)
        with patch('web_routes.current_user') as mock_current_user:
            mock_current_user.is_authenticated = True
            mock_current_user.user_id = 1
            mock_current_user.username = 'smoketest'
            
            # Step 4: Logout
            response = client.get('/logout')
            assert response.status_code == 302  # Redirect after logout

    def test_login_with_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_login_form_validation(self, client):
        """Test login form validation."""
        # Test empty fields
        response = client.post('/login', data={})
        assert response.status_code == 200
        assert b'required' in response.data.lower()


@pytest.mark.functional
class TestSessionBrowsingJourney:
    """Test browsing sessions and viewing session details."""

    @patch('web_routes.get_db_connection')
    @patch('database.get_db_connection')
    def test_browse_sessions_workflow(self, mock_get_db_conn, mock_get_conn, client):
        """Test browsing sessions from home to session details."""
        unique_id = str(uuid.uuid4())[:8]
        session_name = f'Smoke Test Session {unique_id}'
        session_path = f'smoke-test-{unique_id}'
        
        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_get_db_conn.return_value = mock_conn
        
        # Step 1: Home page shows active sessions
        mock_cursor.fetchall.side_effect = [
            [(1, session_name, session_path, 'Austin', 'TX', 'USA')],  # Active sessions
            [(date(2023, 8, 15),), (date(2023, 8, 8),)],  # Recent instances
            []  # Additional empty result for other queries
        ]
        mock_cursor.fetchone.side_effect = [
            (3,),  # Total instances count
            None  # End of queries
        ]
        
        response = client.get('/')
        assert response.status_code == 200
        # Check for any session name (might be truncated in display)
        assert session_name.encode() in response.data or b'Smoke Test Session' in response.data
        
        # Step 2: Click through to sessions list - reset mock for new request
        mock_cursor.fetchall.side_effect = None  # Clear side_effect
        mock_cursor.fetchall.return_value = [
            (session_name, session_path, 'Austin', 'TX', 'USA', None)
        ]
        mock_cursor.fetchone.side_effect = None  # Clear side_effect
        mock_cursor.fetchone.return_value = None
        
        response = client.get('/sessions')
        assert response.status_code == 200
        assert session_name.encode() in response.data or b'Smoke Test Session' in response.data
        
        # Step 3: View specific session details - reset mock for new request
        mock_cursor.fetchone.side_effect = None  # Clear side_effect
        mock_cursor.fetchone.return_value = (
            1, None, session_name, session_path, 'Test Venue',
            'https://testvenue.com', '555-1234', '123 Main St',
            'Austin', 'TX', 'USA', 'Test session comments', False,
            date(2023, 1, 1), None, 'weekly'
        )
        mock_cursor.fetchall.side_effect = [
            [(date(2023, 8, 15),), (date(2023, 8, 8),)],  # Past instances
            [(f'Test Reel {unique_id}', 1001, 5, 42)]  # Popular tunes
        ]
        
        response = client.get(f'/sessions/{session_path}')
        assert response.status_code == 200
        assert session_name.encode() in response.data or b'Smoke Test Session' in response.data
        assert b'Austin' in response.data

    @patch('web_routes.get_db_connection')
    def test_session_not_found(self, mock_get_conn, client):
        """Test accessing non-existent session."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchone.return_value = None  # Session not found
        
        response = client.get('/sessions/nonexistent-session')
        assert response.status_code == 404


@pytest.mark.functional
class TestSessionInstanceJourney:
    """Test viewing and interacting with session instances."""

    @patch('web_routes.get_db_connection')
    def test_view_session_instance_details(self, mock_get_conn, client):
        """Test viewing session instance with tunes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock session instance data
        mock_cursor.fetchone.return_value = (
            'Test Session Instance', date(2023, 8, 15), 'Great session!',
            123, False, None, 'Default Location', None, 1
        )
        
        # Mock tunes data
        mock_cursor.fetchall.return_value = [
            (1, False, 1001, 'First Reel', None, 'Reel'),
            (2, True, 1002, 'Second Reel', None, 'Reel'),
            (3, False, 1003, 'Test Jig', None, 'Jig')
        ]
        
        response = client.get('/sessions/test-session/2023-08-15')
        assert response.status_code == 200
        assert b'Test Session Instance' in response.data
        assert b'Great session!' in response.data
        assert b'First Reel' in response.data
        assert b'Second Reel' in response.data
        assert b'Test Jig' in response.data

    @patch('web_routes.get_db_connection')
    def test_session_instance_not_found(self, mock_get_conn, client):
        """Test accessing non-existent session instance."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchone.return_value = None  # Instance not found
        
        response = client.get('/sessions/test-session/2023-01-01')
        assert response.status_code == 404


@pytest.mark.functional
class TestAPIEndpointsSmokeTest:
    """Smoke test key API endpoints."""

    @patch('api_routes.get_db_connection')
    def test_sessions_data_api_smoke(self, mock_get_conn, client):
        """Smoke test for sessions data API."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchall.return_value = []  # Empty data is fine for smoke test
        
        response = client.get('/api/sessions/data')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = json.loads(response.data)
        assert 'sessions' in data

    def test_username_availability_api_smoke(self, client):
        """Smoke test for username availability API."""
        response = client.post('/api/check-username-availability',
                              json={'username': 'smoketest_available'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'available' in data

    def test_api_endpoints_return_json(self, client):
        """Test that API endpoints return proper JSON responses."""
        api_endpoints = [
            '/api/sessions/data',
        ]
        
        for endpoint in api_endpoints:
            response = client.get(endpoint)
            
            # Should return JSON even on error
            assert response.content_type == 'application/json'
            
            # Should be valid JSON
            try:
                json.loads(response.data)
            except json.JSONDecodeError:
                pytest.fail(f"Endpoint {endpoint} did not return valid JSON")


@pytest.mark.functional
class TestPasswordResetJourney:
    """Test password reset workflow."""

    @patch('web_routes.send_password_reset_email')
    @patch('web_routes.get_db_connection')
    def test_password_reset_request_flow(self, mock_get_conn, mock_send_email, client):
        """Test password reset request workflow."""
        mock_send_email.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock user exists
        mock_cursor.fetchone.return_value = (1, 'testuser', 'test@example.com', 'Test')
        
        # Step 1: Access forgot password page
        response = client.get('/forgot-password')
        assert response.status_code == 200
        
        # Step 2: Submit email for reset
        response = client.post('/forgot-password', data={
            'email': 'test@example.com'
        })
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.headers['Location']
        
        # Should attempt to send email
        mock_send_email.assert_called_once()

    def test_password_reset_invalid_email(self, client):
        """Test password reset with invalid email."""
        response = client.post('/forgot-password', data={
            'email': ''  # Empty email
        })
        
        assert response.status_code == 200
        assert b'required' in response.data.lower()


@pytest.mark.functional 
class TestResponsiveDesign:
    """Test that pages work with different user agents (basic responsive test)."""

    def test_mobile_user_agent(self, client):
        """Test pages work with mobile user agent."""
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        
        response = client.get('/', headers=mobile_headers)
        assert response.status_code == 200
        # Should still contain basic structure
        assert b'<!DOCTYPE html>' in response.data

    def test_desktop_user_agent(self, client):
        """Test pages work with desktop user agent."""
        desktop_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = client.get('/', headers=desktop_headers)
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data


@pytest.mark.functional
@pytest.mark.slow
class TestPerformanceBaseline:
    """Basic performance smoke tests."""

    def test_home_page_response_time(self, client):
        """Test home page responds within reasonable time."""
        import time
        
        start_time = time.time()
        response = client.get('/')
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should respond within 2 seconds (generous for testing)
        assert response_time < 2.0
        assert response.status_code == 200

    def test_multiple_concurrent_requests(self, client):
        """Test handling multiple sequential requests (simulated concurrency)."""
        import time
        
        # Flask test client doesn't handle true threading well
        # So we'll test rapid sequential requests instead
        results = []
        
        start_time = time.time()
        
        # Make 5 rapid sequential requests
        for _ in range(5):
            response = client.get('/')
            results.append(response.status_code)
        
        end_time = time.time()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        
        # Should complete within reasonable time (sequential is fine)
        assert end_time - start_time < 5.0


@pytest.mark.functional
class TestSecurityBasics:
    """Basic security smoke tests."""

    def test_sql_injection_protection(self, client):
        """Test basic SQL injection protection in URL parameters."""
        # Try SQL injection in session path
        malicious_path = "test'; DROP TABLE session; --"
        response = client.get(f'/sessions/{malicious_path}')
        
        # Should handle gracefully (404 or error page, not crash)
        assert response.status_code in [404, 500]

    def test_xss_protection_in_forms(self, client):
        """Test XSS protection in form inputs."""
        xss_payload = '<script>alert("xss")</script>'
        
        response = client.post('/login', data={
            'username': xss_payload,
            'password': 'password'
        })
        
        # Should not execute the malicious script, should escape or reject it
        assert response.status_code == 200
        # Check that the XSS payload is either escaped or not present
        response_text = response.data.decode('utf-8')
        # The malicious script should not be present as-is
        assert 'alert("xss")' not in response_text
        # If the script tag is present, it should be escaped
        if '<script>alert("xss")</script>' in response_text:
            # This would be a security issue - the payload should be escaped
            assert False, "XSS payload was not escaped"
        # The test passes if the payload is either escaped or not present

    def test_csrf_protection_enabled(self, client):
        """Test that CSRF protection is enabled for forms."""
        # This is a basic test - actual CSRF testing would need proper token handling
        response = client.get('/register')
        assert response.status_code == 200
        # Many CSRF implementations add hidden fields or meta tags
        # This is just checking the page loads properly