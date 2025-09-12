"""
Contract test for POST /api/session_instance/{id}/attendees/checkin endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestCheckinAttendeeContract:
    """Contract tests for the checkin attendee endpoint"""

    def test_checkin_success_response_structure(self, client, admin_user, sample_session_instance_data, sample_person_data):
        """Test that successful checkin response matches expected contract"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        checkin_data = {
            'person_id': person_id,
            'attendance': 'yes'
        }
        
        with admin_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        if response.status_code != 200:
            print(f"Error response: {response.data.decode()}")
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        
        # Validate attendee info structure
        attendee_info = data['data']
        required_fields = ['person_id', 'display_name', 'instruments', 'attendance', 'is_regular']
        for field in required_fields:
            assert field in attendee_info
        
        assert attendee_info['person_id'] == person_id
        assert attendee_info['attendance'] == 'yes'

    def test_checkin_with_comment(self, client, admin_user, sample_session_instance_data, sample_person_data):
        """Test checkin with optional comment"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        checkin_data = {
            'person_id': person_id,
            'attendance': 'maybe',
            'comment': 'Bringing my fiddle'
        }
        
        with admin_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        if response.status_code != 200:
            print(f"Debug - person_id in request: {person_id}")
            print(f"Debug - sample_user_data person_id: {sample_user_data['person_id']}")
            print(f"Error response: {response.data.decode()}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_checkin_invalid_attendance_value(self, client, authenticated_user, sample_session_instance_data, sample_person_data):
        """Test that invalid attendance values are rejected"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        invalid_data = {
            'person_id': person_id,
            'attendance': 'invalid_value'
        }
        
        with authenticated_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(invalid_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_checkin_missing_required_fields(self, client, authenticated_user, sample_session_instance_data):
        """Test that missing required fields return 400"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # Missing person_id
        incomplete_data = {
            'attendance': 'yes'
        }
        
        with authenticated_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(incomplete_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_checkin_unauthorized_access(self, client, sample_session_instance_data, sample_person_data):
        """Test that unauthorized users get 403 Forbidden"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        checkin_data = {
            'person_id': person_id,
            'attendance': 'yes'
        }
        
        # No authentication provided
        response = client.post(
            f'/api/session_instance/{session_instance_id}/attendees/checkin',
            data=json.dumps(checkin_data),
            content_type='application/json'
        )
        
        assert response.status_code == 401

    def test_checkin_nonexistent_session(self, client, authenticated_user, sample_person_data):
        """Test checkin to nonexistent session returns 404"""
        nonexistent_session_id = 99999
        person_id = sample_person_data['person_id']
        
        checkin_data = {
            'person_id': person_id,
            'attendance': 'yes'
        }
        
        with authenticated_user:
            response = client.post(
                f'/api/session_instance/{nonexistent_session_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code == 404

    def test_checkin_duplicate_attendance_returns_409(self, client, admin_user, sample_session_instance_data, sample_person_data):
        """Test that checking in the same person twice returns 409 Conflict or updates existing"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        checkin_data = {
            'person_id': person_id,
            'attendance': 'yes'
        }
        
        with admin_user:
            # First checkin
            response1 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            # Second checkin (duplicate)
            response2 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        # Should either update (200) or conflict (409)
        assert response2.status_code in [200, 409]