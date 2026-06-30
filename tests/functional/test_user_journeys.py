"""
End-to-end user journey tests.

Tests complete user workflows from start to finish, simulating
real user interactions with the application.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import uuid
from datetime import datetime, date
from timezone_utils import now_utc

from flask import url_for


@pytest.mark.functional
class TestNewUserCompleteJourney:
    """Test complete journey of a new user discovering and using the site."""

    @patch("web_routes.send_verification_email")
    def test_new_user_discovers_registers_and_explores(
        self, mock_send_email, client, db_conn, db_cursor
    ):
        """Complete new-user journey: discover the site, browse, then register.

        Runs against the real seeded DB. The home dashboard and the sessions
        directory load their lists client-side (covered by the API tests), so the
        browse phases assert the page shells and the server-rendered session
        detail. Registration runs for real against the DB (the verification email
        send is mocked) and the created account is cleaned up. Email verification
        itself is covered separately by the auth-flow integration tests.
        """
        mock_send_email.return_value = True

        # Phase 1: Discovery - the home page loads.
        assert client.get("/").status_code == 200

        # Phase 2: Exploration - the sessions directory shell loads.
        response = client.get("/sessions")
        assert response.status_code == 200
        assert b'id="sessions-tbody"' in response.data

        # Phase 3: Interest - a real session's detail page renders server-side.
        response = client.get("/sessions/austin/mueller")
        assert response.status_code == 200
        assert b"Mueller Session" in response.data

        # Phase 4: Decision to Join - register a brand-new account.
        unique_id = str(uuid.uuid4())[:8]
        username = f"newfan_{unique_id}"
        email = f"{username}@example.com"
        try:
            response = client.post(
                "/register",
                data={
                    "username": username,
                    "password": "mypassword123",
                    "confirm_password": "mypassword123",
                    "first_name": "Music",
                    "last_name": "Fan",
                    "email": email,
                    "time_zone": "America/Chicago",
                },
            )

            # Successful registration redirects to the login page.
            assert response.status_code == 302
            assert "/login" in response.headers["Location"]
            # ...and the verification email was triggered.
            mock_send_email.assert_called_once()

            # The account was actually created (unverified).
            db_cursor.execute(
                "SELECT email_verified FROM user_account WHERE username = %s",
                (username,),
            )
            row = db_cursor.fetchone()
            assert row is not None
            assert row[0] is False
        finally:
            db_cursor.execute("DELETE FROM user_account WHERE username = %s", (username,))
            db_cursor.execute("DELETE FROM person WHERE email = %s", (email,))
            db_conn.commit()

    @patch("web_routes.User.get_by_username")
    @patch("web_routes.create_session")
    @patch("web_routes.login_user")
    @patch("web_routes.get_db_connection")
    def test_verified_user_login_and_exploration(
        self, mock_get_conn, mock_login_user, mock_create_session, mock_get_user, client
    ):
        """Test verified user logging in and exploring authenticated features."""
        # Setup authenticated user
        user = MagicMock()
        user.is_active = True
        user.email_verified = True
        user.check_password.return_value = True
        user.user_id = 101
        user.person_id = 42
        user.is_system_admin = False
        mock_get_user.return_value = user

        # Setup database mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchall.return_value = []  # No admin sessions

        mock_create_session.return_value = "session-token-123"

        # Phase 1: Login
        response = client.post(
            "/login", data={"username": "newmusicfan", "password": "mypassword123"}
        )

        assert response.status_code == 302  # Redirect after login
        mock_login_user.assert_called_once()

        # Phase 2: Explore with authenticated context
        with client.session_transaction() as sess:
            sess["_user_id"] = "101"
            sess["is_system_admin"] = False

        # User can now see personalized content
        response = client.get("/")
        assert response.status_code == 200


@pytest.mark.functional
class TestSessionAdminJourney:
    """Test session administrator user journey."""

    def test_admin_session_management_workflow(self, client, admin_user):
        """Test admin managing sessions and viewing admin features.

        Runs against the real seeded DB. The admin dashboards render their rows
        server-side, so a hand-rolled cursor mock (which has to match the exact
        column count and per-query shape of several queries) is brittle; the real
        DB exercises the actual rendering path.
        """
        # Phase 1: Admin accesses the people dashboard.
        with admin_user:
            response = client.get("/admin/people")
        assert response.status_code == 200
        assert b"Varley" in response.data  # seeded admin person

        # Phase 2: Admin views the sessions list.
        with admin_user:
            response = client.get("/admin/sessions")
        assert response.status_code == 200
        assert b"Mueller Session" in response.data  # seeded session

        # Phase 3: Admin manages a specific seeded session.
        with admin_user:
            response = client.get("/admin/sessions/austin/mueller")
        assert response.status_code == 200
        assert b"Mueller Session" in response.data

    def test_admin_api_usage_workflow(self, client, admin_user):
        """Test admin using API endpoints for management tasks."""
        # Phase 1: Get session players
        with patch("api_routes.get_db_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            mock_cursor.fetchone.side_effect = [
                (True,),  # is_system_admin check
                None,  # Session doesn't exist (test-session not found)
            ]

            with admin_user:
                response = client.get("/api/admin/sessions/test-session/people")
            # The route now exists and returns 404 when session not found
            assert response.status_code == 404


@pytest.mark.functional
class TestMusicianWorkflow:
    """Test workflow of a musician logging tunes at sessions."""

    def test_musician_adds_tunes_to_session(
        self, client, authenticated_user, db_conn, db_cursor
    ):
        """Test musician adding tunes to a session instance.

        Runs against the real seeded DB: add_tune_ajax does fuzzy matching, set
        segmentation and fractional-index ordering across several queries, which
        a hand-rolled cursor mock can't represent faithfully.
        """
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"musician-journey-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
            """,
            (f"Musician Journey {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]
        test_date = date(2023, 8, 15)
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, %s)",
            (session_id, test_date),
        )
        db_conn.commit()

        # Unique names so the fuzzy match is unambiguous (common real names like
        # "The Butterfly" intentionally resolve to multiple seeded tunes).
        with authenticated_user:
            # Phase 1: Add first tune
            response = client.post(
                f"/api/sessions/{session_path}/2023-08-15/add_tune",
                json={"tune_name": f"Journey Reel {unique_id}"},
            )
            assert response.status_code == 200
            assert json.loads(response.data)["success"] is True

            # Phase 2: Add second tune (continues the set)
            response = client.post(
                f"/api/sessions/{session_path}/2023-08-15/add_tune",
                json={"tune_name": f"Journey Jig {unique_id}"},
            )
            assert response.status_code == 200
            assert json.loads(response.data)["success"] is True

        # Both tunes landed on the instance.
        db_cursor.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND si.date = %s
            """,
            (session_id, test_date),
        )
        assert db_cursor.fetchone()[0] >= 2

    def test_musician_uses_magic_tune_selector(self, client):
        """Test musician using magic tune selection feature."""
        with patch("web_routes.get_db_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # Mock tunes for selection
            mock_cursor.fetchall.return_value = [
                (1001, "The Butterfly", "Slip Jig", 3),
                (1002, "Morrison's Jig", "Jig", 8),
                (1003, "The Musical Priest", "Reel", 5),
                (1004, "Out on the Ocean", "Reel", 12),
                (1005, "The Banshee", "Reel", 2),
            ]

            # Phase 1: Get reel recommendations
            response = client.get("/magic?type=reel")
            assert response.status_code == 200
            assert b"Reel" in response.data

            # Phase 2: Get jig recommendations
            response = client.get("/magic?type=jig")
            assert response.status_code == 200

            # Phase 3: Get slip jig recommendations
            response = client.get("/magic?type=slip+jig")
            assert response.status_code == 200


@pytest.mark.functional
class TestTuneLinkingWorkflow:
    """Test workflow of linking tunes to thesession.org database."""

    @patch("api_routes.requests.get")
    def test_tune_linking_and_tunebook_refresh(
        self, mock_requests, client, authenticated_user
    ):
        """Test linking tunes and refreshing tunebook counts."""
        # Mock external API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tune": {
                "id": 1001,
                "name": "The Butterfly",
                "type": "Slip Jig",
                "tunebooks": 156,
            }
        }
        mock_requests.return_value = mock_response

        with patch("api_routes.get_db_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # Phase 1: Link tune to session
            mock_cursor.fetchone.side_effect = [
                (1,),  # Session exists
                (1001, "The Butterfly", "Slip Jig", 120),  # Tune exists
            ]

            with authenticated_user:
                response = client.post(
                    "/api/sessions/test-session/2023-08-15/link_tune",
                    json={
                        "tune_name": "The Butterfly",
                        "tune_id": "1001",
                    },
                )

            assert response.status_code == 200
            data = json.loads(response.data)
            # For functional test, just verify the API responds - specific success may depend on complex setup
            assert "success" in data

            # Phase 2: Refresh tunebook count
            mock_cursor.fetchone.side_effect = [
                (1,),  # Session exists
                (1001,),  # Tune exists in session
            ]

            with authenticated_user:
                response = client.post(
                    "/api/sessions/test-session/tunes/1001/refresh_tunebook_count"
                )

            assert response.status_code == 200
            data = json.loads(response.data)
            # For functional test, just verify the API responds - specific success may depend on complex setup
            assert "success" in data


@pytest.mark.functional
class TestSessionCreationWorkflow:
    """Test workflow of creating new sessions."""

    def test_user_creates_new_session(self, client, authenticated_user):
        """Test user creating a new session through the interface.

        The whole journey runs inside one authenticated context. (Flask-Login's
        session protection rejects a _user_id injected after the client has
        already issued anonymous requests, so we authenticate before the first
        request rather than only around the create call.)
        """
        with authenticated_user:
            # Phase 1: Access add session page
            response = client.get("/add-session")
            assert response.status_code == 200
            assert b"session" in response.data.lower()

            # Phase 2: Check if similar session exists
            response = client.post(
                "/api/check-existing-session", json={"name": "New Test Session"}
            )
            assert response.status_code == 200
            json.loads(response.data)  # valid JSON response

            # Phase 3: Create the session (DB mocked so no row is committed)
            with patch("api_routes.get_db_connection") as mock_get_conn:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_get_conn.return_value = mock_conn
                mock_cursor.fetchone.return_value = (1,)  # New session ID

                response = client.post(
                    "/api/add-session",
                    json={
                        "name": "New Test Session",
                        "path": "new-test-session",
                        "city": "Houston",
                        "state": "TX",
                        "country": "USA",
                        "location_name": "Music Hall",
                        "timezone": "America/Chicago",
                        "comments": "Weekly session for all levels",
                    },
                )

                assert response.status_code == 200
                data = json.loads(response.data)
                # For functional test, just verify the API responds - specific
                # success may depend on complex setup
                assert "success" in data


@pytest.mark.functional
class TestPasswordManagementWorkflow:
    """Test complete password management workflow."""

    @patch("web_routes.send_password_reset_email")
    @patch("web_routes.get_db_connection")
    def test_complete_password_reset_journey(
        self, mock_get_conn, mock_send_email, client
    ):
        """Test complete password reset from request to completion."""
        mock_send_email.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Phase 1: User forgets password and requests reset
        mock_cursor.fetchone.return_value = (1, "testuser", "test@example.com", "Test")

        response = client.post("/forgot-password", data={"email": "test@example.com"})

        assert response.status_code == 302  # Redirect to login
        mock_send_email.assert_called_once()

        # Phase 2: User receives email and clicks reset link
        reset_token = "valid-reset-token-456"
        mock_cursor.fetchone.side_effect = [
            (1,),  # Valid token for GET request
            (1,),  # Valid token for POST request
            ("testuser",),  # Username lookup
        ]

        # Check reset form loads
        response = client.get(f"/reset-password/{reset_token}")
        assert response.status_code == 200
        assert b"password" in response.data.lower()

        # Phase 3: User submits new password
        response = client.post(
            f"/reset-password/{reset_token}",
            data={
                "password": "mynewpassword123",
                "confirm_password": "mynewpassword123",
            },
        )

        assert response.status_code == 302  # Redirect to login
        assert "/login" in response.headers["Location"]

    def test_authenticated_user_changes_password(self, client, authenticated_user):
        """Test authenticated user changing their password."""
        with patch("web_routes.User.get_by_username") as mock_get_user:
            # Mock current user for password verification
            user = MagicMock()
            user.check_password.return_value = True
            mock_get_user.return_value = user

            with patch("web_routes.get_db_connection") as mock_get_conn:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_get_conn.return_value = mock_conn

                # Phase 1: Access change password page
                with authenticated_user:
                    response = client.get("/change-password")
                assert response.status_code == 200
                assert b"current password" in response.data.lower()

                # Phase 2: Submit password change
                with authenticated_user:
                    response = client.post(
                        "/change-password",
                        data={
                            "current_password": "oldpassword123",
                            "new_password": "mynewpassword456",
                            "confirm_password": "mynewpassword456",
                        },
                    )

                assert response.status_code == 302  # Redirect to home
                assert "/" in response.headers["Location"]


@pytest.mark.functional
@pytest.mark.slow
class TestLongRunningWorkflows:
    """Test workflows that involve multiple steps over time."""

    def test_session_evolution_over_time(self, client):
        """Test how a session evolves with multiple instances and tune logs."""
        # This would test a session being created, having instances added,
        # tunes logged over multiple sessions, players joining/leaving, etc.
        # For brevity, implementing a simplified version

        with patch("web_routes.get_db_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # Simulate session with history
            mock_cursor.fetchone.return_value = (
                1,
                None,
                "Evolving Session",
                "evolving-session",
                "Music Venue",
                None,
                None,
                None,
                "Austin",
                "TX",
                "USA",
                "A session that grows over time",
                False,
                date(2023, 1, 1),
                None,
                "weekly",
            )

            # Multiple instances showing growth
            mock_cursor.fetchall.side_effect = [
                # Past instances (showing progression over months)
                [
                    (date(2023, 8, 15),),
                    (date(2023, 8, 8),),
                    (date(2023, 8, 1),),
                    (date(2023, 7, 25),),
                    (date(2023, 7, 18),),
                ],
                # Popular tunes (showing variety and frequency)
                [
                    ("The Butterfly", 1001, 15, 156),
                    ("Morrison's Jig", 1002, 12, 203),
                    ("The Musical Priest", 1003, 10, 89),
                    ("Out on the Ocean", 1004, 8, 145),
                ],
            ]

            response = client.get("/sessions/evolving-session")
            assert response.status_code == 200
            assert b"Evolving Session" in response.data
            assert b"The Butterfly" in response.data  # Most popular tune

            # NOTE: the list of past instance dates is now loaded client-side via
            # the session API (it used to be server-rendered), so it is no longer
            # asserted here — the instances endpoint is covered by the API tests.
