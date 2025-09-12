"""
End-to-end functional test for person management and instruments
Tests the complete lifecycle of person records and instrument management.
"""

import pytest
import json


class TestPersonManagement:
    """Functional tests for person and instrument management workflows"""

    def test_complete_person_lifecycle(self, client, authenticated_admin_user):
        """Test full person lifecycle: create → view → update instruments → delete"""
        with authenticated_admin_user:
            # Step 1: Create new person
            person_data = {
                'first_name': 'Lifecycle',
                'last_name': 'TestPerson',
                'email': 'lifecycle@example.com',
                'instruments': ['fiddle', 'tin whistle']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            assert create_response.status_code == 201
            
            person_id = json.loads(create_response.data)['data']['person_id']
            display_name = json.loads(create_response.data)['data']['display_name']
            
            assert 'Lifecycle' in display_name
            
            # Step 2: View person's instruments
            instruments_response = client.get(f'/api/person/{person_id}/instruments')
            assert instruments_response.status_code == 200
            
            instruments_data = json.loads(instruments_response.data)
            instruments = instruments_data['data']
            
            assert 'fiddle' in instruments
            assert 'tin whistle' in instruments
            assert len(instruments) == 2
            
            # Step 3: Update instruments (add more)
            updated_instruments = {
                'instruments': ['fiddle', 'tin whistle', 'bodhrán', 'guitar']
            }
            
            update_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(updated_instruments),
                content_type='application/json'
            )
            assert update_response.status_code == 200
            
            # Step 4: Verify instruments were updated
            verify_response = client.get(f'/api/person/{person_id}/instruments')
            verify_data = json.loads(verify_response.data)
            new_instruments = verify_data['data']
            
            assert len(new_instruments) == 4
            assert 'bodhrán' in new_instruments
            assert 'guitar' in new_instruments
            
            # Step 5: Reduce instruments (remove some)
            reduced_instruments = {
                'instruments': ['fiddle']
            }
            
            reduce_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(reduced_instruments),
                content_type='application/json'
            )
            assert reduce_response.status_code == 200
            
            # Step 6: Verify reduction
            final_response = client.get(f'/api/person/{person_id}/instruments')
            final_data = json.loads(final_response.data)
            final_instruments = final_data['data']
            
            assert len(final_instruments) == 1
            assert final_instruments[0] == 'fiddle'

    def test_person_with_attendance_history_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test person management when they have attendance history"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Step 1: Create person and get them attending sessions
            person_data = {
                'first_name': 'Attending',
                'last_name': 'Person',
                'instruments': ['concertina']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            person_id = json.loads(create_response.data)['data']['person_id']
            
            # Step 2: Add them to multiple session instances
            for attendance_status in ['yes', 'maybe', 'no']:
                checkin_response = client.post(
                    f'/api/session_instance/{session_instance_id}/attendees/checkin',
                    data=json.dumps({
                        'person_id': person_id,
                        'attendance': attendance_status,
                        'comment': f'Status: {attendance_status}'
                    }),
                    content_type='application/json'
                )
                # Each update should succeed
                assert checkin_response.status_code == 200
            
            # Step 3: Update their instruments while they have attendance history
            new_instruments = {
                'instruments': ['concertina', 'button accordion', 'piano accordion']
            }
            
            instruments_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(new_instruments),
                content_type='application/json'
            )
            assert instruments_response.status_code == 200
            
            # Step 4: Verify they still appear in attendance with updated instruments
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            person = next((a for a in all_attendees if a['person_id'] == person_id), None)
            
            assert person is not None
            assert person['attendance'] == 'no'  # Last status set
            assert 'concertina' in person['instruments']
            assert 'button accordion' in person['instruments']
            assert 'piano accordion' in person['instruments']

    def test_duplicate_person_handling_workflow(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test workflow when dealing with potential duplicate people"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_admin_user:
            # Step 1: Create first John Smith
            person1_data = {
                'first_name': 'John',
                'last_name': 'Smith',
                'instruments': ['fiddle']
            }
            
            create1_response = client.post('/api/person', data=json.dumps(person1_data), content_type='application/json')
            person1_id = json.loads(create1_response.data)['data']['person_id']
            
            # Step 2: Create second John Smith (potential duplicate)
            person2_data = {
                'first_name': 'John',
                'last_name': 'Smith',
                'instruments': ['flute']  # Different instrument
            }
            
            create2_response = client.post('/api/person', data=json.dumps(person2_data), content_type='application/json')
            person2_id = json.loads(create2_response.data)['data']['person_id']
            
            # Step 3: Add both to same session instance
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': person1_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': person2_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Step 4: Verify both appear with disambiguated names
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            johns = [a for a in all_attendees if a['person_id'] in [person1_id, person2_id]]
            
            assert len(johns) == 2
            
            # Should have different display names or clear instrument differentiation
            display_names = [j['display_name'] for j in johns]
            instruments = [j['instruments'] for j in johns]
            
            # Either names are different, or instruments clearly differentiate them
            assert len(set(display_names)) == 2 or (
                ['fiddle'] in instruments and ['flute'] in instruments
            )

    def test_instrument_validation_workflow(self, client, authenticated_admin_user):
        """Test complete workflow of instrument validation and correction"""
        with authenticated_admin_user:
            # Step 1: Try to create person with invalid instruments
            invalid_person_data = {
                'first_name': 'Invalid',
                'last_name': 'Instruments',
                'instruments': ['electric_guitar', 'drums', 'saxophone']  # All invalid
            }
            
            invalid_response = client.post('/api/person', data=json.dumps(invalid_person_data), content_type='application/json')
            assert invalid_response.status_code == 400
            
            # Step 2: Create person with mixed valid/invalid instruments
            mixed_person_data = {
                'first_name': 'Mixed',
                'last_name': 'Instruments',
                'instruments': ['fiddle', 'electric_guitar', 'tin whistle']  # 2 valid, 1 invalid
            }
            
            mixed_response = client.post('/api/person', data=json.dumps(mixed_person_data), content_type='application/json')
            assert mixed_response.status_code == 400  # Should reject due to invalid instrument
            
            # Step 3: Create person with all valid instruments
            valid_person_data = {
                'first_name': 'Valid',
                'last_name': 'Instruments',
                'instruments': ['fiddle', 'tin whistle', 'bodhrán']
            }
            
            valid_response = client.post('/api/person', data=json.dumps(valid_person_data), content_type='application/json')
            assert valid_response.status_code == 201
            person_id = json.loads(valid_response.data)['data']['person_id']
            
            # Step 4: Try to update with invalid instruments
            invalid_update = {
                'instruments': ['fiddle', 'electric_guitar']  # Mix of valid and invalid
            }
            
            invalid_update_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(invalid_update),
                content_type='application/json'
            )
            assert invalid_update_response.status_code == 400
            
            # Step 5: Verify original instruments unchanged after failed update
            check_response = client.get(f'/api/person/{person_id}/instruments')
            check_data = json.loads(check_response.data)
            
            assert 'fiddle' in check_data['data']
            assert 'tin whistle' in check_data['data']
            assert 'bodhrán' in check_data['data']
            assert 'electric_guitar' not in check_data['data']

    def test_person_search_and_discovery_workflow(self, client, authenticated_admin_user, sample_session_data):
        """Test workflow of creating people and having them be discoverable through search"""
        session_id = sample_session_data['session_id']
        
        with authenticated_admin_user:
            # Step 1: Create several people with searchable attributes
            people_data = [
                {
                    'first_name': 'Searchable',
                    'last_name': 'Fiddler',
                    'instruments': ['fiddle']
                },
                {
                    'first_name': 'Another',
                    'last_name': 'Fiddler', 
                    'instruments': ['fiddle', 'tin whistle']
                },
                {
                    'first_name': 'Unique',
                    'last_name': 'Flutist',
                    'instruments': ['flute']
                }
            ]
            
            created_people = []
            for person_data in people_data:
                response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
                assert response.status_code == 201
                person_id = json.loads(response.data)['data']['person_id']
                created_people.append((person_id, person_data))
            
            # Step 2: Add at least one person to the session to enable search
            sample_person_id = created_people[0][0]
            sample_session_instance = sample_session_data.get('sample_instance_id')
            if sample_session_instance:
                client.post(
                    f'/api/session_instance/{sample_session_instance}/attendees/checkin',
                    data=json.dumps({'person_id': sample_person_id, 'attendance': 'yes'}),
                    content_type='application/json'
                )
            
            # Step 3: Test various search scenarios
            # Search by first name
            search_response = client.get(f'/api/session/{session_id}/people/search?q=Searchable')
            search_data = json.loads(search_response.data)
            found_names = [p['display_name'] for p in search_data['data']]
            assert any('Searchable' in name for name in found_names)
            
            # Search by last name
            search_response = client.get(f'/api/session/{session_id}/people/search?q=Fiddler')
            search_data = json.loads(search_response.data)
            # Should find both fiddlers
            fiddler_count = len([p for p in search_data['data'] if 'Fiddler' in p['display_name']])
            assert fiddler_count >= 2
            
            # Search by partial name
            search_response = client.get(f'/api/session/{session_id}/people/search?q=Fid')
            search_data = json.loads(search_response.data)
            # Should find fiddlers
            assert len(search_data['data']) > 0

    def test_cross_session_person_management(self, client, authenticated_admin_user, multiple_sessions_data):
        """Test managing same person across different sessions"""
        session_a = multiple_sessions_data['session_a']
        session_b = multiple_sessions_data['session_b']
        
        with authenticated_admin_user:
            # Step 1: Create person
            person_data = {
                'first_name': 'CrossSession',
                'last_name': 'Player',
                'instruments': ['mandolin']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            person_id = json.loads(create_response.data)['data']['person_id']
            
            # Step 2: Add to session A
            instance_a = session_a['sample_instance_id']
            client.post(
                f'/api/session_instance/{instance_a}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Step 3: Update instruments (should affect all sessions)
            new_instruments = {
                'instruments': ['mandolin', 'bouzouki']
            }
            
            client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(new_instruments),
                content_type='application/json'
            )
            
            # Step 4: Add to session B
            instance_b = session_b['sample_instance_id']
            client.post(
                f'/api/session_instance/{instance_b}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'maybe'}),
                content_type='application/json'
            )
            
            # Step 5: Verify person appears correctly in both sessions with updated instruments
            # Check session A
            attendance_a = client.get(f'/api/session_instance/{instance_a}/attendees')
            data_a = json.loads(attendance_a.data)
            all_a = data_a['data']['regulars'] + data_a['data']['attendees']
            person_a = next((p for p in all_a if p['person_id'] == person_id), None)
            
            assert person_a is not None
            assert 'mandolin' in person_a['instruments']
            assert 'bouzouki' in person_a['instruments']
            assert person_a['attendance'] == 'yes'
            
            # Check session B
            attendance_b = client.get(f'/api/session_instance/{instance_b}/attendees')
            data_b = json.loads(attendance_b.data)
            all_b = data_b['data']['regulars'] + data_b['data']['attendees']
            person_b = next((p for p in all_b if p['person_id'] == person_id), None)
            
            assert person_b is not None
            assert 'mandolin' in person_b['instruments']
            assert 'bouzouki' in person_b['instruments']
            assert person_b['attendance'] == 'maybe'
            
            # Same instruments, different attendance per session
            assert person_a['instruments'] == person_b['instruments']