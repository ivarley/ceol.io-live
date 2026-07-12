"""
Integration tests for manual tune addition interface.

Tests the complete workflow of searching for and adding tunes manually
to a user's personal collection.
"""

import pytest
import json
import uuid
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestManualTuneAdditionWorkflow:
    """Test complete manual tune addition user journey."""

    def test_user_searches_and_adds_tune(self, client, authenticated_user, db_conn, db_cursor):
        """Test complete workflow: search tune → select from results → add to collection."""
        # Create test tunes
        unique_id = str(uuid.uuid4())[:8]
        tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 50000
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"The Butterfly {unique_id}", "Slip Jig", 450))
        db_conn.commit()
        
        with authenticated_user:
            person_id = authenticated_user.person_id
            
            # Phase 1: User hits the legacy add URL — folded away into a redirect
            # to My Tunes with the add pane auto-opened.
            response = client.get("/my-tunes/add", follow_redirects=False)
            assert response.status_code == 302
            assert response.location == "/my-tunes?add=1"
            
            # Phase 2: User searches for a tune
            response = client.get(f"/api/tunes/search?q=butterfly {unique_id}")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert len(data["tunes"]) >= 1
            assert any(t["tune_id"] == tune_id for t in data["tunes"])
            
            # Phase 3: User selects a tune and adds it
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({
                    "tune_id": tune_id,
                    "learn_status": "want to learn",
                    "notes": "Heard at session, want to learn"
                }),
                content_type="application/json"
            )
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data["success"] is True
            assert "person_tune_id" in data["person_tune"]
            assert data["message"] == "Tune added to your collection successfully"
            
            # Phase 4: Verify tune appears in collection
            response = client.get("/api/my-tunes")
            data = json.loads(response.data)
            assert any(t["tune_id"] == tune_id for t in data["tunes"])

    def test_tune_search_autocomplete_features(self, client, authenticated_user, db_conn, db_cursor):
        """Test tune search autocomplete functionality."""
        with authenticated_user:
            # Test minimum query length
            response = client.get("/api/tunes/search?q=a")
            assert response.status_code == 400
            data = json.loads(response.data)
            assert "at least 2 characters" in data["error"]
            
            # Test empty query
            response = client.get("/api/tunes/search?q=")
            assert response.status_code == 400
            
            # Test successful search - use existing tunes in database
            response = client.get("/api/tunes/search?q=reel")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            # Should find some reels in the database
            
            # Test search with limit parameter
            response = client.get("/api/tunes/search?q=the&limit=5")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert len(data["tunes"]) <= 5

    def test_add_tune_with_different_statuses(self, client, authenticated_user, db_conn, db_cursor):
        """Test adding tunes with different initial learning statuses."""
        with authenticated_user:
            person_id = authenticated_user.person_id

            statuses = ["want to learn", "learning", "learned"]

            for status in statuses:
                # Create a unique tune for each status
                unique_id = str(uuid.uuid4())[:8]
                tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 60000  # Different range

                db_cursor.execute("""
                    INSERT INTO tune (tune_id, name, tune_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tune_id) DO NOTHING
                """, (tune_id, f"Test Tune {unique_id}", "Reel"))
                db_conn.commit()

                response = client.post(
                    "/api/my-tunes",
                    data=json.dumps({
                        "tune_id": tune_id,
                        "learn_status": status
                    }),
                    content_type="application/json"
                )
                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True

    def test_add_tune_with_notes(self, client, authenticated_user, db_conn, db_cursor):
        """Test adding a tune with optional notes."""
        with authenticated_user:
            person_id = authenticated_user.person_id

            # Create a test tune
            unique_id = str(uuid.uuid4())[:8]
            tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 70000

            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (tune_id) DO NOTHING
            """, (tune_id, f"Test Tune Notes {unique_id}", "Jig"))
            db_conn.commit()

            response = client.post(
                "/api/my-tunes",
                data=json.dumps({
                    "tune_id": tune_id,
                    "learn_status": "want to learn",
                    "notes": "Heard at Galway session, beautiful melody"
                }),
                content_type="application/json"
            )
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["person_tune"]["notes"] == "Heard at Galway session, beautiful melody"


@pytest.mark.functional
class TestManualAdditionValidation:
    """Test validation and error handling for manual tune addition."""

    def test_cannot_add_nonexistent_tune(self, client, authenticated_user):
        """Test that adding a non-existent tune fails gracefully."""
        with authenticated_user:
            # Use a very high tune_id that definitely doesn't exist
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({"tune_id": 999999999}),
                content_type="application/json"
            )
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not found" in data["error"].lower()

    def test_cannot_add_duplicate_tune(self, client, authenticated_user, db_conn, db_cursor):
        """Test that adding a duplicate tune is prevented."""
        with authenticated_user:
            # Create a test tune
            unique_id = str(uuid.uuid4())[:8]
            tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 80000

            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (tune_id) DO NOTHING
            """, (tune_id, f"Duplicate Test {unique_id}", "Hornpipe"))
            db_conn.commit()

            # Add tune first time
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({"tune_id": tune_id}),
                content_type="application/json"
            )
            assert response.status_code == 201

            # Try to add same tune again
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({"tune_id": tune_id}),
                content_type="application/json"
            )
            assert response.status_code == 409  # Conflict
            data = json.loads(response.data)
            assert data["success"] is False
            assert "already" in data["error"].lower()

    def test_invalid_learn_status_rejected(self, client, authenticated_user, db_conn, db_cursor):
        """Test that invalid learn_status values are rejected."""
        with authenticated_user:
            # Create a test tune
            unique_id = str(uuid.uuid4())[:8]
            tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 90000

            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (tune_id) DO NOTHING
            """, (tune_id, f"Status Test {unique_id}", "Reel"))
            db_conn.commit()

            response = client.post(
                "/api/my-tunes",
                data=json.dumps({
                    "tune_id": tune_id,
                    "learn_status": "invalid_status"
                }),
                content_type="application/json"
            )
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False

    def test_missing_tune_id_rejected(self, client, authenticated_user):
        """Test that requests without tune_id are rejected."""
        with authenticated_user:
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({"learn_status": "want to learn"}),
                content_type="application/json"
            )
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "tune_id" in data["error"].lower()


@pytest.mark.functional
@pytest.mark.skip(reason="These tests use mocking which should be in unit tests, not functional tests")
class TestSearchPrioritization:
    """Test tune search result prioritization."""

    def test_exact_match_prioritized(self, client, authenticated_user):
        """Test that exact matches are prioritized in search results."""
        pass

    def test_popularity_as_secondary_sort(self, client, authenticated_user):
        """Test that tunebook count is used as secondary sort criteria."""
        pass


@pytest.mark.functional
class TestAddPageRedirects:
    """The legacy fallback add pages are folded away: both URLs now redirect to
    their modern Svelte surfaces with the add pane auto-opened (?add=1), passing
    an optional ?q= search prefill through."""

    def test_unauthenticated_user_redirected_to_login(self, client):
        """/my-tunes/add keeps its login gate (302 to login when anonymous)."""
        response = client.get("/my-tunes/add", follow_redirects=False)
        assert response.status_code == 302  # Redirect
        assert "/login" in response.location

    def test_my_tunes_add_redirects_to_pane(self, client, authenticated_user):
        """/my-tunes/add -> /my-tunes?add=1 (the pane auto-opens client-side)."""
        with authenticated_user:
            response = client.get("/my-tunes/add", follow_redirects=False)
            assert response.status_code == 302
            assert response.location == "/my-tunes?add=1"

    def test_my_tunes_add_passes_query_through(self, client, authenticated_user):
        """?q= survives the redirect so the pane's search is prefilled."""
        with authenticated_user:
            response = client.get("/my-tunes/add?q=kesh", follow_redirects=False)
            assert response.status_code == 302
            assert response.location == "/my-tunes?add=1&q=kesh"

    def test_session_tune_add_redirects_to_tunes_tab(self, client):
        """/sessions/<path>/tunes/add -> the session's Tunes tab with ?add=1."""
        response = client.get("/sessions/austin/mueller/tunes/add", follow_redirects=False)
        assert response.status_code == 302
        assert response.location == "/sessions/austin/mueller/tunes?add=1"

    def test_session_tune_add_passes_query_through(self, client):
        response = client.get(
            "/sessions/austin/mueller/tunes/add?q=kesh", follow_redirects=False
        )
        assert response.status_code == 302
        assert response.location == "/sessions/austin/mueller/tunes?add=1&q=kesh"


