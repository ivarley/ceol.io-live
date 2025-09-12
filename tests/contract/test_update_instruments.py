"""
Contract test for PUT /api/person/{id}/instruments endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestUpdateInstrumentsContract:
    """Contract tests for the update person instruments endpoint"""

    def test_update_instruments_success_response_structure(self, client, authenticated_user, sample_person_data):
        """Test that successful update response matches expected contract"""
        person_id = sample_person_data['person_id']
        
        update_data = {
            'instruments': ['fiddle', 'tin whistle']
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True

    def test_update_instruments_empty_list(self, client, authenticated_user, sample_person_data):
        """Test updating to empty instruments list"""
        person_id = sample_person_data['person_id']
        
        update_data = {
            'instruments': []
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_update_instruments_single_instrument(self, client, authenticated_user, sample_person_data):
        """Test updating to single instrument"""
        person_id = sample_person_data['person_id']
        
        update_data = {
            'instruments': ['bodhrán']
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_update_instruments_multiple_instruments(self, client, authenticated_user, sample_person_data):
        """Test updating to multiple instruments"""
        person_id = sample_person_data['person_id']
        
        update_data = {
            'instruments': ['fiddle', 'flute', 'piano accordion', 'bodhrán']
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_update_instruments_invalid_instrument(self, client, authenticated_user, sample_person_data):
        """Test that invalid instrument names are rejected"""
        person_id = sample_person_data['person_id']
        
        invalid_data = {
            'instruments': ['fiddle', 'electric_guitar', 'drums']  # Invalid instruments
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(invalid_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data

    def test_update_instruments_missing_instruments_field(self, client, authenticated_user, sample_person_data):
        """Test that missing instruments field returns 400"""
        person_id = sample_person_data['person_id']
        
        incomplete_data = {}  # Missing instruments field
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(incomplete_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_update_instruments_non_list_instruments(self, client, authenticated_user, sample_person_data):
        """Test that non-list instruments field returns 400"""
        person_id = sample_person_data['person_id']
        
        invalid_data = {
            'instruments': 'fiddle'  # Should be a list, not a string
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(invalid_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_update_instruments_unauthorized_access(self, client, sample_person_data):
        """Test that unauthorized users get 403 Forbidden"""
        person_id = sample_person_data['person_id']
        
        update_data = {
            'instruments': ['fiddle']
        }
        
        # No authentication provided
        response = client.put(
            f'/api/person/{person_id}/instruments',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 403

    def test_update_instruments_nonexistent_person(self, client, authenticated_user):
        """Test that nonexistent person returns 404"""
        nonexistent_id = 99999
        
        update_data = {
            'instruments': ['fiddle']
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{nonexistent_id}/instruments',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    def test_update_instruments_duplicate_instruments(self, client, authenticated_user, sample_person_data):
        """Test that duplicate instruments in the same request are handled properly"""
        person_id = sample_person_data['person_id']
        
        duplicate_data = {
            'instruments': ['fiddle', 'fiddle', 'tin whistle']
        }
        
        with authenticated_user:
            response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(duplicate_data),
                content_type='application/json'
            )
        
        # Should either succeed (deduplicating) or return 400
        assert response.status_code in [200, 400]