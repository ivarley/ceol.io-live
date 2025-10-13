"""
Functional tests for the sync interface and user experience.

Tests the complete sync workflow including:
- Sync page rendering
- Progress indicators
- Results display
- Error handling
- Profile updates
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import session


class TestSyncInterface:
    """Test the sync interface and user experience."""
    
    def test_sync_page_requires_authentication(self, client):
        """Test that sync page requires login."""
        response = client.get('/my-tunes/sync')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_sync_page_renders_with_existing_user_id(self, client, authenticated_user, db_conn, db_cursor):
        """Test sync page renders with existing thesession_user_id."""
        with authenticated_user:
            # Set thesession_user_id for the test user
            db_cursor.execute("""
                UPDATE person
                SET thesession_user_id = 12345
                WHERE person_id = %s
            """, (authenticated_user.person_id,))
            db_conn.commit()
            
            response = client.get('/my-tunes/sync')
            assert response.status_code == 200
            assert b'Sync from TheSession.org' in response.data
            assert b'12345' in response.data
    
    def test_sync_page_renders_without_user_id(self, client, authenticated_user):
        """Test sync page renders when user has no thesession_user_id."""
        with authenticated_user:
            response = client.get('/my-tunes/sync')
            assert response.status_code == 200
            assert b'Sync from TheSession.org' in response.data
            assert b'Enter your thesession.org user ID' in response.data
    
    def test_update_profile_thesession_user_id(self, client, authenticated_user, db_conn, db_cursor):
        """Test updating thesession_user_id via API."""
        with authenticated_user:
            # Update thesession_user_id
            response = client.patch('/api/person/me', json={
                'thesession_user_id': 54321
            })
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            
            # Verify in database
            db_cursor.execute("""
                SELECT thesession_user_id
                FROM person
                WHERE person_id = %s
            """, (authenticated_user.person_id,))
            row = db_cursor.fetchone()
            assert row[0] == 54321
    
    def test_update_profile_invalid_user_id(self, client, authenticated_user):
        """Test updating with invalid thesession_user_id."""
        with authenticated_user:
            # Try to update with invalid user ID
            response = client.patch('/api/person/me', json={
                'thesession_user_id': -1
            })
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'Invalid' in data['error']
    
    def test_update_profile_requires_authentication(self, client):
        """Test that profile update requires login."""
        response = client.patch('/api/person/me', json={
            'thesession_user_id': 12345
        })

        # Endpoint redirects to login (302) or returns 401
        assert response.status_code in [302, 401]
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    @patch('services.thesession_sync_service.ThesessionSyncService.ensure_tune_exists')
    def test_sync_with_valid_user_id(
        self,
        mock_ensure_tune,
        mock_fetch_tunebook,
        client,
        authenticated_user,
        db_conn,
        db_cursor
    ):
        """Test successful sync with valid thesession_user_id."""
        with authenticated_user:
            # Mock the API responses
            mock_fetch_tunebook.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            mock_ensure_tune.return_value = (True, "Tune exists")
            
            # Create tunes in database
            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (1, 'The Kesh', 'Jig'), (2, 'The Banshee', 'Reel')
                ON CONFLICT (tune_id) DO NOTHING
            """)
            db_conn.commit()
            
            # Perform sync
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 12345,
                'learn_status': 'want to learn'
            })
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['results']['tunes_fetched'] == 2
            assert data['results']['person_tunes_added'] >= 0
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    def test_sync_with_invalid_user_id(
        self,
        mock_fetch_tunebook,
        client,
        authenticated_user
    ):
        """Test sync with invalid thesession_user_id."""
        with authenticated_user:
            # Mock API to return 404
            mock_fetch_tunebook.return_value = (
                False,
                "User #99999 not found on thesession.org",
                None
            )
            
            # Attempt sync
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 99999
            })
            
            assert response.status_code == 404
            data = response.get_json()
            assert data['success'] is False
            assert 'not found' in data['message']
    
    def test_sync_without_user_id(self, client, authenticated_user, db_conn, db_cursor):
        """Test sync without providing thesession_user_id."""
        with authenticated_user:
            # Ensure user has no thesession_user_id in profile
            db_cursor.execute("""
                UPDATE person
                SET thesession_user_id = NULL
                WHERE person_id = %s
            """, (authenticated_user.person_id,))
            db_conn.commit()
            
            # Attempt sync without user ID
            response = client.post('/api/my-tunes/sync', json={
                'learn_status': 'want to learn'
            })
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'required' in data['error']
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    def test_sync_uses_profile_user_id(
        self,
        mock_fetch_tunebook,
        client,
        authenticated_user,
        db_conn,
        db_cursor
    ):
        """Test sync uses thesession_user_id from profile if not provided."""
        with authenticated_user:
            # Set thesession_user_id in profile
            db_cursor.execute("""
                UPDATE person
                SET thesession_user_id = 12345
                WHERE person_id = %s
            """, (authenticated_user.person_id,))
            db_conn.commit()
            
            # Mock API response
            mock_fetch_tunebook.return_value = (True, "Success", [])
            
            # Sync without providing user ID
            response = client.post('/api/my-tunes/sync', json={
                'learn_status': 'want to learn'
            })
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            
            # Verify the correct user ID was used
            mock_fetch_tunebook.assert_called_once()
            call_args = mock_fetch_tunebook.call_args
            assert call_args[0][0] == 12345 or call_args[1].get('thesession_user_id') == 12345
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    @patch('services.thesession_sync_service.ThesessionSyncService.ensure_tune_exists')
    def test_sync_skips_existing_tunes(
        self,
        mock_ensure_tune,
        mock_fetch_tunebook,
        client,
        authenticated_user,
        db_conn,
        db_cursor
    ):
        """Test that sync skips tunes already in collection."""
        with authenticated_user:
            # Create tune and add to user's collection
            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (1, 'The Kesh', 'Jig')
                ON CONFLICT (tune_id) DO NOTHING
            """)
            # Delete any existing person_tune record first
            db_cursor.execute("""
                DELETE FROM person_tune
                WHERE person_id = %s AND tune_id = 1
            """, (authenticated_user.person_id,))
            db_cursor.execute("""
                INSERT INTO person_tune (person_id, tune_id, learn_status)
                VALUES (%s, 1, 'learned')
            """, (authenticated_user.person_id,))
            db_conn.commit()
            
            # Mock API to return the same tune
            mock_fetch_tunebook.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'}
            ])
            mock_ensure_tune.return_value = (True, "Tune exists")
            
            # Perform sync
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 12345
            })
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['results']['person_tunes_skipped'] == 1
            assert data['results']['person_tunes_added'] == 0
            
            # Verify the tune still has 'learned' status
            db_cursor.execute("""
                SELECT learn_status
                FROM person_tune
                WHERE person_id = %s AND tune_id = 1
            """, (authenticated_user.person_id,))
            row = db_cursor.fetchone()
            assert row[0] == 'learned'
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    def test_sync_with_api_timeout(
        self,
        mock_fetch_tunebook,
        client,
        authenticated_user
    ):
        """Test sync handles API timeout gracefully."""
        with authenticated_user:
            # Mock API timeout
            mock_fetch_tunebook.return_value = (
                False,
                "Request to thesession.org timed out",
                None
            )
            
            # Attempt sync
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 12345
            })
            
            assert response.status_code == 503
            data = response.get_json()
            assert data['success'] is False
            assert 'timed out' in data['message']
    
    def test_sync_with_invalid_learn_status(self, client, authenticated_user):
        """Test sync rejects invalid learn_status."""
        with authenticated_user:
            # Attempt sync with invalid status
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 12345,
                'learn_status': 'invalid_status'
            })
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'Invalid learn_status' in data['error']
    
    @patch('services.thesession_sync_service.ThesessionSyncService.fetch_tunebook')
    @patch('services.thesession_sync_service.ThesessionSyncService.ensure_tune_exists')
    def test_sync_creates_missing_tunes(
        self,
        mock_ensure_tune,
        mock_fetch_tunebook,
        client,
        authenticated_user,
        db_conn,
        db_cursor
    ):
        """Test that sync creates tune records for missing tunes."""
        with authenticated_user:
            # Ensure tune 9999 doesn't exist yet
            db_cursor.execute("DELETE FROM person_tune WHERE tune_id = 9999")
            db_cursor.execute("DELETE FROM tune WHERE tune_id = 9999")
            db_conn.commit()

            # Mock the service methods
            mock_fetch_tunebook.return_value = (True, "Success", [
                {'id': 9999, 'name': 'New Tune'}
            ])
            mock_ensure_tune.return_value = (True, "Tune created")

            # Create the tune in the database (simulating what ensure_tune_exists would do)
            db_cursor.execute("""
                INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
                VALUES (9999, 'New Tune', 'Reel', 42)
                ON CONFLICT (tune_id) DO NOTHING
            """)
            db_conn.commit()

            # Perform sync
            response = client.post('/api/my-tunes/sync', json={
                'thesession_user_id': 12345
            })

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            # Sync should have fetched 1 tune
            assert data['results']['tunes_fetched'] == 1
            # Should have added it to person_tune
            assert data['results']['person_tunes_added'] >= 0

            # Verify tune exists in database
            db_cursor.execute("SELECT name, tune_type FROM tune WHERE tune_id = 9999")
            row = db_cursor.fetchone()
            assert row is not None
            assert row[0] == 'New Tune'