@pytest.mark.functional
class TestSuccessRedirection:
    """Test success feedback and navigation after adding tune."""

    def test_success_message_on_redirect(self, client, authenticated_user):
        """Test that success message is shown after adding tune."""
        with authenticated_user:
            # After successful add, user is redirected to /my-tunes with added parameter
            response = client.get("/my-tunes?added=The%20Butterfly")
            assert response.status_code == 200
            # JavaScript should display success message
            assert b"my-tunes" in response.data

    def test_added_tune_highlighted_in_list(self, client, authenticated_user, db_conn, db_cursor):
        """Test that newly added tune can be identified in the list."""
        with authenticated_user:
            person_id = authenticated_user.person_id

            # Create a test tune
            unique_id = str(uuid.uuid4())[:8]
            tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 95000

            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (tune_id) DO NOTHING
            """, (tune_id, f"Highlight Test {unique_id}", "Polka"))
            db_conn.commit()

            # Add the tune
            response = client.post(
                "/api/my-tunes",
                data=json.dumps({"tune_id": tune_id}),
                content_type="application/json"
            )
            assert response.status_code == 201
            data = json.loads(response.data)
            new_person_tune_id = data["person_tune"]["person_tune_id"]

            # Verify tune appears in collection
            response = client.get("/api/my-tunes")
            data = json.loads(response.data)
            assert any(t["person_tune_id"] == new_person_tune_id for t in data["tunes"])
            assert any(t["tune_id"] == tune_id for t in data["tunes"])
