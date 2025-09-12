"""
Integration test for viewing session attendance with permissions
Tests the full permission model for attendance visibility and management.
"""

import pytest
import json
from flask import url_for


class TestAttendancePermissions:
    """Integration tests for attendance permission scenarios"""

    def test_public_user_cannot_see_attendance_tab(self, client, sample_session_instance_data):
        """Test that non-logged-in users cannot access attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # Try to access attendance without authentication
        response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data

    def test_logged_in_non_attendee_cannot_see_attendance(self, client, authenticated_user, session_instance_user_not_associated):
        """Test that logged-in users who aren't associated with session cannot see attendance"""
        session_instance_id = session_instance_user_not_associated['session_instance_id']
        
        with authenticated_user:
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False

    def test_session_regular_can_see_attendance(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regular attendees can view attendance for their sessions"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'regulars' in data['data']
        assert 'attendees' in data['data']

    def test_session_admin_can_see_and_manage_attendance(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that session admins can view and manage attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Can view attendance
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert response.status_code == 200
            
            # Can check in other people (admin privilege)
            checkin_data = {
                'person_id': sample_session_instance_data['other_person_id'],
                'attendance': 'yes'
            }
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            assert response.status_code in [200, 201]

    def test_current_attendee_can_see_attendance(self, client, authenticated_user, session_instance_with_user_attending):
        """Test that users currently attending a session can view attendance"""
        session_instance_id = session_instance_with_user_attending['session_instance_id']
        
        with authenticated_user:
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_regular_user_cannot_check_in_others(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that non-admin regulars cannot check in other people"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        other_person_id = sample_session_instance_data['other_person_id']
        
        checkin_data = {
            'person_id': other_person_id,  # Different from authenticated user
            'attendance': 'yes'
        }
        
        with authenticated_regular_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        # Should be forbidden unless it's self-checkin
        assert response.status_code in [403, 400]

    def test_user_can_check_in_themselves(self, client, authenticated_user, sample_session_instance_data):
        """Test that any logged-in user can check themselves into any session"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_user:
            # Get user's person_id (assuming this is available from fixture)
            user_person_id = authenticated_user.person_id
            
            checkin_data = {
                'person_id': user_person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 201]

    def test_regular_cannot_remove_others_attendance(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regular users cannot remove other people's attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        other_person_id = sample_session_instance_data['other_person_id']
        
        with authenticated_regular_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{other_person_id}')
        
        assert response.status_code == 403

    def test_admin_can_remove_any_attendance(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that session admins can remove anyone's attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = sample_session_instance_data['attendee_person_id']
        
        with authenticated_admin_user:
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{person_id}')
        
        assert response.status_code in [200, 404]  # 404 if not attending

    def test_user_can_remove_own_attendance(self, client, authenticated_user, sample_session_instance_data):
        """Test that users can remove their own attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_user:
            user_person_id = authenticated_user.person_id
            
            response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{user_person_id}')
        
        # Should be allowed (self-removal)
        assert response.status_code in [200, 404]  # 404 if not attending

    def test_permission_inheritance_from_session_to_instance(self, client, authenticated_regular_user, multiple_session_instances):
        """Test that session-level permissions apply to all instances of that session"""
        session_instances = multiple_session_instances['instances']
        
        with authenticated_regular_user:
            for instance in session_instances:
                response = client.get(f'/api/session_instance/{instance["session_instance_id"]}/attendees')
                # Should have same permission for all instances of the session
                assert response.status_code == 200

    def test_cross_session_permission_isolation(self, client, authenticated_regular_user, different_session_instance):
        """Test that permissions don't leak between different sessions"""
        # User is regular for session A but not session B
        other_session_instance_id = different_session_instance['session_instance_id']
        
        with authenticated_regular_user:
            response = client.get(f'/api/session_instance/{other_session_instance_id}/attendees')
        
        # Should not have access to different session
        assert response.status_code == 403