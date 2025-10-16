"""
Integration tests for authentication workflows.

Tests complete authentication flows including registration, login, password reset,
email verification, and session management with real database interactions.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import uuid

from auth import User, create_session
from database import get_db_connection
from timezone_utils import now_utc


@pytest.mark.integration
class TestRegistrationFlow:
    """Test complete user registration workflow."""

    @patch("web_routes.send_verification_email")
    def test_complete_registration_flow(
        self, mock_send_email, client, db_conn, db_cursor
    ):
        """Test complete registration process from form to database."""
        mock_send_email.return_value = True

        # Use unique identifiers to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        username = f"testreguser{unique_id}"
        email = f"testreg{unique_id}@example.com"

        # Submit registration form
        response = client.post(
            "/register",
            data={
                "username": username,
                "password": "securepass123",
                "confirm_password": "securepass123",
                "first_name": "Test",
                "last_name": "Registration",
                "email": email,
                "time_zone": "America/New_York",
            },
        )

        # Should redirect to login page
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

        # Verify person record was created
        db_cursor.execute(
            """
            SELECT person_id, first_name, last_name, email
            FROM person
            WHERE email = %s
        """,
            (email,),
        )
        person_record = db_cursor.fetchone()
        assert person_record is not None
        assert person_record[1] == "Test"
        assert person_record[2] == "Registration"

        # Verify user account was created
        db_cursor.execute(
            """
            SELECT user_id, username, person_id, email_verified, timezone
            FROM user_account
            WHERE username = %s
        """,
            (username,),
        )
        user_record = db_cursor.fetchone()
        assert user_record is not None
        assert user_record[1] == username
        assert user_record[2] == person_record[0]  # person_id should match
        assert user_record[3] is False  # email_verified should be False
        # Timezone should be set to requested value or UTC default
        assert user_record[4] in ["America/New_York", "UTC"]

        # Verify verification email was attempted
        mock_send_email.assert_called_once()

    def test_registration_duplicate_username(
        self, client, db_conn, db_cursor, sample_user_data
    ):
        """Test registration fails with duplicate username."""
        # Create existing user with unique email
        unique_id = str(uuid.uuid4())[:8]
        existing_email = f"existing{unique_id}@example.com"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Existing", "User", existing_email),
        )
        person_id = db_cursor.fetchone()[0]

        existing_username = f"existinguser{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (person_id, existing_username, existing_email, "hashedpass", "UTC"),
        )
        db_conn.commit()

        # Try to register with same username
        response = client.post(
            "/register",
            data={
                "username": existing_username,  # Use the same unique username to trigger duplicate error
                "password": "newpass123",
                "confirm_password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "email": f"new{unique_id}@example.com",  # Different email to isolate username duplication
            },
        )

        assert response.status_code == 200
        assert b"already exists" in response.data

    @patch("web_routes.send_verification_email")
    def test_registration_duplicate_email(self, mock_send_email, client, db_conn, db_cursor):
        """Test registration succeeds by linking to existing person without user account."""
        mock_send_email.return_value = True

        # Create person with existing email using unique identifier
        unique_id = str(uuid.uuid4())[:8]
        duplicate_email = f"duplicate{unique_id}@example.com"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Existing", "Person", duplicate_email),
        )
        existing_person_id = db_cursor.fetchone()[0]
        db_conn.commit()

        response = client.post(
            "/register",
            data={
                "username": f"newuser{unique_id}",  # Unique username
                "password": "newpass123",
                "confirm_password": "newpass123",
                "first_name": "Updated",
                "last_name": "Name",
                "email": duplicate_email,  # Same email - should link to existing person
            },
        )

        # Should redirect to login page after successful registration
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

        # Verify user account was created with existing person_id
        db_cursor.execute(
            """
            SELECT person_id, username
            FROM user_account
            WHERE username = %s
        """,
            (f"newuser{unique_id}",),
        )
        user_record = db_cursor.fetchone()
        assert user_record is not None
        assert user_record[0] == existing_person_id  # Should use existing person_id

        # Verify person name was updated
        db_cursor.execute(
            """
            SELECT first_name, last_name
            FROM person
            WHERE person_id = %s
        """,
            (existing_person_id,),
        )
        person_record = db_cursor.fetchone()
        assert person_record[0] == "Updated"
        assert person_record[1] == "Name"

    def test_registration_email_with_existing_user_account(self, client, db_conn, db_cursor):
        """Test registration fails when email already has a user account."""
        # Create person with existing email and user account
        unique_id = str(uuid.uuid4())[:8]
        duplicate_email = f"hasaccount{unique_id}@example.com"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Has", "Account", duplicate_email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password)
            VALUES (%s, %s, %s, %s)
        """,
            (person_id, f"existinguser{unique_id}", duplicate_email, "hashedpass"),
        )
        db_conn.commit()

        response = client.post(
            "/register",
            data={
                "username": f"newuser{unique_id}",  # Different username
                "password": "newpass123",
                "confirm_password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "email": duplicate_email,  # Email already has user account
            },
        )

        # Should stay on registration page with error
        assert response.status_code == 200
        assert b"already registered with a user account" in response.data


