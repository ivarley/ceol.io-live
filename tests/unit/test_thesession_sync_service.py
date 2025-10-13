"""
Unit tests for ThesessionSyncService.

Tests the thesession.org sync service with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.thesession_sync_service import ThesessionSyncService


class TestThesessionSyncService:
    """Test suite for ThesessionSyncService."""
    
    @pytest.fixture
    def sync_service(self):
        """Create a ThesessionSyncService instance."""
        return ThesessionSyncService()
    
    @pytest.fixture
    def mock_tunebook_response(self):
        """Mock tunebook API response."""
        return {
            'tunebook': [
                {'id': 1, 'name': 'The Kesh', 'type': 'jig'},
                {'id': 2, 'name': 'The Banshee', 'type': 'reel'},
                {'id': 3, 'name': 'The Butterfly', 'type': 'slip jig'}
            ]
        }
    
    @pytest.fixture
    def mock_tune_metadata_response(self):
        """Mock tune details API response."""
        return {
            'id': 1,
            'name': 'The Kesh',
            'type': 'jig',
            'tunebooks': 1234
        }
    
    # Test fetch_tunebook
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_success(self, mock_get, sync_service, mock_tunebook_response):
        """Test successful tunebook fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tunebook_response
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(12345)
        
        assert success is True
        assert "Successfully fetched 3 tunes" in message
        assert len(tunebook) == 3
        assert tunebook[0]['id'] == 1
        assert tunebook[0]['name'] == 'The Kesh'
        mock_get.assert_called_once()
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_user_not_found(self, mock_get, sync_service):
        """Test tunebook fetch with non-existent user."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(99999)
        
        assert success is False
        assert "not found" in message.lower()
        assert tunebook is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_server_error(self, mock_get, sync_service):
        """Test tunebook fetch with server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(12345)
        
        assert success is False
        assert "status: 500" in message
        assert tunebook is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_timeout(self, mock_get, sync_service):
        """Test tunebook fetch with timeout."""
        mock_get.side_effect = Exception("Timeout")
        
        success, message, tunebook = sync_service.fetch_tunebook(12345)
        
        assert success is False
        assert tunebook is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_invalid_data(self, mock_get, sync_service):
        """Test tunebook fetch with invalid response data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'invalid': 'data'}
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(12345)
        
        assert success is False
        assert "Invalid tunebook data" in message
        assert tunebook is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_empty(self, mock_get, sync_service):
        """Test tunebook fetch with empty tunebook."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'tunebook': []}
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(12345)
        
        assert success is True
        assert "Successfully fetched 0 tunes" in message
        assert len(tunebook) == 0
    
    # Test fetch_tune_metadata
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tune_metadata_success(self, mock_get, sync_service, mock_tune_metadata_response):
        """Test successful tune metadata fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tune_metadata_response
        mock_get.return_value = mock_response
        
        success, message, metadata = sync_service.fetch_tune_metadata(1)
        
        assert success is True
        assert "Successfully fetched" in message
        assert metadata['tune_id'] == 1
        assert metadata['name'] == 'The Kesh'
        assert metadata['tune_type'] == 'Jig'  # Should be title case
        assert metadata['tunebook_count'] == 1234
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tune_metadata_not_found(self, mock_get, sync_service):
        """Test tune metadata fetch with non-existent tune."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        success, message, metadata = sync_service.fetch_tune_metadata(99999)
        
        assert success is False
        assert "not found" in message.lower()
        assert metadata is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tune_metadata_missing_fields(self, mock_get, sync_service):
        """Test tune metadata fetch with missing required fields."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 1}  # Missing name and type
        mock_get.return_value = mock_response
        
        success, message, metadata = sync_service.fetch_tune_metadata(1)
        
        assert success is False
        assert "Invalid tune data" in message
        assert metadata is None
    
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tune_metadata_no_tunebook_count(self, mock_get, sync_service):
        """Test tune metadata fetch with missing tunebook count."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 1,
            'name': 'The Kesh',
            'type': 'jig'
            # No 'tunebooks' field
        }
        mock_get.return_value = mock_response
        
        success, message, metadata = sync_service.fetch_tune_metadata(1)
        
        assert success is True
        assert metadata['tunebook_count'] == 0  # Should default to 0
    
    # Test ensure_tune_exists
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_ensure_tune_exists_already_exists(self, mock_get_conn, sync_service):
        """Test ensure_tune_exists when tune already exists."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = (1,)  # Tune exists
        mock_get_conn.return_value = mock_conn
        
        success, message = sync_service.ensure_tune_exists(1)
        
        assert success is True
        assert "already exists" in message
        mock_cur.execute.assert_called_once()  # Only SELECT, no INSERT
    
    @patch('services.thesession_sync_service.save_to_history')
    @patch('services.thesession_sync_service.get_db_connection')
    def test_ensure_tune_exists_creates_new(self, mock_get_conn, mock_save_history, sync_service):
        """Test ensure_tune_exists creates new tune."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Tune doesn't exist
        mock_get_conn.return_value = mock_conn
        
        # Mock fetch_tune_metadata
        with patch.object(sync_service, 'fetch_tune_metadata') as mock_fetch:
            mock_fetch.return_value = (True, "Success", {
                'tune_id': 1,
                'name': 'The Kesh',
                'tune_type': 'Jig',
                'tunebook_count': 1234
            })
            
            success, message = sync_service.ensure_tune_exists(1)
            
            assert success is True
            assert "Created tune" in message
            assert "The Kesh" in message
            assert mock_cur.execute.call_count == 2  # SELECT + INSERT
            mock_conn.commit.assert_called_once()
            mock_save_history.assert_called_once()
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_ensure_tune_exists_fetch_fails(self, mock_get_conn, sync_service):
        """Test ensure_tune_exists when API fetch fails."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Tune doesn't exist
        mock_get_conn.return_value = mock_conn
        
        # Mock fetch_tune_metadata to fail
        with patch.object(sync_service, 'fetch_tune_metadata') as mock_fetch:
            mock_fetch.return_value = (False, "API error", None)
            
            success, message = sync_service.ensure_tune_exists(1)
            
            assert success is False
            assert "Could not fetch" in message
            mock_conn.rollback.assert_not_called()  # No transaction started
    
    # Test sync_tunebook_to_person
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_tunebook_to_person_success(self, mock_get_conn, sync_service):
        """Test successful tunebook sync."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        # Mock fetchone to return None (person_tune doesn't exist)
        mock_cur.fetchone.return_value = None
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            # Mock ensure_tune_exists
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Tune already exists")
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345
                )
                
                assert success is True
                assert results['tunes_fetched'] == 2
                assert results['person_tunes_added'] == 2
                assert results['person_tunes_skipped'] == 0
                assert len(results['errors']) == 0
                mock_conn.commit.assert_called()
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_tunebook_to_person_with_duplicates(self, mock_get_conn, sync_service):
        """Test tunebook sync with existing person_tunes."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        # Mock fetchone to alternate between existing and new
        mock_cur.fetchone.side_effect = [(1,), None]  # First exists, second doesn't
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            # Mock ensure_tune_exists
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Tune already exists")
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345
                )
                
                assert success is True
                assert results['person_tunes_added'] == 1
                assert results['person_tunes_skipped'] == 1
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_tunebook_to_person_creates_missing_tunes(self, mock_get_conn, sync_service):
        """Test tunebook sync creates missing tune records."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        mock_cur.fetchone.return_value = None
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'}
            ])
            
            # Mock ensure_tune_exists to indicate tune was created
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Created tune #1: The Kesh")
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345
                )
                
                assert success is True
                assert results['tunes_created'] == 1
                assert results['person_tunes_added'] == 1
    
    def test_sync_tunebook_to_person_fetch_fails(self, sync_service):
        """Test tunebook sync when fetch fails."""
        # Mock fetch_tunebook to fail
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch:
            mock_fetch.return_value = (False, "API error", None)
            
            success, message, results = sync_service.sync_tunebook_to_person(
                person_id=1,
                thesession_user_id=12345
            )
            
            assert success is False
            assert "API error" in message
            assert results['tunes_fetched'] == 0
            assert len(results['errors']) > 0
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_tunebook_to_person_handles_errors(self, mock_get_conn, sync_service):
        """Test tunebook sync handles individual tune errors."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        mock_cur.fetchone.return_value = None
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            # Mock ensure_tune_exists to fail for second tune
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.side_effect = [
                    (True, "Tune already exists"),
                    (False, "API error")
                ]
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345
                )
                
                assert results['person_tunes_added'] == 1
                assert len(results['errors']) == 1
                assert "Tune #2" in results['errors'][0]
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_tunebook_to_person_missing_tune_id(self, mock_get_conn, sync_service):
        """Test tunebook sync handles entries with missing tune IDs."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        # Mock fetch_tunebook with entry missing ID
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'name': 'The Kesh'},  # Missing 'id'
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            # Mock ensure_tune_exists
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Tune already exists")
                mock_cur.fetchone.return_value = None
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345
                )
                
                assert results['person_tunes_added'] == 1  # Only second tune
                assert len(results['errors']) == 1  # Error for missing ID
    
    # Test get_sync_preview
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_get_sync_preview_success(self, mock_get_conn, sync_service):
        """Test sync preview with mixed existing and new tunes."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        # Mock fetchone to return: person_tune exists, person_tune doesn't exist, person_tune doesn't exist
        # For the second call, tune exists in tune table
        # For the third call, tune doesn't exist in tune table
        mock_cur.fetchone.side_effect = [
            (1,),    # person_tune exists for tune 1
            None,    # person_tune doesn't exist for tune 2
            (2,),    # tune 2 exists in tune table
            None,    # person_tune doesn't exist for tune 3
            None     # tune 3 doesn't exist in tune table
        ]
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch:
            mock_fetch.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'},
                {'id': 3, 'name': 'The Butterfly'}
            ])
            
            success, message, preview = sync_service.get_sync_preview(
                person_id=1,
                thesession_user_id=12345
            )
            
            assert success is True
            assert preview['total_tunes'] == 3
            assert preview['existing_tunes'] == 1
            assert preview['new_tunes'] == 2
            assert preview['missing_from_db'] == 1
            assert "2 new tunes" in message
            assert "1 already in collection" in message
    
    def test_get_sync_preview_fetch_fails(self, sync_service):
        """Test sync preview when fetch fails."""
        # Mock fetch_tunebook to fail
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch:
            mock_fetch.return_value = (False, "API error", None)
            
            success, message, preview = sync_service.get_sync_preview(
                person_id=1,
                thesession_user_id=12345
            )
            
            assert success is False
            assert "API error" in message
            assert preview['total_tunes'] == 0
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_get_sync_preview_all_existing(self, mock_get_conn, sync_service):
        """Test sync preview when all tunes already exist."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        
        # All person_tunes exist
        mock_cur.fetchone.return_value = (1,)
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch:
            mock_fetch.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            success, message, preview = sync_service.get_sync_preview(
                person_id=1,
                thesession_user_id=12345
            )
            
            assert success is True
            assert preview['new_tunes'] == 0
            assert preview['existing_tunes'] == 2
            assert "0 new tunes" in message

    # Test retry mechanism
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_with_retry_success_after_failure(self, mock_get, mock_sleep, sync_service):
        """Test tunebook fetch succeeds after initial timeout with retry."""
        import requests
        
        # First call times out, second call succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'tunebook': [{'id': 1, 'name': 'The Kesh'}]}
        
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            mock_response
        ]
        
        success, message, tunebook = sync_service.fetch_tunebook(12345, retry=True)
        
        assert success is True
        assert len(tunebook) == 1
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1  # Slept once between retries
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_with_retry_exhausted(self, mock_get, mock_sleep, sync_service):
        """Test tunebook fetch fails after all retries exhausted."""
        import requests
        
        # All calls time out
        mock_get.side_effect = requests.exceptions.Timeout()
        
        success, message, tunebook = sync_service.fetch_tunebook(12345, retry=True)
        
        assert success is False
        assert "after 3 attempts" in message
        assert tunebook is None
        assert mock_get.call_count == 3  # MAX_RETRIES
        assert mock_sleep.call_count == 2  # Slept between attempts
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_no_retry_on_404(self, mock_get, mock_sleep, sync_service):
        """Test tunebook fetch doesn't retry on 404 (non-retryable error)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        success, message, tunebook = sync_service.fetch_tunebook(12345, retry=True)
        
        assert success is False
        assert "not found" in message.lower()
        assert tunebook is None
        assert mock_get.call_count == 1  # No retries for 404
        assert mock_sleep.call_count == 0
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tunebook_retry_disabled(self, mock_get, mock_sleep, sync_service):
        """Test tunebook fetch doesn't retry when retry=False."""
        import requests
        
        mock_get.side_effect = requests.exceptions.Timeout()
        
        success, message, tunebook = sync_service.fetch_tunebook(12345, retry=False)
        
        assert success is False
        assert "timed out" in message.lower()
        assert tunebook is None
        assert mock_get.call_count == 1  # No retries
        assert mock_sleep.call_count == 0
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_fetch_tune_metadata_with_retry_success(self, mock_get, mock_sleep, sync_service):
        """Test tune metadata fetch succeeds after retry."""
        import requests
        
        # First call fails with connection error, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 1,
            'name': 'The Kesh',
            'type': 'jig',
            'tunebooks': 500
        }
        
        mock_get.side_effect = [
            requests.exceptions.ConnectionError(),
            mock_response
        ]
        
        success, message, metadata = sync_service.fetch_tune_metadata(1, retry=True)
        
        assert success is True
        assert metadata['name'] == 'The Kesh'
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('services.thesession_sync_service.time.sleep')
    @patch('services.thesession_sync_service.requests.get')
    def test_retry_exponential_backoff(self, mock_get, mock_sleep, sync_service):
        """Test retry mechanism uses exponential backoff."""
        import requests
        
        mock_get.side_effect = requests.exceptions.Timeout()
        
        sync_service.fetch_tunebook(12345, retry=True)
        
        # Check that sleep was called with increasing delays
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2  # Two sleeps for 3 attempts
        assert sleep_calls[0] == sync_service.RETRY_DELAY  # First delay
        assert sleep_calls[1] == sync_service.RETRY_DELAY * sync_service.RETRY_BACKOFF  # Second delay (exponential)
    
    # Test progress tracking
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_with_progress_callback(self, mock_get_conn, sync_service):
        """Test sync calls progress callback with status updates."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        mock_cur.fetchone.return_value = None
        
        progress_updates = []
        
        def progress_callback(progress):
            progress_updates.append(progress.copy())
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [
                {'id': 1, 'name': 'The Kesh'},
                {'id': 2, 'name': 'The Banshee'}
            ])
            
            # Mock ensure_tune_exists
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Tune already exists")
                
                success, message, results = sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345,
                    progress_callback=progress_callback
                )
                
                assert success is True
                assert len(progress_updates) > 0
                
                # Check that progress updates include status and progress_percent
                for update in progress_updates:
                    assert 'status' in update
                    assert 'progress_percent' in update
                
                # Check final update shows completion
                final_update = progress_updates[-1]
                assert final_update['status'] in ['completed', 'completed_with_errors']
                assert final_update['progress_percent'] == 100
    
    @patch('services.thesession_sync_service.get_db_connection')
    def test_sync_progress_includes_all_fields(self, mock_get_conn, sync_service):
        """Test sync progress updates include all result fields."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        mock_cur.fetchone.return_value = None
        
        progress_updates = []
        
        def progress_callback(progress):
            progress_updates.append(progress.copy())
        
        # Mock fetch_tunebook
        with patch.object(sync_service, 'fetch_tunebook') as mock_fetch_tb:
            mock_fetch_tb.return_value = (True, "Success", [{'id': 1}])
            
            with patch.object(sync_service, 'ensure_tune_exists') as mock_ensure:
                mock_ensure.return_value = (True, "Created tune #1")
                
                sync_service.sync_tunebook_to_person(
                    person_id=1,
                    thesession_user_id=12345,
                    progress_callback=progress_callback
                )
                
                # Check that all updates have required fields
                for update in progress_updates:
                    assert 'tunes_fetched' in update
                    assert 'tunes_created' in update
                    assert 'person_tunes_added' in update
                    assert 'person_tunes_skipped' in update
                    assert 'errors' in update
                    assert 'status' in update
                    assert 'progress_percent' in update
