"""
Integration test for searching and adding existing attendees
Tests basic API functionality for search and attendee management.
"""

import pytest
import json


class TestSearchAddAttendee:
    """Integration tests for searching and adding existing attendees"""

    def test_search_endpoint_exists_and_responds(self, client, authenticated_admin_user, sample_session_data):
        """Test that the search endpoint exists and returns proper structure"""
        session_id = sample_session_data['session_id']
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q=test')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'data' in data
            assert isinstance(data['data'], list)

    def test_search_requires_query_parameter(self, client, authenticated_admin_user, sample_session_data):
        """Test that search requires a query parameter"""
        session_id = sample_session_data['session_id']
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search')
            
            # Should require query parameter
            assert response.status_code in [400, 422]

    def test_search_requires_authentication(self, client, sample_session_data):
        """Test that search requires authentication"""
        session_id = sample_session_data['session_id']
        
        response = client.get(f'/api/session/{session_id}/people/search?q=test')
        
        # Should require authentication
        assert response.status_code == 401

    def test_search_validates_session_exists(self, client, authenticated_admin_user):
        """Test that search validates session exists"""
        nonexistent_session_id = 99999
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{nonexistent_session_id}/people/search?q=test')
            
            # Should return 404 for nonexistent session
            assert response.status_code == 404

    def test_add_attendee_through_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test the complete workflow of creating a person and adding them to attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Create a new person
            import time
            person_data = {
                'first_name': 'WorkflowTest',
                'last_name': f'Person{int(time.time())}',
                'instruments': ['flute']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            assert create_response.status_code == 201
            new_person_id = json.loads(create_response.data)['data']['person_id']
            
            # Add them to the session instance
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': new_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Verify they appear in attendance list
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            attendee_ids = [a['person_id'] for a in all_attendees]
            
            assert new_person_id in attendee_ids

    def test_create_and_immediately_add_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test creating a person and immediately adding them to a session"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Create person with unique name
            import time
            person_data = {
                'first_name': 'Immediate',
                'last_name': f'Add{int(time.time())}',
                'instruments': ['bodhrán']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            assert create_response.status_code == 201
            person_id = json.loads(create_response.data)['data']['person_id']
            
            # Immediately check them in
            checkin_data = {
                'person_id': person_id,
                'attendance': 'yes',
                'comment': 'Added immediately after creation'
            }
            
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            assert checkin_response.status_code in [200, 201]
            
            # Verify the person is in attendance with the correct comment
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            added_person = next((a for a in all_attendees if a['person_id'] == person_id), None)
            
            assert added_person is not None
            assert added_person['attendance'] == 'yes'
            assert added_person['comment'] == 'Added immediately after creation'

    def test_manage_multiple_people_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test adding multiple people to a session and managing their attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Create multiple people
            people_data = []
            import time
            timestamp = int(time.time())
            
            for i in range(3):
                person_data = {
                    'first_name': f'MultiPerson{i}',
                    'last_name': f'Test{timestamp}',
                    'instruments': ['tin whistle', 'mandolin'][i % 2:i % 2 + 1]
                }
                
                create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
                assert create_response.status_code == 201
                person_id = json.loads(create_response.data)['data']['person_id']
                people_data.append({'person_id': person_id, 'data': person_data})
            
            # Add all people to the session with different attendance statuses
            attendance_statuses = ['yes', 'maybe', 'yes']
            
            for i, person_info in enumerate(people_data):
                checkin_data = {
                    'person_id': person_info['person_id'],
                    'attendance': attendance_statuses[i]
                }
                
                checkin_response = client.post(
                    f'/api/session_instance/{session_instance_id}/attendees/checkin',
                    data=json.dumps(checkin_data),
                    content_type='application/json'
                )
                assert checkin_response.status_code in [200, 201]
            
            # Verify all people appear in attendance with correct statuses
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            
            for i, person_info in enumerate(people_data):
                attendee = next((a for a in all_attendees if a['person_id'] == person_info['person_id']), None)
                assert attendee is not None
                assert attendee['attendance'] == attendance_statuses[i]

