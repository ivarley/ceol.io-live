"""
Integration tests for personal tune management API endpoints.

Tests the /api/my-tunes endpoints with real database interactions to ensure
proper authentication, authorization, data handling, and business logic.
"""

import pytest
import json
import uuid
from datetime import datetime


@pytest.mark.integration
class TestPersonTuneAPI:
    """Test personal tune management API endpoints."""

    def test_get_my_tunes_requires_authentication(self, client):
        """Test that GET /api/my-tunes requires authentication."""
        response = client.get("/api/my-tunes")
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False
        assert "authentication" in data["error"].lower()

    def test_get_my_tunes_empty_collection(self, client, authenticated_user, db_conn, db_cursor):
        """Test getting tunes when user has no tunes in collection."""
        # Clean up any existing person_tune records for this user
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = 2")
        db_conn.commit()

        with authenticated_user:
            response = client.get("/api/my-tunes")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "tunes" in data
        assert len(data["tunes"]) == 0
        assert data["pagination"]["total_count"] == 0

    def test_get_my_tunes_with_data(self, client, authenticated_user, db_conn, db_cursor):
        """Test getting tunes when user has tunes in collection."""
        # Clean up any existing person_tune records for this user
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = 2")
        db_conn.commit()

        # Create test tunes
        unique_id = str(uuid.uuid4())[:8]
        tune_id_1 = int(unique_id[:6], 16) % 100000 + 50000
        tune_id_2 = int(unique_id[2:8], 16) % 100000 + 50000

        # Ensure person exists
        person_id = 2  # Match authenticated_user fixture
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
            VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (
            tune_id_1, f"Test Reel {unique_id}", "Reel", 100,
            tune_id_2, f"Test Jig {unique_id}", "Jig", 50
        ))
        
        # Add tunes to user's collection
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count)
            VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
        """, (
            person_id, tune_id_1, 'want to learn', 3,
            person_id, tune_id_2, 'learning', 0
        ))
        db_conn.commit()
        
        with authenticated_user:
            response = client.get("/api/my-tunes")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["tunes"]) == 2
        assert data["pagination"]["total_count"] == 2
        
        # Verify tune data
        tune_names = [t["tune_name"] for t in data["tunes"]]
        assert f"Test Reel {unique_id}" in tune_names
        assert f"Test Jig {unique_id}" in tune_names

    def test_get_my_tunes_with_learn_status_filter(self, client, authenticated_user, db_conn, db_cursor):
        """Test filtering tunes by learn_status."""
        # Clean up any existing person_tune records for this user
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = 2")
        db_conn.commit()

        # Create test tunes
        unique_id = str(uuid.uuid4())[:8]
        tune_id_1 = int(unique_id[:6], 16) % 100000 + 50000
        tune_id_2 = int(unique_id[2:8], 16) % 100000 + 50000

        person_id = 2  # Match authenticated_user fixture
        # Ensure person exists
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s), (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (
            tune_id_1, f"Want to Learn Reel {unique_id}", "Reel",
            tune_id_2, f"Learning Jig {unique_id}", "Jig"
        ))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s), (%s, %s, %s)
        """, (
            person_id, tune_id_1, 'want to learn',
            person_id, tune_id_2, 'learning'
        ))
        db_conn.commit()
        
        with authenticated_user:
            response = client.get("/api/my-tunes?learn_status=want to learn")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["tunes"]) == 1
        assert data["tunes"][0]["learn_status"] == "want to learn"
        assert data["filters"]["learn_status"] == "want to learn"

    def test_get_my_tunes_with_tune_type_filter(self, client, authenticated_user, db_conn, db_cursor):
        """Test filtering tunes by tune_type."""
        # Clean up any existing person_tune records for this user
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = 2")
        db_conn.commit()

        # Create test tunes
        unique_id = str(uuid.uuid4())[:8]
        tune_id_1 = int(unique_id[:6], 16) % 100000 + 50000
        tune_id_2 = int(unique_id[2:8], 16) % 100000 + 50000

        person_id = 2  # Match authenticated_user fixture
        # Ensure person exists
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s), (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (
            tune_id_1, f"Filter Reel {unique_id}", "Reel",
            tune_id_2, f"Filter Jig {unique_id}", "Jig"
        ))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s), (%s, %s, %s)
        """, (
            person_id, tune_id_1, 'want to learn',
            person_id, tune_id_2, 'want to learn'
        ))
        db_conn.commit()
        
        with authenticated_user:
            response = client.get("/api/my-tunes?tune_type=Reel")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["tunes"]) == 1
        assert data["tunes"][0]["tune_type"] == "Reel"

    def test_get_my_tunes_with_search(self, client, authenticated_user, db_conn, db_cursor):
        """Test searching tunes by name."""
        # Create test tunes
        unique_id = str(uuid.uuid4())[:8]
        tune_id_1 = int(unique_id[:6], 16) % 100000 + 50000
        tune_id_2 = int(unique_id[2:8], 16) % 100000 + 50000

        person_id = 2  # Match authenticated_user fixture
        # Ensure person exists
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s), (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (
            tune_id_1, f"Cooley's Reel {unique_id}", "Reel",
            tune_id_2, f"Morrison's Jig {unique_id}", "Jig"
        ))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s), (%s, %s, %s)
        """, (
            person_id, tune_id_1, 'want to learn',
            person_id, tune_id_2, 'want to learn'
        ))
        db_conn.commit()
        
        with authenticated_user:
            response = client.get("/api/my-tunes?search=Cooley")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["tunes"]) == 1
        assert "Cooley" in data["tunes"][0]["tune_name"]

    def test_get_my_tunes_pagination(self, client, authenticated_user, db_conn, db_cursor):
        """Test pagination of tune collection."""
        # Create multiple test tunes
        unique_id = str(uuid.uuid4())[:8]
        person_id = 2  # Match authenticated_user fixture
        
        # Ensure person exists
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        # Create 5 tunes
        for i in range(5):
            tune_id = int(unique_id[:6], 16) % 100000 + 50000 + i
            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (tune_id) DO NOTHING
            """, (tune_id, f"Pagination Tune {i} {unique_id}", "Reel"))
            
            db_cursor.execute("""
                INSERT INTO person_tune (person_id, tune_id, learn_status)
                VALUES (%s, %s, %s)
            """, (person_id, tune_id, 'want to learn'))
        
        db_conn.commit()
        
        with authenticated_user:
            # Get first page with 2 items per page
            response = client.get("/api/my-tunes?page=1&per_page=2")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["tunes"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total_count"] >= 5
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

    def test_add_my_tune_requires_authentication(self, client):
        """Test that POST /api/my-tunes requires authentication."""
        response = client.post("/api/my-tunes", json={"tune_id": 123})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False

    def test_add_my_tune_success(self, client, authenticated_user, db_conn, db_cursor):
        """Test successfully adding a tune to collection."""
        # Create test tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"New Tune {unique_id}", "Reel", 75))
        db_conn.commit()
        
        with authenticated_user:
            response = client.post("/api/my-tunes", json={
                "tune_id": tune_id,
                "learn_status": "want to learn",
                "notes": "Test notes"
            })
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["person_tune"]["tune_id"] == tune_id
        assert data["person_tune"]["learn_status"] == "want to learn"
        assert data["person_tune"]["notes"] == "Test notes"
        assert data["person_tune"]["tune_name"] == f"New Tune {unique_id}"

    def test_add_my_tune_missing_tune_id(self, client, authenticated_user):
        """Test adding tune without tune_id."""
        with authenticated_user:
            response = client.post("/api/my-tunes",
                                  json={"learn_status": "want to learn"})

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "tune_id" in data["error"].lower()

    def test_add_my_tune_nonexistent_tune(self, client, authenticated_user):
        """Test adding a tune that doesn't exist."""
        with authenticated_user:
            response = client.post("/api/my-tunes", json={"tune_id": 999999999})
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_add_my_tune_duplicate(self, client, authenticated_user, db_conn, db_cursor):
        """Test adding a tune that's already in collection."""
        # Create test tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        # Ensure person exists
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (person_id, "Test", "User", f"test{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Duplicate Tune {unique_id}", "Reel"))
        
        # Add tune to collection first
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
        """, (person_id, tune_id, 'want to learn'))
        db_conn.commit()
        
        # Try to add the same tune again
        with authenticated_user:
            response = client.post("/api/my-tunes", json={"tune_id": tune_id})
        
        assert response.status_code == 409  # Conflict
        data = json.loads(response.data)
        assert data["success"] is False
        assert "already exists" in data["error"].lower()

    def test_update_tune_status_requires_authentication(self, client):
        """Test that PUT /api/my-tunes/<id>/status requires authentication."""
        response = client.put("/api/my-tunes/1/status", json={"learn_status": "learning"})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False

    def test_update_tune_status_success(self, client, authenticated_user, db_conn, db_cursor):
        """Test successfully updating tune learning status."""
        # Create test tune and person_tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Status Update Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'want to learn'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.put(f"/api/my-tunes/{person_tune_id}/status", json={
                "learn_status": "learning"
            })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["person_tune"]["learn_status"] == "learning"

    def test_update_tune_status_to_learned_sets_date(self, client, authenticated_user, db_conn, db_cursor):
        """Test that updating status to 'learned' sets learned_date."""
        # Create test tune and person_tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Learned Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'learning'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.put(f"/api/my-tunes/{person_tune_id}/status", json={
                "learn_status": "learned"
            })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["person_tune"]["learn_status"] == "learned"
        assert data["person_tune"]["learned_date"] is not None

    def test_update_tune_status_unauthorized(self, client, authenticated_user, db_conn, db_cursor):
        """Test that users cannot update other users' tunes."""
        # Create another user's tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        other_person_id = 999  # Different from authenticated user's person_id
        
        # Create the other person
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (other_person_id, "Other", "User", f"other{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Other User Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
            RETURNING person_tune_id
        """, (other_person_id, tune_id, 'want to learn'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.put(f"/api/my-tunes/{person_tune_id}/status", json={
                "learn_status": "learning"
            })
        
        assert response.status_code == 403  # Forbidden
        data = json.loads(response.data)
        assert data["success"] is False

    def test_increment_heard_count_requires_authentication(self, client):
        """Test that POST /api/my-tunes/<id>/heard requires authentication."""
        response = client.post("/api/my-tunes/1/heard")
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False

    def test_increment_heard_count_success(self, client, authenticated_user, db_conn, db_cursor):
        """Test successfully incrementing heard count."""
        # Create test tune and person_tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Heard Count Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count)
            VALUES (%s, %s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'want to learn', 2))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.post(f"/api/my-tunes/{person_tune_id}/heard")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["heard_count"] == 3
        assert data["person_tune"]["heard_count"] == 3

    def test_increment_heard_count_only_for_want_to_learn(self, client, authenticated_user, db_conn, db_cursor):
        """Test that heard count can only be incremented for 'want to learn' status."""
        # Create test tune with 'learning' status
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Learning Status Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count)
            VALUES (%s, %s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'learning', 0))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.post(f"/api/my-tunes/{person_tune_id}/heard")
        
        assert response.status_code == 422  # Unprocessable Entity
        data = json.loads(response.data)
        assert data["success"] is False
        assert "want to learn" in data["error"].lower()

    def test_increment_heard_count_unauthorized(self, client, authenticated_user, db_conn, db_cursor):
        """Test that users cannot increment heard count for other users' tunes."""
        # Create another user's tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        other_person_id = 999
        
        # Create the other person
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (other_person_id, "Other", "User", f"other{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Other User Heard Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count)
            VALUES (%s, %s, %s, %s)
            RETURNING person_tune_id
        """, (other_person_id, tune_id, 'want to learn', 0))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.post(f"/api/my-tunes/{person_tune_id}/heard")
        
        assert response.status_code == 403  # Forbidden
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_person_tune_detail_requires_authentication(self, client):
        """Test that GET /api/my-tunes/<id> requires authentication."""
        response = client.get("/api/my-tunes/1")
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False
        assert "authentication" in data["error"].lower()

    def test_get_person_tune_detail_success(self, client, authenticated_user, db_conn, db_cursor):
        """Test successfully getting tune detail."""
        # Create test tune and person_tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Detail Tune {unique_id}", "Reel", 150))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'want to learn', 5, 'Test notes'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.get(f"/api/my-tunes/{person_tune_id}")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["person_tune"]["person_tune_id"] == person_tune_id
        assert data["person_tune"]["tune_name"] == f"Detail Tune {unique_id}"
        assert data["person_tune"]["tune_type"] == "Reel"
        assert data["person_tune"]["learn_status"] == "want to learn"
        assert data["person_tune"]["heard_count"] == 5
        assert data["person_tune"]["notes"] == "Test notes"
        assert data["person_tune"]["tunebook_count"] == 150
        assert data["person_tune"]["thesession_url"] == f"https://thesession.org/tunes/{tune_id}"
        assert "session_play_count" in data["person_tune"]

    def test_get_person_tune_detail_not_found(self, client, authenticated_user):
        """Test getting detail for non-existent tune."""
        with authenticated_user:
            response = client.get("/api/my-tunes/999999999")
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_get_person_tune_detail_unauthorized(self, client, db_conn, db_cursor):
        """Test that users cannot get details for other users' tunes."""
        from unittest.mock import patch
        from auth import User
        
        # Create a non-admin user
        unique_id = str(uuid.uuid4())[:8]
        non_admin_person_id = int(unique_id[:4], 16) % 1000 + 5000
        
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (non_admin_person_id, "NonAdmin", "User", f"nonadmin{unique_id}@example.com"))
        
        # Create another user's tune
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        other_person_id = 999
        
        # Create the other person
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
        """, (other_person_id, "Other", "User", f"other{unique_id}@example.com"))
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Other User Detail Tune {unique_id}", "Reel"))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
            RETURNING person_tune_id
        """, (other_person_id, tune_id, 'want to learn'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        # Create non-admin user and authenticate
        non_admin_user = User(
            user_id=9999,
            person_id=non_admin_person_id,
            username="nonadmin",
            is_system_admin=False,
            email=f"nonadmin{unique_id}@example.com"
        )
        
        with patch("auth.User.get_by_id") as mock_get_user:
            mock_get_user.return_value = non_admin_user
            
            with client.session_transaction() as sess:
                sess["_user_id"] = "9999"
                sess["_fresh"] = True
                sess["is_system_admin"] = False
                sess["admin_session_ids"] = []
            
            response = client.get(f"/api/my-tunes/{person_tune_id}")
        
        assert response.status_code == 403  # Forbidden
        data = json.loads(response.data)
        assert data["success"] is False
        assert ("permission" in data["error"].lower() or "unauthorized" in data["error"].lower())

    def test_get_person_tune_detail_with_session_play_count(self, client, authenticated_user, db_conn, db_cursor):
        """Test that tune detail includes session play count."""
        # Create test tune and person_tune
        unique_id = str(uuid.uuid4())[:8]
        tune_id = int(unique_id[:6], 16) % 100000 + 50000
        person_id = 2  # Match authenticated_user fixture person_id
        session_id = int(unique_id[2:6], 16) % 10000 + 1000
        
        # Create session
        db_cursor.execute("""
            INSERT INTO session (session_id, name, path)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO NOTHING
        """, (session_id, f"Test Session {unique_id}", f"test-session-{unique_id}"))
        
        # Add person to session
        db_cursor.execute("""
            INSERT INTO session_person (session_id, person_id)
            VALUES (%s, %s)
            ON CONFLICT (session_id, person_id) DO NOTHING
        """, (session_id, person_id))
        
        # Create session instance
        db_cursor.execute("""
            INSERT INTO session_instance (session_id, date)
            VALUES (%s, CURRENT_DATE)
            RETURNING session_instance_id
        """, (session_id,))
        session_instance_id = db_cursor.fetchone()[0]
        
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Session Play Tune {unique_id}", "Reel"))
        
        # Add tune to session instance
        db_cursor.execute("""
            INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number)
            VALUES (%s, %s, %s)
        """, (session_instance_id, tune_id, 1))
        
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status)
            VALUES (%s, %s, %s)
            RETURNING person_tune_id
        """, (person_id, tune_id, 'want to learn'))
        person_tune_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        with authenticated_user:
            response = client.get(f"/api/my-tunes/{person_tune_id}")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["person_tune"]["session_play_count"] >= 1