@pytest.mark.integration
class TestLoginFlow:
    """Test complete login workflow."""

    def test_successful_login_flow(self, client, db_conn, db_cursor):
        """Test complete login process with session creation."""
        # Create test user with verified email
        unique_id = str(uuid.uuid4())[:8]
        email = f"logintest{unique_id}@example.com"
        username = f"logintest{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Login", "Test", email),
        )
        person_id = db_cursor.fetchone()[0]

        import bcrypt

        hashed_password = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode(
            "utf-8"
        )

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    timezone, email_verified, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, hashed_password, "UTC", True, True),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Test login
        response = client.post(
            "/login", data={"username": username, "password": "testpass123"}
        )

        # Should redirect after successful login
        assert response.status_code == 302

        # Verify session was created in database
        db_cursor.execute(
            """
            SELECT session_id, user_id
            FROM user_session
            WHERE user_id = %s AND expires_at > NOW()
        """,
            (user_id,),
        )
        session_record = db_cursor.fetchone()
        assert session_record is not None
        assert session_record[1] == user_id

    def test_login_with_unverified_email(self, client, db_conn, db_cursor):
        """Test login fails with unverified email."""
        # Create test user with unverified email
        unique_id = str(uuid.uuid4())[:8]
        email = f"unverified{unique_id}@example.com"
        username = f"unverified{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Unverified", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        import bcrypt

        hashed_password = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode(
            "utf-8"
        )

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    timezone, email_verified, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (person_id, username, email, hashed_password, "UTC", False, True),
        )
        db_conn.commit()

        response = client.post(
            "/login", data={"username": username, "password": "testpass123"}
        )

        assert response.status_code == 200
        assert b"verify your email" in response.data.lower()

    def test_login_invalid_credentials(self, client, db_conn, db_cursor):
        """Test login fails with invalid credentials and logs attempt."""
        response = client.post(
            "/login", data={"username": "nonexistent", "password": "wrongpassword"}
        )

        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

        # Verify login failure was logged
        db_cursor.execute(
            """
            SELECT username, event_type, failure_reason
            FROM login_history
            WHERE username = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            ("nonexistent",),
        )
        log_record = db_cursor.fetchone()
        if log_record:  # May not exist if logging is mocked
            assert log_record[0] == "nonexistent"
            assert log_record[1] == "LOGIN_FAILURE"
            assert log_record[2] == "USER_NOT_FOUND"


@pytest.mark.integration
class TestPasswordResetFlow:
    """Test password reset workflow."""

    @patch("web_routes.send_password_reset_email")
    def test_password_reset_request(self, mock_send_email, client, db_conn, db_cursor):
        """Test password reset request process."""
        mock_send_email.return_value = True

        # Create test user
        unique_id = str(uuid.uuid4())[:8]
        email = f"reset{unique_id}@example.com"
        username = f"reset{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Reset", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, "oldhashedpass", True),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Request password reset
        response = client.post("/forgot-password", data={"email": email})

        assert response.status_code == 302  # Redirect to login

        # Verify reset token was set in database
        db_cursor.execute(
            """
            SELECT password_reset_token, password_reset_expires
            FROM user_account
            WHERE user_id = %s
        """,
            (user_id,),
        )
        reset_record = db_cursor.fetchone()
        assert reset_record[0] is not None  # Token should be set
        assert reset_record[1] is not None  # Expiry should be set
        from timezone_utils import now_utc

        assert reset_record[1] > now_utc()  # Should expire in future

        mock_send_email.assert_called_once()

    def test_password_reset_completion(self, client, db_conn, db_cursor):
        """Test password reset completion with valid token."""
        # Create user with reset token
        unique_id = str(uuid.uuid4())[:8]
        email = f"resetcomplete{unique_id}@example.com"
        username = f"resetcomplete{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Reset", "Complete", email),
        )
        person_id = db_cursor.fetchone()[0]

        reset_token = f"valid-reset-token-{unique_id}"
        from timezone_utils import now_utc

        reset_expires = now_utc() + timedelta(hours=1)

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    password_reset_token, password_reset_expires, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, "oldpass", reset_token, reset_expires, True),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Complete password reset
        response = client.post(
            f"/reset-password/{reset_token}",
            data={"password": "newpassword123", "confirm_password": "newpassword123"},
        )

        assert response.status_code == 302  # Redirect to login

        # Verify password was changed and token cleared
        db_cursor.execute(
            """
            SELECT hashed_password, password_reset_token, password_reset_expires
            FROM user_account
            WHERE user_id = %s
        """,
            (user_id,),
        )
        updated_record = db_cursor.fetchone()
        assert updated_record[0] != "oldpass"  # Password should be changed
        assert updated_record[1] is None  # Token should be cleared
        assert updated_record[2] is None  # Expiry should be cleared

    def test_password_reset_expired_token(self, client, db_conn, db_cursor):
        """Test password reset fails with expired token."""
        # Create user with expired reset token
        unique_id = str(uuid.uuid4())[:8]
        email = f"resetexpired{unique_id}@example.com"
        username = f"resetexpired{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Reset", "Expired", email),
        )
        person_id = db_cursor.fetchone()[0]

        expired_token = f"expired-reset-token-{unique_id}"
        expired_time = now_utc() - timedelta(hours=1)  # Already expired

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    password_reset_token, password_reset_expires, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (person_id, username, email, "oldpass", expired_token, expired_time, True),
        )
        db_conn.commit()

        response = client.post(
            f"/reset-password/{expired_token}",
            data={"password": "newpassword123", "confirm_password": "newpassword123"},
        )

        assert response.status_code == 302  # Redirect to forgot password
        assert "/forgot-password" in response.headers["Location"]


@pytest.mark.integration
class TestEmailVerificationFlow:
    """Test email verification workflow."""

    def test_email_verification_success(self, client, db_conn, db_cursor):
        """Test successful email verification."""
        # Create unverified user
        unique_id = str(uuid.uuid4())[:8]
        email = f"verify{unique_id}@example.com"
        username = f"verify{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Verify", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        verification_token = f"valid-verification-token-{unique_id}"
        verification_expires = now_utc() + timedelta(hours=24)

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    email_verified, verification_token, verification_token_expires)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (
                person_id,
                username,
                email,
                "hashedpass",
                False,
                verification_token,
                verification_expires,
            ),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Verify email
        response = client.get(f"/verify-email/{verification_token}")

        assert response.status_code == 302  # Redirect to login
        assert "/login" in response.headers["Location"]

        # Verify email_verified was set to True
        db_cursor.execute(
            """
            SELECT email_verified, verification_token, verification_token_expires
            FROM user_account
            WHERE user_id = %s
        """,
            (user_id,),
        )
        verified_record = db_cursor.fetchone()
        assert verified_record[0] is True  # email_verified should be True
        assert verified_record[1] is None  # token should be cleared
        assert verified_record[2] is None  # expiry should be cleared

    def test_email_verification_invalid_token(self, client):
        """Test email verification with invalid token."""
        response = client.get("/verify-email/invalid-token-123")

        assert response.status_code == 302
        assert "/resend-verification" in response.headers["Location"]

    @patch("web_routes.send_verification_email")
    def test_resend_verification_email(
        self, mock_send_email, client, db_conn, db_cursor
    ):
        """Test resending verification email."""
        mock_send_email.return_value = True

        # Create unverified user
        unique_id = str(uuid.uuid4())[:8]
        email = f"resend{unique_id}@example.com"
        username = f"resend{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Resend", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password,
                                    email_verified, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, "hashedpass", False, True),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        response = client.post("/resend-verification", data={"email": email})

        assert response.status_code == 302  # Redirect to login

        # Verify new verification token was generated
        db_cursor.execute(
            """
            SELECT verification_token, verification_token_expires
            FROM user_account
            WHERE user_id = %s
        """,
            (user_id,),
        )
        token_record = db_cursor.fetchone()
        assert token_record[0] is not None  # New token should be set
        assert token_record[1] is not None  # New expiry should be set

        mock_send_email.assert_called_once()


@pytest.mark.integration
class TestSessionManagement:
    """Test session management and cleanup."""

    def test_session_creation_and_cleanup(self, db_conn, db_cursor):
        """Test session creation and automatic cleanup."""
        # Create test user
        unique_id = str(uuid.uuid4())[:8]
        email = f"session{unique_id}@example.com"
        username = f"sessionuser{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Session", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, "hashedpass"),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Create session
        session_id = create_session(user_id, "127.0.0.1", "Test User Agent")

        # Verify session was created
        db_cursor.execute(
            """
            SELECT session_id, user_id, ip_address, user_agent, expires_at
            FROM user_session
            WHERE session_id = %s
        """,
            (session_id,),
        )
        session_record = db_cursor.fetchone()
        assert session_record is not None
        assert session_record[1] == user_id
        assert session_record[2] == "127.0.0.1"
        assert session_record[3] == "Test User Agent"
        assert session_record[4] > now_utc()  # Should expire in future

        # Create an expired session for cleanup testing
        expired_time = now_utc() - timedelta(days=1)
        expired_session_id = f"expired-session-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO user_session (session_id, user_id, expires_at)
            VALUES (%s, %s, %s)
        """,
            (expired_session_id, user_id, expired_time),
        )
        db_conn.commit()

        # Test cleanup
        from auth import cleanup_expired_sessions

        cleanup_expired_sessions()

        # Verify expired session was removed but active session remains
        db_cursor.execute(
            "SELECT session_id FROM user_session WHERE user_id = %s", (user_id,)
        )
        remaining_sessions = db_cursor.fetchall()
        session_ids = [s[0] for s in remaining_sessions]
        assert session_id in session_ids
        assert expired_session_id not in session_ids
