"""
Unit tests for PersonTune model.

Tests the PersonTune model class validation, business logic, and database operations
without requiring actual database connections.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from models.person_tune import PersonTune


class TestPersonTuneValidation:
    """Test PersonTune validation methods."""
    
    def test_valid_initialization(self):
        """Test PersonTune initialization with valid data."""
        person_tune = PersonTune(
            person_id=1,
            tune_id=100,
            learn_status='learning',
            heard_count=3
        )
        
        assert person_tune.person_id == 1
        assert person_tune.tune_id == 100
        assert person_tune.learn_status == 'learning'
        assert person_tune.heard_count == 3
        assert person_tune.learned_date is None
        assert person_tune.notes is None
    
    def test_default_values(self):
        """Test PersonTune initialization with default values."""
        person_tune = PersonTune()
        
        assert person_tune.learn_status == 'want to learn'
        assert person_tune.heard_count == 0
        assert person_tune.person_tune_id is None
        assert person_tune.person_id is None
        assert person_tune.tune_id is None
    
    def test_invalid_learn_status(self):
        """Test validation fails with invalid learn_status."""
        with pytest.raises(ValueError, match="learn_status must be one of"):
            PersonTune(learn_status='invalid_status')
    
    def test_negative_heard_count(self):
        """Test validation fails with negative heard count."""
        with pytest.raises(ValueError, match="heard_count must be non-negative"):
            PersonTune(heard_count=-1)
    
    def test_invalid_person_id(self):
        """Test validation fails with invalid person_id."""
        with pytest.raises(ValueError, match="person_id must be positive"):
            PersonTune(person_id=0)
        
        with pytest.raises(ValueError, match="person_id must be positive"):
            PersonTune(person_id=-5)
    
    def test_invalid_tune_id(self):
        """Test validation fails with invalid tune_id."""
        with pytest.raises(ValueError, match="tune_id must be positive"):
            PersonTune(tune_id=0)
        
        with pytest.raises(ValueError, match="tune_id must be positive"):
            PersonTune(tune_id=-10)
    
    def test_learned_date_with_non_learned_status(self):
        """Test validation fails when learned_date is set but status is not 'learned'."""
        learned_date = datetime.now(timezone.utc)
        
        with pytest.raises(ValueError, match="learned_date should only be set when learn_status is 'learned'"):
            PersonTune(
                learn_status='want to learn',
                learned_date=learned_date
            )
    
    def test_learned_status_without_learned_date(self):
        """Test that 'learned' status is allowed without learned_date."""
        # This should not raise an exception
        person_tune = PersonTune(learn_status='learned')
        assert person_tune.learn_status == 'learned'
        assert person_tune.learned_date is None
    
    def test_validate_for_save_missing_person_id(self):
        """Test validate_for_save fails when person_id is missing."""
        person_tune = PersonTune(tune_id=100)
        
        with pytest.raises(ValueError, match="person_id is required for save"):
            person_tune.validate_for_save()
    
    def test_validate_for_save_missing_tune_id(self):
        """Test validate_for_save fails when tune_id is missing."""
        person_tune = PersonTune(person_id=1)
        
        with pytest.raises(ValueError, match="tune_id is required for save"):
            person_tune.validate_for_save()
    
    def test_validate_for_save_success(self):
        """Test validate_for_save succeeds with required fields."""
        person_tune = PersonTune(person_id=1, tune_id=100)
        
        # Should not raise an exception
        person_tune.validate_for_save()


class TestPersonTuneStatusManagement:
    """Test PersonTune learning status management."""
    
    def test_set_learn_status_valid_change(self):
        """Test setting learn_status to a different valid value."""
        person_tune = PersonTune(learn_status='want to learn')
        
        result = person_tune.set_learn_status('learning')
        
        assert result is True
        assert person_tune.learn_status == 'learning'
    
    def test_set_learn_status_same_value(self):
        """Test setting learn_status to the same value returns False."""
        person_tune = PersonTune(learn_status='learning')
        
        result = person_tune.set_learn_status('learning')
        
        assert result is False
        assert person_tune.learn_status == 'learning'
    
    def test_set_learn_status_invalid_value(self):
        """Test setting learn_status to invalid value raises error."""
        person_tune = PersonTune()
        
        with pytest.raises(ValueError, match="learn_status must be one of"):
            person_tune.set_learn_status('invalid_status')
    
    @patch('models.person_tune.now_utc')
    def test_set_learn_status_to_learned_sets_date(self, mock_now):
        """Test that setting status to 'learned' sets learned_date."""
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_now.return_value = mock_date
        
        person_tune = PersonTune(learn_status='learning')
        person_tune.set_learn_status('learned')
        
        assert person_tune.learn_status == 'learned'
        assert person_tune.learned_date == mock_date
    
    @patch('models.person_tune.now_utc')
    def test_set_learn_status_from_learned_clears_date(self, mock_now):
        """Test that changing status from 'learned' clears learned_date."""
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        person_tune = PersonTune(
            learn_status='learned',
            learned_date=mock_date
        )
        person_tune.set_learn_status('learning')
        
        assert person_tune.learn_status == 'learning'
        assert person_tune.learned_date is None
    
    @patch('models.person_tune.PersonTune._update_in_database')
    def test_set_learn_status_updates_database_for_persisted_record(self, mock_update):
        """Test that set_learn_status calls database update for persisted records."""
        person_tune = PersonTune(person_tune_id=1, learn_status='want to learn')
        
        person_tune.set_learn_status('learning', changed_by='test_user')
        
        mock_update.assert_called_once_with('test_user')


class TestPersonTuneHeardCount:
    """Test PersonTune heard count management."""
    
    def test_increment_heard_count_valid(self):
        """Test incrementing heard count for 'want to learn' status."""
        person_tune = PersonTune(
            learn_status='want to learn',
            heard_count=2
        )
        
        result = person_tune.increment_heard_count()
        
        assert result == 3
        assert person_tune.heard_count == 3
    
    def test_increment_heard_count_invalid_status(self):
        """Test incrementing heard count fails for non-'want to learn' status."""
        person_tune = PersonTune(learn_status='learning')
        
        with pytest.raises(ValueError, match="Can only increment heard count for tunes with 'want to learn' status"):
            person_tune.increment_heard_count()
    
    @patch('models.person_tune.PersonTune._update_in_database')
    def test_increment_heard_count_updates_database_for_persisted_record(self, mock_update):
        """Test that increment_heard_count calls database update for persisted records."""
        person_tune = PersonTune(
            person_tune_id=1,
            learn_status='want to learn',
            heard_count=0
        )
        
        person_tune.increment_heard_count(changed_by='test_user')
        
        assert person_tune.heard_count == 1
        mock_update.assert_called_once_with('test_user')


class TestPersonTuneDatabaseOperations:
    """Test PersonTune database operations with mocked connections."""
    
    @patch('models.person_tune.get_db_connection')
    @patch('models.person_tune.save_to_history')
    @patch('models.person_tune.now_utc')
    def test_save_new_record(self, mock_now, mock_save_history, mock_get_conn):
        """Test saving a new PersonTune record."""
        # Setup mocks
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_now.return_value = mock_date
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock the INSERT returning values
        mock_cursor.fetchone.return_value = (123, mock_date, mock_date)
        
        # Create and save PersonTune
        person_tune = PersonTune(person_id=1, tune_id=100, learn_status='learning')
        result = person_tune.save(changed_by='test_user')
        
        # Verify database operations
        assert mock_cursor.execute.call_count == 4  # BEGIN, INSERT, history INSERT, COMMIT
        mock_cursor.execute.assert_any_call("BEGIN")
        mock_cursor.execute.assert_any_call("COMMIT")
        
        # Check INSERT call
        insert_call = mock_cursor.execute.call_args_list[1]
        assert "INSERT INTO person_tune" in insert_call[0][0]
        assert insert_call[0][1] == (1, 100, 'learning', 0, None, None)
        
        # Verify result
        assert result is person_tune
        assert person_tune.person_tune_id == 123
        assert person_tune.created_date == mock_date
        assert person_tune.last_modified_date == mock_date
    
    @patch('models.person_tune.get_db_connection')
    @patch('models.person_tune.save_to_history')
    def test_update_existing_record(self, mock_save_history, mock_get_conn):
        """Test updating an existing PersonTune record."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Create PersonTune with existing ID
        person_tune = PersonTune(
            person_tune_id=123,
            person_id=1,
            tune_id=100,
            learn_status='learned'
        )
        
        person_tune._update_in_database(changed_by='test_user')
        
        # Verify database operations
        mock_save_history.assert_called_once_with(
            mock_cursor, 'person_tune', 'UPDATE', 123, 'test_user'
        )
        
        # Check UPDATE call
        update_calls = [call for call in mock_cursor.execute.call_args_list 
                       if 'UPDATE person_tune' in str(call)]
        assert len(update_calls) == 1
        
        update_call = update_calls[0]
        assert "UPDATE person_tune" in update_call[0][0]
        assert "SET learn_status = %s" in update_call[0][0]
    
    @patch('models.person_tune.get_db_connection')
    def test_get_by_id_found(self, mock_get_conn):
        """Test retrieving PersonTune by ID when record exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock database response
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor.fetchone.return_value = (
            123, 1, 100, 'learning', 2, None, 'Test notes', mock_date, mock_date
        )
        
        result = PersonTune.get_by_id(123)
        
        # Verify query
        mock_cursor.execute.assert_called_once()
        query_call = mock_cursor.execute.call_args
        assert "SELECT person_tune_id" in query_call[0][0]
        assert query_call[0][1] == (123,)
        
        # Verify result
        assert result is not None
        assert result.person_tune_id == 123
        assert result.person_id == 1
        assert result.tune_id == 100
        assert result.learn_status == 'learning'
        assert result.heard_count == 2
        assert result.notes == 'Test notes'
    
    @patch('models.person_tune.get_db_connection')
    def test_get_by_id_not_found(self, mock_get_conn):
        """Test retrieving PersonTune by ID when record doesn't exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_cursor.fetchone.return_value = None
        
        result = PersonTune.get_by_id(999)
        
        assert result is None
    
    @patch('models.person_tune.get_db_connection')
    def test_get_by_person_and_tune(self, mock_get_conn):
        """Test retrieving PersonTune by person_id and tune_id."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor.fetchone.return_value = (
            123, 1, 100, 'want to learn', 0, None, None, mock_date, mock_date
        )
        
        result = PersonTune.get_by_person_and_tune(1, 100)
        
        # Verify query
        query_call = mock_cursor.execute.call_args
        assert "WHERE person_id = %s AND tune_id = %s" in query_call[0][0]
        assert query_call[0][1] == (1, 100)
        
        # Verify result
        assert result is not None
        assert result.person_id == 1
        assert result.tune_id == 100
    
    @patch('models.person_tune.get_db_connection')
    def test_get_for_person_with_filters(self, mock_get_conn):
        """Test retrieving PersonTunes for a person with filters."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor.fetchall.return_value = [
            (123, 1, 100, 'learning', 0, None, None, mock_date, mock_date),
            (124, 1, 101, 'learning', 1, None, 'Notes', mock_date, mock_date)
        ]
        
        results = PersonTune.get_for_person(
            person_id=1,
            learn_status_filter='learning',
            limit=10,
            offset=5
        )
        
        # Verify query
        query_call = mock_cursor.execute.call_args
        assert "WHERE person_id = %s" in query_call[0][0]
        assert "AND learn_status = %s" in query_call[0][0]
        assert "LIMIT %s" in query_call[0][0]
        assert "OFFSET %s" in query_call[0][0]
        assert query_call[0][1] == [1, 'learning', 10, 5]
        
        # Verify results
        assert len(results) == 2
        assert all(isinstance(pt, PersonTune) for pt in results)
        assert results[0].person_tune_id == 123
        assert results[1].person_tune_id == 124
    
    @patch('models.person_tune.get_db_connection')
    @patch('models.person_tune.save_to_history')
    def test_delete_existing_record(self, mock_save_history, mock_get_conn):
        """Test deleting an existing PersonTune record."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        mock_cursor.rowcount = 1  # Simulate successful deletion
        
        person_tune = PersonTune(person_tune_id=123)
        result = person_tune.delete(changed_by='test_user')
        
        # Verify database operations
        mock_save_history.assert_called_once_with(
            mock_cursor, 'person_tune', 'DELETE', 123, 'test_user'
        )
        
        delete_calls = [call for call in mock_cursor.execute.call_args_list 
                       if 'DELETE FROM person_tune' in str(call)]
        assert len(delete_calls) == 1
        
        # Verify result
        assert result is True
        assert person_tune.person_tune_id is None
    
    def test_delete_non_persisted_record(self):
        """Test deleting a non-persisted PersonTune record."""
        person_tune = PersonTune()  # No person_tune_id
        result = person_tune.delete()
        
        assert result is False
        assert person_tune.person_tune_id is None


class TestPersonTuneUtilityMethods:
    """Test PersonTune utility methods."""
    
    def test_to_dict(self):
        """Test converting PersonTune to dictionary."""
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        person_tune = PersonTune(
            person_tune_id=123,
            person_id=1,
            tune_id=100,
            learn_status='learned',
            heard_count=5,
            learned_date=mock_date,
            notes='Test notes',
            created_date=mock_date,
            last_modified_date=mock_date
        )
        
        result = person_tune.to_dict()
        
        expected = {
            'person_tune_id': 123,
            'person_id': 1,
            'tune_id': 100,
            'learn_status': 'learned',
            'heard_count': 5,
            'learned_date': mock_date.isoformat(),
            'notes': 'Test notes',
            'created_date': mock_date.isoformat(),
            'last_modified_date': mock_date.isoformat()
        }
        
        assert result == expected
    
    def test_to_dict_with_none_dates(self):
        """Test converting PersonTune to dictionary with None dates."""
        person_tune = PersonTune(person_id=1, tune_id=100)
        
        result = person_tune.to_dict()
        
        assert result['learned_date'] is None
        assert result['created_date'] is None
        assert result['last_modified_date'] is None
    
    def test_repr(self):
        """Test PersonTune string representation."""
        person_tune = PersonTune(
            person_tune_id=123,
            person_id=1,
            tune_id=100,
            learn_status='learning',
            heard_count=3
        )
        
        result = repr(person_tune)
        
        expected = (
            "PersonTune(person_tune_id=123, person_id=1, tune_id=100, "
            "learn_status='learning', heard_count=3)"
        )
        assert result == expected
    
    def test_equality(self):
        """Test PersonTune equality comparison."""
        mock_date = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        person_tune1 = PersonTune(
            person_tune_id=123,
            person_id=1,
            tune_id=100,
            learn_status='learned',  # Use 'learned' status to allow learned_date
            heard_count=2,
            learned_date=mock_date,
            notes='Test'
        )
        
        person_tune2 = PersonTune(
            person_tune_id=123,
            person_id=1,
            tune_id=100,
            learn_status='learned',  # Use 'learned' status to allow learned_date
            heard_count=2,
            learned_date=mock_date,
            notes='Test'
        )
        
        person_tune3 = PersonTune(
            person_tune_id=124,  # Different ID
            person_id=1,
            tune_id=100,
            learn_status='learned',  # Use 'learned' status to allow learned_date
            heard_count=2,
            learned_date=mock_date,
            notes='Test'
        )
        
        assert person_tune1 == person_tune2
        assert person_tune1 != person_tune3
        assert person_tune1 != "not a PersonTune"


class TestPersonTuneErrorHandling:
    """Test PersonTune error handling scenarios."""
    
    @patch('models.person_tune.get_db_connection')
    def test_save_database_error_rollback(self, mock_get_conn):
        """Test that database errors during save trigger rollback."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Simulate database error on the INSERT statement (second execute call)
        mock_cursor.execute.side_effect = [None, Exception("Database error"), None]
        
        person_tune = PersonTune(person_id=1, tune_id=100)
        
        with pytest.raises(Exception, match="Database error"):
            person_tune.save()
        
        # Verify rollback was called
        rollback_calls = [call for call in mock_cursor.execute.call_args_list 
                         if 'ROLLBACK' in str(call)]
        assert len(rollback_calls) == 1
    
    def test_update_in_database_without_id(self):
        """Test that _update_in_database raises error without person_tune_id."""
        person_tune = PersonTune()
        
        with pytest.raises(ValueError, match="Cannot update record without person_tune_id"):
            person_tune._update_in_database()
    
    def test_validate_for_save_calls_base_validation(self):
        """Test that validate_for_save calls the base _validate method."""
        # Create a valid PersonTune first, then modify it to have invalid data
        person_tune = PersonTune(person_id=1, tune_id=100)
        # Directly set invalid status to bypass __init__ validation
        person_tune.learn_status = 'invalid_status'
        
        with pytest.raises(ValueError, match="learn_status must be one of"):
            person_tune.validate_for_save()