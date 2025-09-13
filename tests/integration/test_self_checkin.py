"""
Integration test for regular attendee self check-in
Tests the complete self-checkin flow for regular attendees.
"""

import pytest
import json


class TestSelfCheckin:
    """Integration tests for self check-in scenarios"""

    def test_regular_attendee_one_click_checkin(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regular attendees can check themselves in with one click"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            user_person_id = authenticated_regular_user.person_id
            
            # One-click check-in
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
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['attendance'] == 'yes'
        assert data['data']['is_regular'] is True

    def test_regular_attendee_appears_in_attendance_list(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regular attendees appear in the regulars list regardless of attendance status"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            # Check attendance list
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # User should appear in regulars list
            regulars = data['data']['regulars']
            user_person_id = authenticated_regular_user.person_id
            regular_person_ids = [r['person_id'] for r in regulars]
            
            assert user_person_id in regular_person_ids

    def test_regular_can_change_attendance_status(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regulars can change their attendance status multiple times"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_regular_user.person_id
        
        with authenticated_regular_user:
            # First: Check in as 'yes'
            response1 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert response1.status_code in [200, 201]
            
            # Then: Change to 'maybe'
            response2 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'maybe'}),
                content_type='application/json'
            )
            assert response2.status_code == 200
            
            data = json.loads(response2.data)
            assert data['data']['attendance'] == 'maybe'
            
            # Finally: Change to 'no'
            response3 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'no'}),
                content_type='application/json'
            )
            assert response3.status_code == 200
            
            data = json.loads(response3.data)
            assert data['data']['attendance'] == 'no'

    def test_regular_checkin_with_comment(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regulars can add comments when checking in"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_regular_user.person_id
        
        checkin_data = {
            'person_id': user_person_id,
            'attendance': 'yes',
            'comment': 'Bringing my new fiddle!'
        }
        
        with authenticated_regular_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 201]
        data = json.loads(response.data)
        assert data['success'] is True

    def test_non_regular_user_self_checkin(self, client, authenticated_user, sample_session_instance_data):
        """Test that non-regular users can still check themselves into any session"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_user:
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
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_regular'] is False  # Not a regular for this session

    def test_self_checkin_updates_attendance_list(self, client, authenticated_user, sample_session_instance_data):
        """Test that self check-in immediately updates the attendance list"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_user.person_id
        
        with authenticated_user:
            # Check initial state
            response1 = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            initial_data = json.loads(response1.data)
            
            # Self check-in
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Check updated state
            response2 = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            updated_data = json.loads(response2.data)
            
            # Should now appear in attendees list
            all_attendees = updated_data['data']['regulars'] + updated_data['data']['attendees']
            attendee_ids = [a['person_id'] for a in all_attendees]
            
            assert user_person_id in attendee_ids

    def test_regular_priority_in_display_order(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regulars appear first in attendance lists"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            # Check in as regular
            user_person_id = authenticated_regular_user.person_id
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Get attendance list
            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            data = json.loads(response.data)
            
            # Regulars should be in their own section
            regulars = data['data']['regulars']
            attendees = data['data']['attendees']
            
            # Find the user in regulars section
            regular_person_ids = [r['person_id'] for r in regulars]
            assert user_person_id in regular_person_ids

    def test_self_checkin_persistence_across_requests(self, client, authenticated_user, sample_session_instance_data):
        """Test that self check-in persists across multiple requests"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_user.person_id
        
        with authenticated_user:
            # Self check-in
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Multiple subsequent requests should show consistent state
            for _ in range(3):
                response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
                data = json.loads(response.data)
                
                all_attendees = data['data']['regulars'] + data['data']['attendees']
                user_attendee = next((a for a in all_attendees if a['person_id'] == user_person_id), None)
                
                assert user_attendee is not None
                assert user_attendee['attendance'] == 'yes'

    def test_self_checkin_cross_session_independence(self, client, authenticated_user, multiple_session_instances):
        """Test that check-in to one session doesn't affect others"""
        instances = multiple_session_instances['instances']
        session_a = instances[0]['session_instance_id']
        session_b = instances[1]['session_instance_id']
        user_person_id = authenticated_user.person_id
        
        with authenticated_user:
            # Check into session A only
            client.post(
                f'/api/session_instance/{session_a}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Session A should show attendance
            response_a = client.get(f'/api/session_instance/{session_a}/attendees')
            data_a = json.loads(response_a.data)
            all_a = data_a['data']['regulars'] + data_a['data']['attendees']
            ids_a = [a['person_id'] for a in all_a]
            assert user_person_id in ids_a
            
            # Session B should not show attendance
            response_b = client.get(f'/api/session_instance/{session_b}/attendees')
            if response_b.status_code != 200:
                print(f"Session B response status: {response_b.status_code}")
                print(f"Session B response: {response_b.data.decode()}")
            data_b = json.loads(response_b.data)
            all_b = data_b['data']['regulars'] + data_b['data']['attendees']
            attending_b = [a for a in all_b if a['person_id'] == user_person_id and a['attendance'] in ['yes', 'maybe']]
            assert len(attending_b) == 0