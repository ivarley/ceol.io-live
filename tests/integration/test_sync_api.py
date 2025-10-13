"""
Integration tests for the sync API endpoint.

Tests the POST /api/my-tunes/sync endpoint including:
- Successful sync operations
- Error handling for API failures
- Progress tracking and status reporting
"""

import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_tunebook_response():
    """Mock tunebook response from thesession.org."""
    return {
        'tunebook': [
            {'id': 1, 'name': 'The Kesh', 'type': 'jig'},
            {'id': 2, 'name': 'The Banshee', 'type': 'reel'},
            {'id': 3, 'name': 'The Butterfly', 'type': 'slip jig'}
        ]
    }


@pytest.fixture
def mock_tune_metadata():
    """Mock tune metadata responses from thesession.org."""
    return {
        1: {'name': 'The Kesh', 'type': 'jig', 'tunebooks': 500},
        2: {'name': 'The Banshee', 'type': 'reel', 'tunebooks': 300},
        3: {'name': 'The Butterfly', 'type': 'slip jig', 'tunebooks': 450}
    }


def test_sync_requires_authentication(client):
    """Test that sync endpoint requires authentication."""
    response = client.post('/api/my-tunes/sync', json={})
    
    # Should return 401 or redirect
    assert response.status_code in [302, 401]


def test_sync_without_thesession_user_id(client, authenticated_user, db_conn, db_cursor):
    """Test sync fails when no thesession_user_id is available."""
    # Ensure person exists and has no thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = NULL WHERE person_id = %s
    """, (person_id,))
    db_conn.commit()
    
    # Make sync request without providing thesession_user_id
    with authenticated_user:
        response = client.post('/api/my-tunes/sync', json={})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    
    assert data['success'] is False
    assert 'thesession_user_id is required' in data['error']


def test_sync_with_invalid_thesession_user_id(client, authenticated_user, db_conn, db_cursor):
    """Test sync with invalid thesession_user_id."""
    # Test with non-numeric ID
    with authenticated_user:
        response = client.post('/api/my-tunes/sync', json={
            'thesession_user_id': 'invalid'
        })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Invalid thesession_user_id' in data['error']
    
    # Test with negative ID
    with authenticated_user:
        response = client.post('/api/my-tunes/sync', json={
            'thesession_user_id': -1
        })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Invalid thesession_user_id' in data['error']


def test_sync_with_invalid_learn_status(client, authenticated_user, db_conn, db_cursor):
    """Test sync with invalid learn_status."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    with authenticated_user:
        response = client.post('/api/my-tunes/sync', json={
            'learn_status': 'invalid_status'
        })
    
    assert response.status_code == 400
    data = json.loads(response.data)
    
    assert data['success'] is False
    assert 'Invalid learn_status' in data['error']


def test_sync_user_not_found_on_thesession(client, authenticated_user, db_conn, db_cursor):
    """Test sync when user is not found on thesession.org."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock 404 response from thesession.org
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 404
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'not found' in data['message'].lower()


def test_sync_thesession_api_timeout(client, authenticated_user, db_conn, db_cursor):
    """Test sync when thesession.org API times out."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock timeout exception
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 503
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'timed out' in data['message'].lower()


