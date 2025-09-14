"""
Integration tests for bulk person import API endpoints.

Tests the two-stage bulk import process: CSV preprocessing and person saving.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import uuid
from datetime import datetime, date

from flask import url_for


@pytest.mark.integration
class TestBulkPersonImportAPI:
    """Test bulk person import API endpoints."""

    def setup_method(self):
        """Set up test session for each test."""
        self.session_data = None
        self.session_id = None

    def _create_test_session(self, db_conn, db_cursor):
        """Create a test session and return its ID."""
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"test-bulk-import-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country, initiation_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING session_id
            """,
            (
                f"Test Bulk Import Session {unique_id}",
                session_path,
                "Austin",
                "TX",
                "USA",
                datetime(2023, 1, 1).date(),
            ),
        )
        session_id = db_cursor.fetchone()[0]
        db_conn.commit()
        return session_id

    def _get_authenticated_admin(self, client, authenticated_admin_user):
        """Get authenticated admin user for testing."""
        return authenticated_admin_user

    def test_bulk_import_preprocess_missing_session(self, client):
        """Test preprocess endpoint with non-existent session."""
        response = client.post("/api/session/99999/bulk-import/preprocess", json={
            "csv_data": "John Smith,john@example.com"
        })
        # Authentication happens first, so we expect 401 not 404
        assert response.status_code == 401

    def test_bulk_import_preprocess_no_data(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint with missing CSV data."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert not data["success"]
            assert "csv_data" in data["message"]

    def test_bulk_import_preprocess_basic_csv(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint with basic CSV data."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # Use unique test emails to avoid conflicts with existing test data
        unique_id = str(uuid.uuid4())[:8]
        csv_data = f"John Smith,john-{unique_id}@bulktest.com,Fiddle,Flute\nJane Doe,jane-{unique_id}@bulktest.com,Guitar"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            assert "processed_people" in data
            assert len(data["processed_people"]) == 2
            
            # Check first person
            person1 = data["processed_people"][0]
            assert person1["first_name"] == "John"
            assert person1["last_name"] == "Smith"
            assert person1["email"] == f"john-{unique_id}@bulktest.com"
            assert set(person1["instruments"]) == {"fiddle", "flute"}
            assert not person1["is_duplicate"]
            
            # Check second person
            person2 = data["processed_people"][1]
            assert person2["first_name"] == "Jane"
            assert person2["last_name"] == "Doe"
            assert person2["email"] == f"jane-{unique_id}@bulktest.com"
            assert person2["instruments"] == ["guitar"]
            assert not person2["is_duplicate"]

    def test_bulk_import_preprocess_with_headers(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint with CSV headers."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        csv_data = """First Name,Last Name,Email,Regular,City,State,Country,Instruments
John,Smith,john@example.com,yes,Dallas,TX,USA,"Fiddle,Flute"
Jane,Doe,jane@example.com,no,Houston,TX,USA,Guitar"""
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            assert len(data["processed_people"]) == 2
            
            # Check first person with regular flag
            person1 = data["processed_people"][0]
            assert person1["is_regular"] == True
            assert person1["city"] == "Dallas"
            assert person1["state"] == "TX"
            assert person1["country"] == "USA"
            
            # Check second person
            person2 = data["processed_people"][1]
            assert person2["is_regular"] == False

    def test_bulk_import_preprocess_duplicate_detection(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test duplicate detection in preprocess endpoint."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # Use unique email for this test
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"john-dup-{unique_id}@example.com"
        
        # Create existing person
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
            """,
            ("John", "Smith", test_email)
        )
        existing_person_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        csv_data = f"John Smith,{test_email},Fiddle\nJane Doe,jane-dup-{unique_id}@example.com,Guitar"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            
            # Check duplicate detection
            person1 = data["processed_people"][0]
            assert person1["is_duplicate"] == True
            assert person1["duplicate_reason"] == "email"
            assert person1["existing_person_id"] == existing_person_id
            
            person2 = data["processed_people"][1]
            assert person2["is_duplicate"] == False

    def test_bulk_import_save_missing_session(self, client):
        """Test save endpoint with non-existent session."""
        response = client.post("/api/session/99999/bulk-import/save", json={
            "processed_people": []
        })
        # Authentication happens first, so we expect 401 not 404
        assert response.status_code == 401

    def test_bulk_import_save_no_data(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test save endpoint with missing processed people data."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/save", json={})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert not data["success"]
            assert "processed_people" in data["message"]

    def test_bulk_import_save_success(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test successful bulk save of processed people."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # Use unique emails to avoid conflicts  
        unique_id = str(uuid.uuid4())[:8]
        processed_people = [
            {
                "first_name": "John",
                "last_name": "Smith",
                "email": f"john-save-{unique_id}@bulktest.com",
                "city": "Austin",
                "state": "TX",
                "country": "USA",
                "instruments": ["fiddle", "flute"],
                "is_regular": True,
                "is_duplicate": False
            },
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": f"jane-save-{unique_id}@bulktest.com",
                "city": "Austin",
                "state": "TX", 
                "country": "USA",
                "instruments": ["guitar"],
                "is_regular": False,
                "is_duplicate": False
            }
        ]
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/save", json={
                "processed_people": processed_people
            })
            if response.status_code != 200:
                print(f"Response status: {response.status_code}")
                print(f"Response data: {response.data.decode()}")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            assert data["created_count"] == 2
            assert data["skipped_count"] == 0
            
            # Verify people were created in database
            db_cursor.execute("SELECT first_name, last_name, email FROM person WHERE email IN (%s, %s)",
                            (f"john-save-{unique_id}@bulktest.com", f"jane-save-{unique_id}@bulktest.com"))
            people = db_cursor.fetchall()
            assert len(people) == 2
            
            # Verify instruments were created
            db_cursor.execute(
                """SELECT pi.instrument FROM person_instrument pi 
                   JOIN person p ON pi.person_id = p.person_id 
                   WHERE p.email = %s ORDER BY pi.instrument""",
                (f"john-save-{unique_id}@bulktest.com",)
            )
            instruments = [row[0] for row in db_cursor.fetchall()]
            assert set(instruments) == {"fiddle", "flute"}
            
            # Verify session_person records were created
            db_cursor.execute(
                """SELECT sp.is_regular FROM session_person sp 
                   JOIN person p ON sp.person_id = p.person_id 
                   WHERE sp.session_id = %s AND p.email = %s""",
                (session_id, f"john-save-{unique_id}@bulktest.com")
            )
            is_regular = db_cursor.fetchone()[0]
            assert is_regular == True

    def test_bulk_import_save_skip_duplicates(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test bulk save skips duplicates correctly."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # Use unique email for this test
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"john-skip-{unique_id}@example.com"
        
        # Create existing person
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
            """,
            ("John", "Smith", test_email)
        )
        existing_person_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        processed_people = [
            {
                "first_name": "John",
                "last_name": "Smith", 
                "email": test_email,
                "instruments": ["fiddle"],
                "is_regular": True,
                "is_duplicate": True,
                "existing_person_id": existing_person_id
            },
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": f"jane-skip-{unique_id}@example.com",
                "instruments": ["guitar"],
                "is_regular": False,
                "is_duplicate": False
            }
        ]
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/save", json={
                "processed_people": processed_people
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            assert data["created_count"] == 1  # Only Jane was created
            assert data["skipped_count"] == 1  # John was skipped
            
            # Verify only Jane was created
            db_cursor.execute("SELECT COUNT(*) FROM person WHERE email = %s", (f"jane-skip-{unique_id}@example.com",))
            count = db_cursor.fetchone()[0]
            assert count == 1

    def test_bulk_import_invalid_csv_format(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint with malformed CSV data."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # CSV with missing required name field
        csv_data = ",john@example.com,Fiddle"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 400
            data = json.loads(response.data)
            assert not data["success"]
            assert "name" in data["message"].lower()

    def test_bulk_import_permission_denied(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test bulk import endpoints require admin permissions."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        # Test without authentication
        response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
            "csv_data": "John Smith,john@example.com"
        })
        assert response.status_code == 401 or response.status_code == 403

    def test_bulk_import_preprocess_full_name_field(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint with Full Name field that gets split."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        csv_data = "John Michael Smith,john@example.com,Fiddle"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            
            person = data["processed_people"][0]
            assert person["first_name"] == "John Michael"
            assert person["last_name"] == "Smith"  # Last word becomes last name

    def test_bulk_import_preprocess_phone_detection(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test preprocess endpoint detects phone numbers."""
        session_id = self._create_test_session(db_conn, db_cursor)
        
        csv_data = "John Smith,512-555-1234,Fiddle"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            
            person = data["processed_people"][0]
            assert person["sms_number"] == "512-555-1234"
            assert person["email"] is None

    def test_bulk_import_defaults_from_session(self, client, db_conn, db_cursor, authenticated_admin_user):
        """Test that missing city/state/country default from session."""
        # Update the test session with specific location data
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"test-bulk-import-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country, initiation_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING session_id
            """,
            (
                f"Test Session {unique_id}",
                session_path,
                "Houston",
                "TX",
                "USA",
                datetime(2023, 1, 1).date(),
            ),
        )
        session_id = db_cursor.fetchone()[0]
        db_conn.commit()
        
        csv_data = "John Smith,john@example.com,Fiddle"
        
        with authenticated_admin_user:
            response = client.post(f"/api/session/{session_id}/bulk-import/preprocess", json={
                "csv_data": csv_data
            })
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"]
            
            person = data["processed_people"][0]
            assert person["city"] == "Houston"
            assert person["state"] == "TX"
            assert person["country"] == "USA"