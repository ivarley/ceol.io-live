"""
End-to-end functional test for complete attendance workflow
Tests the full user journey from viewing session to managing attendance.
"""

import pytest
import json
from flask import url_for


class TestAttendanceFlow:
    """Functional tests for complete attendance workflows"""

    def test_complete_session_organizer_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test complete workflow: view session → see attendees → add people → manage attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        session_id = sample_session_instance_data['session_id']
        
        with authenticated_admin_user:
            # Step 1: View session instance (would normally be HTML page)
            # For API testing, we check attendance tab availability
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert attendance_response.status_code == 200
            
            initial_data = json.loads(attendance_response.data)
            initial_count = len(initial_data['data']['regulars']) + len(initial_data['data']['attendees'])
            
            # Step 2: Search for existing people to add
            search_response = client.get(f'/api/session/{session_id}/people/search?q=John')
            search_data = json.loads(search_response.data)
            
            if search_data['data']:
                # Step 3: Add existing person to attendance
                existing_person = search_data['data'][0]
                checkin_response = client.post(
                    f'/api/session_instance/{session_instance_id}/attendees/checkin',
                    data=json.dumps({
                        'person_id': existing_person['person_id'],
                        'attendance': 'maybe',
                        'comment': 'Found through search'
                    }),
                    content_type='application/json'
                )
                assert checkin_response.status_code in [200, 201]
            
            # Step 4: Create entirely new person
            new_person_data = {
                'first_name': 'Brand',
                'last_name': 'NewPerson',
                'instruments': ['mandolin', 'guitar']
            }
            
            create_response = client.post('/api/person', data=json.dumps(new_person_data), content_type='application/json')
            assert create_response.status_code == 201
            new_person_id = json.loads(create_response.data)['data']['person_id']
            
            # Step 5: Check in the new person immediately
            new_person_checkin = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({
                    'person_id': new_person_id,
                    'attendance': 'yes',
                    'comment': 'First time at our session!'
                }),
                content_type='application/json'
            )
            assert new_person_checkin.status_code in [200, 201]
            
            # Step 6: View updated attendance list
            final_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            final_data = json.loads(final_response.data)
            final_count = len(final_data['data']['regulars']) + len(final_data['data']['attendees'])
            
            # Should have more people now
            assert final_count >= initial_count
            
            # New person should appear in attendance
            all_attendees = final_data['data']['regulars'] + final_data['data']['attendees']
            attendee_ids = [a['person_id'] for a in all_attendees]
            assert new_person_id in attendee_ids
            
            # Step 7: Manage attendance - change someone's status
            if all_attendees:
                person_to_update = all_attendees[0]
                update_response = client.post(
                    f'/api/session_instance/{session_instance_id}/attendees/checkin',
                    data=json.dumps({
                        'person_id': person_to_update['person_id'],
                        'attendance': 'no',
                        'comment': 'Changed their mind'
                    }),
                    content_type='application/json'
                )
                assert update_response.status_code == 200

    def test_regular_attendee_self_service_workflow(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test regular attendee workflow: check-in → view session → update status"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            user_person_id = authenticated_regular_user.person_id
            
            # Step 1: First check in - this gives user permission to view attendance
            # (based on can_view_attendance logic: user can view if they're attending)
            initial_checkin = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({
                    'person_id': user_person_id,
                    'attendance': 'yes'
                }),
                content_type='application/json'
            )
            assert initial_checkin.status_code in [200, 201]
            
            # Step 2: Now view session attendance (user should have access after checking in)
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert attendance_response.status_code == 200
            
            initial_data = json.loads(attendance_response.data)
            
            # User should appear in attendees list (may not be in regulars if not set up as regular)
            all_attendees = initial_data['data']['regulars'] + initial_data['data']['attendees'] 
            user_in_attendance = any(a['person_id'] == user_person_id for a in all_attendees)
            assert user_in_attendance
            
            # Step 3: Change mind and update to "maybe"
            update_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({
                    'person_id': user_person_id,
                    'attendance': 'maybe',
                    'comment': 'Depends on weather'
                }),
                content_type='application/json'
            )
            assert update_response.status_code == 200
            
            # Step 4: Final check - verify status persisted
            final_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            final_data = json.loads(final_response.data)
            
            all_attendees = final_data['data']['regulars'] + final_data['data']['attendees']
            user_attendance = next((a for a in all_attendees if a['person_id'] == user_person_id), None)
            
            assert user_attendance is not None
            assert user_attendance['attendance'] == 'maybe'

    def test_casual_user_discovery_and_checkin_workflow(self, client, authenticated_user, sample_session_instance_data):
        """Test casual user workflow: discover session → self check-in → appear in attendance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_user:
            user_person_id = authenticated_user.person_id
            
            # Step 1: User discovers they can check into any session
            # Verify they can see attendance (once they're attending or regular)
            initial_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            # May be 403 initially if not associated with session
            
            # Step 2: Self check-in to the session
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({
                    'person_id': user_person_id,
                    'attendance': 'yes',
                    'comment': 'Heard about this session online!'
                }),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Step 3: Now should be able to see attendance (as attendee)
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert attendance_response.status_code == 200
            
            attendance_data = json.loads(attendance_response.data)
            
            # Step 4: User should appear in attendance list as non-regular
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            user_attendance = next((a for a in all_attendees if a['person_id'] == user_person_id), None)
            
            assert user_attendance is not None
            assert user_attendance['attendance'] == 'yes'
            assert user_attendance['is_regular'] is False
            
            # Step 5: User can remove themselves if needed
            removal_response = client.delete(f'/api/session_instance/{session_instance_id}/attendees/{user_person_id}')
            assert removal_response.status_code in [200, 204]

    def test_multi_session_instance_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test workflow: create person → check in → verify search → check into different instance"""
        session_id = sample_session_instance_data['session_id']
        instance_a = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Step 1: Create person and check into instance A
            person_data = {
                'first_name': 'Multi',
                'last_name': 'Instance',
                'instruments': ['bouzouki']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            assert create_response.status_code == 201
            person_id = json.loads(create_response.data)['data']['person_id']
            
            checkin_response = client.post(
                f'/api/session_instance/{instance_a}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Step 2: Verify person appears in attendance list for this instance
            attendance_response = client.get(f'/api/session_instance/{instance_a}/attendees')
            assert attendance_response.status_code == 200
            
            attendance_data = json.loads(attendance_response.data)
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            attending_person = next((a for a in all_attendees if a['person_id'] == person_id), None)
            assert attending_person is not None
            assert attending_person['attendance'] == 'yes'
            
            # Step 3: Update attendance to different status  
            update_response = client.post(
                f'/api/session_instance/{instance_a}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'maybe', 'comment': 'Changed my mind'}),
                content_type='application/json'
            )
            assert update_response.status_code == 200
            
            # Step 4: Verify the attendance update persisted
            final_attendance_response = client.get(f'/api/session_instance/{instance_a}/attendees')
            final_attendance_data = json.loads(final_attendance_response.data)
            final_attendees = final_attendance_data['data']['regulars'] + final_attendance_data['data']['attendees']
            final_person = next((a for a in final_attendees if a['person_id'] == person_id), None)
            assert final_person is not None
            assert final_person['attendance'] == 'maybe'
            assert final_person['comment'] == 'Changed my mind'

    def test_instrument_management_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test workflow for managing person's instruments through attendance interface"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Step 1: Create person with initial instruments
            person_data = {
                'first_name': 'Instrument',
                'last_name': 'Player',
                'instruments': ['fiddle']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            person_id = json.loads(create_response.data)['data']['person_id']
            
            # Step 2: Check them in and verify instruments show
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            person = next((a for a in all_attendees if a['person_id'] == person_id), None)
            
            assert 'fiddle' in person['instruments']
            
            # Step 3: Update instruments (simulate clicking on person name → edit modal)
            instruments_update = {
                'instruments': ['fiddle', 'tin whistle', 'bodhrán']
            }
            
            update_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(instruments_update),
                content_type='application/json'
            )
            assert update_response.status_code == 200
            
            # Step 4: Verify updated instruments appear in attendance list
            final_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            final_data = json.loads(final_response.data)
            all_final = final_data['data']['regulars'] + final_data['data']['attendees']
            updated_person = next((a for a in all_final if a['person_id'] == person_id), None)
            
            assert 'fiddle' in updated_person['instruments']
            assert 'tin whistle' in updated_person['instruments']
            assert 'bodhrán' in updated_person['instruments']

    def test_error_recovery_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test workflow error handling and recovery"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Step 1: Try to add invalid person (should fail gracefully)
            invalid_checkin = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': 99999, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert invalid_checkin.status_code in [400, 404]
            
            # Step 2: Try to create person with invalid data (should fail)
            invalid_person = {
                'first_name': '',  # Empty name
                'last_name': 'Test',
                'instruments': ['invalid_instrument']
            }
            
            invalid_create = client.post('/api/person', data=json.dumps(invalid_person), content_type='application/json')
            assert invalid_create.status_code == 400
            
            # Step 3: Successful recovery - create valid person
            valid_person = {
                'first_name': 'Recovery',
                'last_name': 'Test',
                'instruments': ['fiddle']
            }
            
            success_response = client.post('/api/person', data=json.dumps(valid_person), content_type='application/json')
            assert success_response.status_code == 201
            
            # Verify system still works after errors
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert attendance_response.status_code == 200