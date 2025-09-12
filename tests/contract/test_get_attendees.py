"""
Contract test for GET /api/session_instance/{id}/attendees endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestGetAttendeesContract:
    """Contract tests for the get attendees endpoint"""

    def test_get_attendees_success_response_structure(self, client, sample_session_instance_data):
        """Test that successful response matches expected contract"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        
        # Validate data structure
        attendee_data = data['data']
        assert 'regulars' in attendee_data
        assert 'attendees' in attendee_data
        assert isinstance(attendee_data['regulars'], list)
        assert isinstance(attendee_data['attendees'], list)

    def test_get_attendees_regular_attendee_structure(self, client, sample_session_instance_data, sample_regular_attendee):
        """Test that regular attendee objects match expected structure"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        if data['data']['regulars']:
            regular = data['data']['regulars'][0]
            required_fields = ['person_id', 'display_name', 'instruments', 'attendance', 'is_regular']
            for field in required_fields:
                assert field in regular
            
            assert isinstance(regular['person_id'], int)
            assert isinstance(regular['display_name'], str)
            assert isinstance(regular['instruments'], list)
            assert regular['attendance'] in ['yes', 'maybe', 'no', None]
            assert regular['is_regular'] is True

    def test_get_attendees_unauthorized_access(self, client, sample_session_instance_data):
        """Test that unauthorized users get 403 Forbidden"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # No authentication provided
        response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is False
        assert 'error' in data

    def test_get_attendees_nonexistent_session(self, client, authenticated_user):
        """Test that nonexistent session returns 404"""
        nonexistent_id = 99999
        
        with authenticated_user:
            response = client.get(f'/api/session_instance/{nonexistent_id}/attendees')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is False

    def test_get_attendees_invalid_session_id(self, client, authenticated_user):
        """Test that invalid session ID format returns 400 or 404"""
        invalid_id = "not_a_number"
        
        with authenticated_user:
            response = client.get(f'/api/session_instance/{invalid_id}/attendees')
        
        assert response.status_code in [400, 404]