def test_sync_thesession_api_connection_error(client, authenticated_user, db_conn, db_cursor):
    """Test sync when cannot connect to thesession.org."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock connection error
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 503
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'could not connect' in data['message'].lower()


def test_sync_success_with_new_tunes(client, authenticated_user, db_conn, db_cursor, 
                                      mock_tunebook_response, mock_tune_metadata):
    """Test successful sync with new tunes."""
    # Clean up any existing person_tunes for this person first
    person_id = authenticated_user.person_id
    db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s", (person_id,))
    
    # Set thesession_user_id for the test user
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock the thesession API calls
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        def mock_api_call(url, timeout=None):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if '/tunebook' in url:
                mock_response.json.return_value = mock_tunebook_response
            elif '/tunes/' in url:
                tune_id = int(url.split('/tunes/')[1].split('?')[0])
                mock_response.json.return_value = mock_tune_metadata.get(tune_id, {})
            
            return mock_response
        
        mock_get.side_effect = mock_api_call
        
        # Make sync request
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['results']['tunes_fetched'] == 3
        assert data['results']['person_tunes_added'] == 3
        assert data['results']['person_tunes_skipped'] == 0
        assert len(data['results']['errors']) == 0


def test_sync_with_existing_tunes(client, authenticated_user, db_conn, db_cursor,
                                   mock_tunebook_response, mock_tune_metadata):
    """Test sync when some tunes already exist in collection."""
    # Clean up any existing person_tunes for this person first
    person_id = authenticated_user.person_id
    db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s", (person_id,))
    
    # Set thesession_user_id for the test user
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    
    # Pre-create one tune in the collection
    db_cursor.execute("""
        INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tune_id) DO NOTHING
    """, (1, 'The Kesh', 'Jig', 500))
    
    # Create person_tune
    db_cursor.execute("""
        INSERT INTO person_tune (person_id, tune_id, learn_status)
        VALUES (%s, %s, %s)
        ON CONFLICT (person_id, tune_id) DO UPDATE SET learn_status = EXCLUDED.learn_status
    """, (person_id, 1, 'learning'))
    db_conn.commit()
    
    # Mock the thesession API calls
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        def mock_api_call(url, timeout=None):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if '/tunebook' in url:
                mock_response.json.return_value = mock_tunebook_response
            elif '/tunes/' in url:
                tune_id = int(url.split('/tunes/')[1].split('?')[0])
                mock_response.json.return_value = mock_tune_metadata.get(tune_id, {})
            
            return mock_response
        
        mock_get.side_effect = mock_api_call
        
        # Make sync request
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['results']['tunes_fetched'] == 3
        assert data['results']['person_tunes_added'] == 2  # Only 2 new ones
        assert data['results']['person_tunes_skipped'] == 1  # One already existed
        
        # Verify existing tune status was preserved
        db_cursor.execute("""
            SELECT learn_status FROM person_tune
            WHERE person_id = %s AND tune_id = %s
        """, (person_id, 1))
        status = db_cursor.fetchone()[0]
        assert status == 'learning'  # Should still be 'learning', not 'want to learn'


def test_sync_empty_tunebook(client, authenticated_user, db_conn, db_cursor):
    """Test sync when user has an empty tunebook."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock empty tunebook response
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'tunebook': []}
        mock_get.return_value = mock_response
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['results']['tunes_fetched'] == 0
        assert data['results']['person_tunes_added'] == 0


def test_sync_with_retry_after_timeout(client, authenticated_user, db_conn, db_cursor,
                                        mock_tunebook_response, mock_tune_metadata):
    """Test sync succeeds after initial timeout with retry mechanism."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock the thesession API calls with initial timeout then success
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        import requests
        call_count = {'count': 0}
        
        def mock_api_call(url, timeout=None):
            call_count['count'] += 1
            
            # First call times out, subsequent calls succeed
            if call_count['count'] == 1:
                raise requests.exceptions.Timeout()
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if '/tunebook' in url:
                mock_response.json.return_value = mock_tunebook_response
            elif '/tunes/' in url:
                tune_id = int(url.split('/tunes/')[1].split('?')[0])
                mock_response.json.return_value = mock_tune_metadata.get(tune_id, {})
            
            return mock_response
        
        mock_get.side_effect = mock_api_call
        
        # Mock time.sleep to speed up test
        with patch('services.thesession_sync_service.time.sleep'):
            with authenticated_user:
                response = client.post('/api/my-tunes/sync', json={})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['results']['tunes_fetched'] == 3
            # Verify retry happened (more than 1 call to API)
            assert call_count['count'] > 1


def test_sync_fails_after_max_retries(client, authenticated_user, db_conn, db_cursor):
    """Test sync fails after exhausting all retry attempts."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock the thesession API to always timeout
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        # Mock time.sleep to speed up test
        with patch('services.thesession_sync_service.time.sleep'):
            with authenticated_user:
                response = client.post('/api/my-tunes/sync', json={})
            
            assert response.status_code == 503
            data = json.loads(response.data)
            
            assert data['success'] is False
            assert 'timed out' in data['message'].lower()
            assert 'attempts' in data['message'].lower()


