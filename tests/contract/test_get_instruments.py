"""
Contract test for GET /api/person/{id}/instruments endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestGetInstrumentsContract:
    """Contract tests for the get person instruments endpoint"""

    def test_get_instruments_success_response_structure(self, client, authenticated_user, sample_person_data):
        """Test that successful response matches expected contract"""
        person_id = sample_person_data['person_id']
        
        with authenticated_user:
            response = client.get(f'/api/person/{person_id}/instruments')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        
        # Validate instruments list structure
        instruments = data['data']
        assert isinstance(instruments, list)
        
        if instruments:
            for instrument in instruments:
                assert isinstance(instrument, str)
                # Should be one of the approved instruments
                approved_instruments = [
                    'fiddle', 'flute', 'tin whistle', 'low whistle', 
                    'uilleann pipes', 'concertina', 'button accordion', 
                    'piano accordion', 'bodhrán', 'harp', 'tenor banjo', 
                    'mandolin', 'guitar', 'bouzouki', 'viola'
                ]
                assert instrument in approved_instruments

    def test_get_instruments_empty_list(self, client, authenticated_user, sample_person_no_instruments):
        """Test person with no instruments returns empty list"""
        person_id = sample_person_no_instruments['person_id']
        
        with authenticated_user:
            response = client.get(f'/api/person/{person_id}/instruments')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data'] == []

    def test_get_instruments_multiple_instruments(self, client, authenticated_user, sample_person_with_instruments):
        """Test person with multiple instruments"""
        person_id = sample_person_with_instruments['person_id']
        expected_instruments = sample_person_with_instruments['instruments']
        
        with authenticated_user:
            response = client.get(f'/api/person/{person_id}/instruments')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['data'], list)
        assert len(data['data']) == len(expected_instruments)

    def test_get_instruments_unauthorized_access(self, client, sample_person_data):
        """Test that unauthorized users get 403 Forbidden"""
        person_id = sample_person_data['person_id']
        
        # No authentication provided
        response = client.get(f'/api/person/{person_id}/instruments')
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is False

    def test_get_instruments_nonexistent_person(self, client, authenticated_user):
        """Test that nonexistent person returns 404"""
        nonexistent_id = 99999
        
        with authenticated_user:
            response = client.get(f'/api/person/{nonexistent_id}/instruments')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data

    def test_get_instruments_invalid_person_id(self, client, authenticated_user):
        """Test that invalid person ID format returns 400 or 404"""
        invalid_id = "not_a_number"
        
        with authenticated_user:
            response = client.get(f'/api/person/{invalid_id}/instruments')
        
        assert response.status_code in [400, 404]

    def test_get_instruments_alphabetical_order(self, client, authenticated_user, sample_person_with_multiple_instruments):
        """Test that instruments are returned in alphabetical order"""
        person_id = sample_person_with_multiple_instruments['person_id']
        
        with authenticated_user:
            response = client.get(f'/api/person/{person_id}/instruments')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        instruments = data['data']
        
        if len(instruments) > 1:
            # Check if sorted alphabetically
            sorted_instruments = sorted(instruments)
            assert instruments == sorted_instruments