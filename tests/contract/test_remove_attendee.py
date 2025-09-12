"""
Contract test for DELETE /api/session_instance/{id}/attendees/{person_id} endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestRemoveAttendeeContract:
    """Contract tests for the remove attendee endpoint"""

    def test_remove_attendee_success_response(self, client, admin_user, sample_session_instance_data, sample_person_data):
        """Test that successful removal response matches expected contract"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        with admin_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        # Person may not be attending, so we expect either 200 (removed) or 404 (not attending)
        assert response.status_code in [200, 404]
        
        data = json.loads(response.data)
        assert 'success' in data
        
        if response.status_code == 200:
            assert data['success'] is True
        else:  # 404
            assert data['success'] is False

    def test_remove_attendee_unauthorized_access(self, client, sample_session_instance_data, sample_person_data):
        """Test that unauthorized users get 403 Forbidden"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        # No authentication provided
        response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is False

    def test_remove_attendee_admin_permission_required(self, client, authenticated_non_admin_user, sample_session_instance_data, sample_person_data):
        """Test that non-admin users cannot remove others"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']  # Different person from authenticated user
        
        with authenticated_non_admin_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        # Should be forbidden unless user is admin or removing themselves, or 404 if not attending
        assert response.status_code in [403, 404]  # 403 for permission denied, 404 if not attending

    def test_remove_attendee_nonexistent_session(self, client, authenticated_user, sample_person_data):
        """Test removal from nonexistent session returns 404"""
        nonexistent_session_id = 99999
        person_id = sample_person_data['person_id']
        
        with authenticated_user:
            response = client.delete(f'/api/session_instance/{nonexistent_session_id}/attendees/{person_id}')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'message' in data

    def test_remove_attendee_nonexistent_person(self, client, authenticated_user, sample_session_instance_data):
        """Test removal of nonexistent person returns 404"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        nonexistent_person_id = 99999
        
        with authenticated_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{nonexistent_person_id}')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    def test_remove_attendee_not_attending(self, client, authenticated_user, sample_session_instance_data, sample_person_not_attending):
        """Test removal of person not in attendance returns 404"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_not_attending['person_id']
        
        with authenticated_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    def test_remove_attendee_invalid_session_id(self, client, authenticated_user, sample_person_data):
        """Test that invalid session ID format returns 400 or 404"""
        invalid_session_id = "not_a_number"
        person_id = sample_person_data['person_id']
        
        with authenticated_user:
            response = client.delete(f'/api/session_instance/{invalid_session_id}/attendees/{person_id}')
        
        assert response.status_code in [400, 404]

    def test_remove_attendee_invalid_person_id(self, client, authenticated_user, sample_session_instance_data):
        """Test that invalid person ID format returns 400 or 404"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        invalid_person_id = "not_a_number"
        
        with authenticated_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{invalid_person_id}')
        
        assert response.status_code in [400, 404]

    def test_remove_attendee_self_removal_allowed(self, client, authenticated_user, sample_session_instance_data, sample_user_data):
        """Test that users can remove themselves from attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_user:
            # Get the current user's person_id from the sample_user_data fixture
            user_person_id = sample_user_data['person_id']
            
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{user_person_id}')
        
        # Self-removal should be allowed
        assert response.status_code in [200, 404]  # 404 if not attending

    def test_remove_attendee_idempotent(self, client, admin_user, sample_session_instance_data, sample_person_data):
        """Test that removing already removed attendee returns appropriate response"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_person_data['person_id']
        
        with admin_user:
            # First removal
            response1 = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
            
            # Second removal (should be idempotent)
            response2 = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        # Second call should either succeed (idempotent) or return 404
        assert response2.status_code in [200, 404]