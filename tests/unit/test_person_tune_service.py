"""
Unit tests for PersonTuneService.

Tests the PersonTuneService class business logic and CRUD operations
with mocked PersonTune model dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from services.person_tune_service import PersonTuneService
from models.person_tune import PersonTune


class TestPersonTuneServiceCreate:
    """Test PersonTuneService create operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    @patch('services.person_tune_service.PersonTune')
    def test_create_person_tune_success(self, mock_person_tune_class):
        """Test successful creation of a new PersonTune."""
        # Mock the class methods
        mock_person_tune_class.get_by_person_and_tune.return_value = None
        mock_person_tune_class.DEFAULT_LEARN_STATUS = 'want to learn'
        
        # Mock the instance
        mock_instance = MagicMock()
        mock_instance.person_tune_id = 123
        mock_person_tune_class.return_value = mock_instance
        mock_instance.save.return_value = mock_instance
        
        success, message, result = self.service.create_person_tune(
            person_id=1,
            tune_id=100,
            learn_status='learning',
            notes='Test notes',
            changed_by='test_user'
        )
        
        # Verify the result
        assert success is True
        assert message == "PersonTune created successfully"
        assert result is mock_instance
        
        # Verify PersonTune was created with correct parameters
        mock_person_tune_class.assert_called_once_with(
            person_id=1,
            tune_id=100,
            learn_status='learning',
            notes='Test notes'
        )
        
        # Verify save was called
        mock_instance.save.assert_called_once_with(changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_create_person_tune_already_exists(self, mock_person_tune_class):
        """Test creation fails when PersonTune already exists."""
        # Mock existing PersonTune
        existing_tune = MagicMock()
        mock_person_tune_class.get_by_person_and_tune.return_value = existing_tune
        
        success, message, result = self.service.create_person_tune(
            person_id=1,
            tune_id=100
        )
        
        assert success is False
        assert "already exists" in message
        assert result is None
        
        # Verify no new instance was created
        mock_person_tune_class.assert_not_called()
    
    @patch('services.person_tune_service.PersonTune')
    def test_create_person_tune_validation_error(self, mock_person_tune_class):
        """Test creation fails with validation error."""
        mock_person_tune_class.get_by_person_and_tune.return_value = None
        mock_person_tune_class.side_effect = ValueError("Invalid learn_status")
        
        success, message, result = self.service.create_person_tune(
            person_id=1,
            tune_id=100,
            learn_status='invalid_status'
        )
        
        assert success is False
        assert "Validation error" in message
        assert "Invalid learn_status" in message
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_create_person_tune_database_error(self, mock_person_tune_class):
        """Test creation fails with database error."""
        mock_person_tune_class.get_by_person_and_tune.return_value = None
        mock_instance = MagicMock()
        mock_person_tune_class.return_value = mock_instance
        mock_instance.save.side_effect = Exception("Database connection failed")
        
        success, message, result = self.service.create_person_tune(
            person_id=1,
            tune_id=100
        )
        
        assert success is False
        assert "Error creating PersonTune" in message
        assert "Database connection failed" in message
        assert result is None


class TestPersonTuneServiceRead:
    """Test PersonTuneService read operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tune_by_id_success(self, mock_person_tune_class):
        """Test successful retrieval by ID."""
        mock_tune = MagicMock()
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        result = self.service.get_person_tune_by_id(123)
        
        assert result is mock_tune
        mock_person_tune_class.get_by_id.assert_called_once_with(123)
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tune_by_id_not_found(self, mock_person_tune_class):
        """Test retrieval by ID when not found."""
        mock_person_tune_class.get_by_id.return_value = None
        
        result = self.service.get_person_tune_by_id(999)
        
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tune_by_id_exception(self, mock_person_tune_class):
        """Test retrieval by ID with exception."""
        mock_person_tune_class.get_by_id.side_effect = Exception("Database error")
        
        result = self.service.get_person_tune_by_id(123)
        
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tune_by_person_and_tune_success(self, mock_person_tune_class):
        """Test successful retrieval by person and tune IDs."""
        mock_tune = MagicMock()
        mock_person_tune_class.get_by_person_and_tune.return_value = mock_tune
        
        result = self.service.get_person_tune_by_person_and_tune(1, 100)
        
        assert result is mock_tune
        mock_person_tune_class.get_by_person_and_tune.assert_called_once_with(1, 100)
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tunes_success(self, mock_person_tune_class):
        """Test successful retrieval of person's tunes."""
        mock_tunes = [MagicMock(), MagicMock()]
        mock_person_tune_class.get_for_person.return_value = mock_tunes
        
        result = self.service.get_person_tunes(
            person_id=1,
            learn_status_filter='learning',
            limit=10,
            offset=5
        )
        
        assert result == mock_tunes
        mock_person_tune_class.get_for_person.assert_called_once_with(
            person_id=1,
            learn_status_filter='learning',
            limit=10,
            offset=5
        )
    
    @patch('services.person_tune_service.PersonTune')
    def test_get_person_tunes_exception(self, mock_person_tune_class):
        """Test retrieval of person's tunes with exception."""
        mock_person_tune_class.get_for_person.side_effect = Exception("Database error")
        
        result = self.service.get_person_tunes(person_id=1)
        
        assert result == []


class TestPersonTuneServiceUpdate:
    """Test PersonTuneService update operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_learn_status_success(self, mock_person_tune_class):
        """Test successful learning status update."""
        mock_tune = MagicMock()
        mock_tune.set_learn_status.return_value = True
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.update_learn_status(
            person_tune_id=123,
            new_status='learned',
            changed_by='test_user'
        )
        
        assert success is True
        assert "Status updated to 'learned' successfully" == message
        assert result is mock_tune
        
        mock_tune.set_learn_status.assert_called_once_with('learned', changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_learn_status_not_found(self, mock_person_tune_class):
        """Test status update when PersonTune not found."""
        mock_person_tune_class.get_by_id.return_value = None
        
        success, message, result = self.service.update_learn_status(
            person_tune_id=999,
            new_status='learned'
        )
        
        assert success is False
        assert "not found" in message
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_learn_status_no_change(self, mock_person_tune_class):
        """Test status update when status is already the same."""
        mock_tune = MagicMock()
        mock_tune.set_learn_status.return_value = False
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.update_learn_status(
            person_tune_id=123,
            new_status='learning'
        )
        
        assert success is False
        assert "Status was already 'learning'" == message
        assert result is mock_tune
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_learn_status_validation_error(self, mock_person_tune_class):
        """Test status update with validation error."""
        mock_tune = MagicMock()
        mock_tune.set_learn_status.side_effect = ValueError("Invalid status")
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.update_learn_status(
            person_tune_id=123,
            new_status='invalid'
        )
        
        assert success is False
        assert "Validation error" in message
        assert "Invalid status" in message
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_increment_heard_count_success(self, mock_person_tune_class):
        """Test successful heard count increment."""
        mock_tune = MagicMock()
        mock_tune.increment_heard_count.return_value = 3
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.increment_heard_count(
            person_tune_id=123,
            changed_by='test_user'
        )
        
        assert success is True
        assert "Heard count incremented to 3" == message
        assert result == 3
        
        mock_tune.increment_heard_count.assert_called_once_with(changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_increment_heard_count_not_found(self, mock_person_tune_class):
        """Test heard count increment when PersonTune not found."""
        mock_person_tune_class.get_by_id.return_value = None
        
        success, message, result = self.service.increment_heard_count(person_tune_id=999)
        
        assert success is False
        assert "not found" in message
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_increment_heard_count_validation_error(self, mock_person_tune_class):
        """Test heard count increment with validation error."""
        mock_tune = MagicMock()
        mock_tune.increment_heard_count.side_effect = ValueError("Invalid status for increment")
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.increment_heard_count(person_tune_id=123)
        
        assert success is False
        assert "Validation error" in message
        assert "Invalid status for increment" in message
        assert result is None
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_person_tune_status_and_notes(self, mock_person_tune_class):
        """Test updating both status and notes."""
        mock_tune = MagicMock()
        mock_tune.learn_status = 'want to learn'
        mock_tune.notes = 'Old notes'
        mock_tune.set_learn_status.return_value = True
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.update_person_tune(
            person_tune_id=123,
            learn_status='learning',
            notes='New notes',
            changed_by='test_user'
        )
        
        assert success is True
        assert "Updated status to 'learning', notes successfully" == message
        assert result is mock_tune
        
        mock_tune.set_learn_status.assert_called_once_with('learning', changed_by='test_user')
        assert mock_tune.notes == 'New notes'
        mock_tune.save.assert_called_once_with(changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_update_person_tune_no_changes(self, mock_person_tune_class):
        """Test updating PersonTune with no actual changes."""
        mock_tune = MagicMock()
        mock_tune.learn_status = 'learning'
        mock_tune.notes = 'Same notes'
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message, result = self.service.update_person_tune(
            person_tune_id=123,
            learn_status='learning',  # Same as current
            notes='Same notes'        # Same as current
        )
        
        assert success is True
        assert message == "No changes were made"
        assert result is mock_tune
        
        # Verify save was not called since no changes
        mock_tune.save.assert_not_called()


class TestPersonTuneServiceDelete:
    """Test PersonTuneService delete operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    @patch('services.person_tune_service.PersonTune')
    def test_delete_person_tune_success(self, mock_person_tune_class):
        """Test successful deletion of PersonTune."""
        mock_tune = MagicMock()
        mock_tune.delete.return_value = True
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message = self.service.delete_person_tune(
            person_tune_id=123,
            changed_by='test_user'
        )
        
        assert success is True
        assert message == "PersonTune deleted successfully"
        
        mock_tune.delete.assert_called_once_with(changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_delete_person_tune_not_found(self, mock_person_tune_class):
        """Test deletion when PersonTune not found."""
        mock_person_tune_class.get_by_id.return_value = None
        
        success, message = self.service.delete_person_tune(person_tune_id=999)
        
        assert success is False
        assert "not found" in message
    
    @patch('services.person_tune_service.PersonTune')
    def test_delete_person_tune_failed(self, mock_person_tune_class):
        """Test deletion failure."""
        mock_tune = MagicMock()
        mock_tune.delete.return_value = False
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message = self.service.delete_person_tune(person_tune_id=123)
        
        assert success is False
        assert message == "Failed to delete PersonTune"
    
    @patch('services.person_tune_service.PersonTune')
    def test_delete_person_tune_exception(self, mock_person_tune_class):
        """Test deletion with exception."""
        mock_tune = MagicMock()
        mock_tune.delete.side_effect = Exception("Database error")
        mock_person_tune_class.get_by_id.return_value = mock_tune
        
        success, message = self.service.delete_person_tune(person_tune_id=123)
        
        assert success is False
        assert "Error deleting PersonTune" in message
        assert "Database error" in message


class TestPersonTuneServiceBulkOperations:
    """Test PersonTuneService bulk operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    def test_bulk_create_person_tunes_all_success(self):
        """Test bulk creation where all tunes are created successfully."""
        with patch.object(self.service, 'create_person_tune') as mock_create:
            # Mock successful creation for all tunes
            mock_create.side_effect = [
                (True, "PersonTune created successfully", MagicMock(person_tune_id=1)),
                (True, "PersonTune created successfully", MagicMock(person_tune_id=2)),
                (True, "PersonTune created successfully", MagicMock(person_tune_id=3))
            ]
            
            success, message, results = self.service.bulk_create_person_tunes(
                person_id=1,
                tune_ids=[100, 101, 102],
                learn_status='learning',
                changed_by='test_user'
            )
            
            assert success is True
            assert "Successfully created 3 PersonTunes" == message
            assert len(results['created']) == 3
            assert len(results['skipped']) == 0
            assert len(results['errors']) == 0
            assert results['total_processed'] == 3
            
            # Verify all create calls were made
            assert mock_create.call_count == 3
            mock_create.assert_any_call(
                person_id=1, tune_id=100, learn_status='learning', changed_by='test_user'
            )
    
    def test_bulk_create_person_tunes_mixed_results(self):
        """Test bulk creation with mixed success, skip, and error results."""
        with patch.object(self.service, 'create_person_tune') as mock_create:
            mock_create.side_effect = [
                (True, "PersonTune created successfully", MagicMock(person_tune_id=1)),
                (False, "PersonTune already exists for person 1 and tune 101", None),
                (False, "Validation error: Invalid tune_id", None)
            ]
            
            success, message, results = self.service.bulk_create_person_tunes(
                person_id=1,
                tune_ids=[100, 101, 102]
            )
            
            assert success is False
            assert "Created 1, skipped 1, failed 1" == message
            assert len(results['created']) == 1
            assert len(results['skipped']) == 1
            assert len(results['errors']) == 1
            assert results['total_processed'] == 3
    
    def test_bulk_create_person_tunes_all_existing(self):
        """Test bulk creation where all tunes already exist."""
        with patch.object(self.service, 'create_person_tune') as mock_create:
            mock_create.side_effect = [
                (False, "PersonTune already exists for person 1 and tune 100", None),
                (False, "PersonTune already exists for person 1 and tune 101", None)
            ]
            
            success, message, results = self.service.bulk_create_person_tunes(
                person_id=1,
                tune_ids=[100, 101]
            )
            
            assert success is True
            assert "All 2 PersonTunes already existed" == message
            assert len(results['created']) == 0
            assert len(results['skipped']) == 2
            assert len(results['errors']) == 0


class TestPersonTuneServiceStatistics:
    """Test PersonTuneService statistics methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    def test_get_learning_status_summary(self):
        """Test getting learning status summary."""
        # Create mock PersonTune objects
        mock_tunes = [
            MagicMock(learn_status='want to learn'),
            MagicMock(learn_status='want to learn'),
            MagicMock(learn_status='learning'),
            MagicMock(learn_status='learned'),
            MagicMock(learn_status='learned'),
            MagicMock(learn_status='learned')
        ]
        
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.return_value = mock_tunes
            
            result = self.service.get_learning_status_summary(person_id=1)
            
            expected = {
                'want to learn': 2,
                'learning': 1,
                'learned': 3,
                'total': 6
            }
            
            assert result == expected
            mock_get_tunes.assert_called_once_with(1)
    
    def test_get_learning_status_summary_empty(self):
        """Test getting learning status summary with no tunes."""
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.return_value = []
            
            result = self.service.get_learning_status_summary(person_id=1)
            
            expected = {
                'want to learn': 0,
                'learning': 0,
                'learned': 0,
                'total': 0
            }
            
            assert result == expected
    
    def test_get_learning_status_summary_exception(self):
        """Test getting learning status summary with exception."""
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.side_effect = Exception("Database error")
            
            result = self.service.get_learning_status_summary(person_id=1)
            
            expected = {
                'want to learn': 0,
                'learning': 0,
                'learned': 0,
                'total': 0
            }
            
            assert result == expected
    
    def test_get_heard_count_statistics(self):
        """Test getting heard count statistics."""
        # Create mock PersonTune objects with different heard counts
        mock_tunes = [
            MagicMock(heard_count=0),  # Never heard
            MagicMock(heard_count=1),  # Heard once
            MagicMock(heard_count=3),  # Heard multiple times
            MagicMock(heard_count=5),  # Heard multiple times
            MagicMock(heard_count=0)   # Never heard
        ]
        
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.return_value = mock_tunes
            
            result = self.service.get_heard_count_statistics(person_id=1)
            
            expected = {
                'total_tunes': 5,
                'total_heard_count': 9,  # 0+1+3+5+0
                'average_heard_count': 1.8,  # 9/5
                'max_heard_count': 5,
                'tunes_never_heard': 2,  # Count of 0s
                'tunes_heard_multiple_times': 2  # Count of >1
            }
            
            assert result == expected
            mock_get_tunes.assert_called_once_with(1, learn_status_filter='want to learn')
    
    def test_get_heard_count_statistics_empty(self):
        """Test getting heard count statistics with no tunes."""
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.return_value = []
            
            result = self.service.get_heard_count_statistics(person_id=1)
            
            expected = {
                'total_tunes': 0,
                'total_heard_count': 0,
                'average_heard_count': 0.0,
                'max_heard_count': 0,
                'tunes_never_heard': 0,
                'tunes_heard_multiple_times': 0
            }
            
            assert result == expected
    
    def test_get_heard_count_statistics_exception(self):
        """Test getting heard count statistics with exception."""
        with patch.object(self.service, 'get_person_tunes') as mock_get_tunes:
            mock_get_tunes.side_effect = Exception("Database error")
            
            result = self.service.get_heard_count_statistics(person_id=1)
            
            expected = {
                'total_tunes': 0,
                'total_heard_count': 0,
                'average_heard_count': 0.0,
                'max_heard_count': 0,
                'tunes_never_heard': 0,
                'tunes_heard_multiple_times': 0
            }
            
            assert result == expected


class TestPersonTuneServiceIntegration:
    """Test PersonTuneService integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PersonTuneService()
    
    @patch('services.person_tune_service.PersonTune')
    def test_create_and_update_workflow(self, mock_person_tune_class):
        """Test a typical create and update workflow."""
        # Mock creation
        mock_person_tune_class.get_by_person_and_tune.return_value = None
        mock_person_tune_class.DEFAULT_LEARN_STATUS = 'want to learn'
        
        mock_instance = MagicMock()
        mock_instance.person_tune_id = 123
        mock_person_tune_class.return_value = mock_instance
        mock_instance.save.return_value = mock_instance
        
        # Create PersonTune
        success, message, created_tune = self.service.create_person_tune(
            person_id=1,
            tune_id=100,
            changed_by='test_user'
        )
        
        assert success is True
        assert created_tune is mock_instance
        
        # Mock update
        mock_person_tune_class.get_by_id.return_value = mock_instance
        mock_instance.set_learn_status.return_value = True
        
        # Update status
        success, message, updated_tune = self.service.update_learn_status(
            person_tune_id=123,
            new_status='learning',
            changed_by='test_user'
        )
        
        assert success is True
        assert updated_tune is mock_instance
        mock_instance.set_learn_status.assert_called_with('learning', changed_by='test_user')
    
    @patch('services.person_tune_service.PersonTune')
    def test_increment_heard_count_workflow(self, mock_person_tune_class):
        """Test heard count increment workflow."""
        mock_instance = MagicMock()
        mock_instance.increment_heard_count.return_value = 1
        mock_person_tune_class.get_by_id.return_value = mock_instance
        
        # First increment
        success, message, count = self.service.increment_heard_count(
            person_tune_id=123,
            changed_by='test_user'
        )
        
        assert success is True
        assert count == 1
        assert "Heard count incremented to 1" == message
        
        # Second increment
        mock_instance.increment_heard_count.return_value = 2
        success, message, count = self.service.increment_heard_count(
            person_tune_id=123,
            changed_by='test_user'
        )
        
        assert success is True
        assert count == 2
        assert "Heard count incremented to 2" == message
        
        # Verify both calls were made
        assert mock_instance.increment_heard_count.call_count == 2