def test_sync_no_retry_on_404(client, authenticated_user, db_conn, db_cursor):
    """Test sync doesn't retry on 404 errors (non-retryable)."""
    # Set thesession_user_id
    person_id = authenticated_user.person_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock 404 response
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 404
        data = json.loads(response.data)
        
        assert data['success'] is False
        # Should only be called once (no retries for 404)
        assert mock_get.call_count == 1


def test_sync_response_includes_progress_fields(client, authenticated_user, db_conn, db_cursor,
                                                 mock_tunebook_response, mock_tune_metadata):
    """Test sync response includes progress tracking fields."""
    # Clean up any existing person_tunes
    person_id = authenticated_user.person_id
    db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s", (person_id,))
    
    # Set thesession_user_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock the thesession API calls
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        def mock_api_call(url, timeout=None):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if '/tunebook' in url:
                mock_response.json.return_value = mock_tunebook_response
            elif '/tunes/' in url:
                tune_id = int(url.split('/tunes/')[1].split('?')[0])
                mock_response.json.return_value = mock_tune_metadata.get(tune_id, {})
            
            return mock_response
        
        mock_get.side_effect = mock_api_call
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify progress tracking fields are present
        assert 'status' in data['results']
        assert 'progress_percent' in data['results']
        assert data['results']['status'] in ['completed', 'completed_with_errors']
        assert data['results']['progress_percent'] == 100


def test_sync_partial_success_with_some_failures(client, authenticated_user, db_conn, db_cursor):
    """Test sync handles partial success when some tunes fail."""
    # Clean up any existing person_tunes
    person_id = authenticated_user.person_id
    db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s", (person_id,))
    
    # Make sure tune 2 doesn't exist in the tune table so it will fail
    db_cursor.execute("DELETE FROM tune WHERE tune_id = 2")
    
    # Set thesession_user_id
    db_cursor.execute("""
        UPDATE person SET thesession_user_id = %s WHERE person_id = %s
    """, (12345, person_id))
    db_conn.commit()
    
    # Mock tunebook with 3 tunes
    mock_tunebook = {
        'tunebook': [
            {'id': 1, 'name': 'The Kesh'},
            {'id': 2, 'name': 'The Banshee'},
            {'id': 3, 'name': 'The Butterfly'}
        ]
    }
    
    # Mock metadata for tunes 1 and 3, but tune 2 will fail
    mock_metadata = {
        1: {'name': 'The Kesh', 'type': 'jig', 'tunebooks': 500},
        3: {'name': 'The Butterfly', 'type': 'slip jig', 'tunebooks': 450}
    }
    
    with patch('services.thesession_sync_service.requests.get') as mock_get:
        def mock_api_call(url, timeout=None):
            mock_response = MagicMock()
            
            if '/tunebook' in url:
                mock_response.status_code = 200
                mock_response.json.return_value = mock_tunebook
            elif '/tunes/2' in url:
                # Tune 2 fails with 404
                mock_response.status_code = 404
            elif '/tunes/' in url:
                tune_id = int(url.split('/tunes/')[1].split('?')[0])
                mock_response.status_code = 200
                mock_response.json.return_value = mock_metadata.get(tune_id, {})
            
            return mock_response
        
        mock_get.side_effect = mock_api_call
        
        with authenticated_user:
            response = client.post('/api/my-tunes/sync', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should succeed overall but with errors
        assert data['success'] is True
        assert data['results']['tunes_fetched'] == 3
        assert data['results']['person_tunes_added'] == 2  # Only 2 succeeded
        assert len(data['results']['errors']) == 1  # One error for tune 2
        assert 'Tune #2' in data['results']['errors'][0]
