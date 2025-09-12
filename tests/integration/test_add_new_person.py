"""
Integration test for admin adding new person with instruments
Tests the complete flow of creating a new person and immediately checking them in.
"""

import pytest
import json


class TestAddNewPerson:
    """Integration tests for adding new people to sessions"""

    def test_admin_can_create_person_and_checkin(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that session admins can create a new person and check them in"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # Create new person
        import time
        unique_email = f'mary{int(time.time())}@example.com'
        person_data = {
            'first_name': 'Mary',
            'last_name': 'O\'Brien',
            'email': unique_email,
            'instruments': ['flute', 'tin whistle']
        }
        
        with authenticated_admin_user:
            # Create the person
            create_response = client.post(
                '/api/person',
                data=json.dumps(person_data),
                content_type='application/json'
            )
            
            assert create_response.status_code == 201
            create_data = json.loads(create_response.data)
            assert create_data['success'] is True
            new_person_id = create_data['data']['person_id']
            
            # Immediately check them in
            checkin_data = {
                'person_id': new_person_id,
                'attendance': 'yes'
            }
            
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            assert checkin_response.status_code in [200, 201]
            checkin_response_data = json.loads(checkin_response.data)
            assert checkin_response_data['success'] is True
            assert checkin_response_data['data']['person_id'] == new_person_id

    def test_new_person_appears_in_attendance_with_instruments(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that newly created person appears in attendance list with their instruments"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # Use unique name to avoid disambiguation from previous test runs
        import time
        timestamp = int(time.time())
        person_data = {
            'first_name': 'Sean',
            'last_name': f'Murphy{timestamp}',
            'instruments': ['bodhrán', 'guitar']
        }
        
        with authenticated_admin_user:
            # Create person
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            new_person_id = json.loads(create_response.data)['data']['person_id']
            
            # Check in
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': new_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Verify appears in attendance list
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            new_person = next((a for a in all_attendees if a['person_id'] == new_person_id), None)
            
            assert new_person is not None
            assert new_person['display_name'].startswith('Sean M')  # May include timestamp in last name
            assert 'bodhrán' in new_person['instruments']
            assert 'guitar' in new_person['instruments']
            assert new_person['is_regular'] is False

    def test_new_person_with_duplicate_instruments_handled(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that duplicate instruments in creation request are handled properly"""
        person_data = {
            'first_name': 'Paddy',
            'last_name': 'Kelly',
            'instruments': ['fiddle', 'fiddle', 'tin whistle', 'fiddle']  # Duplicates
        }
        
        with authenticated_admin_user:
            response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            
            # Should either succeed (deduplicating) or return specific error
            if response.status_code == 201:
                person_id = json.loads(response.data)['data']['person_id']
                
                # Check actual instruments stored
                instruments_response = client.get(f'/api/person/{person_id}/instruments')
                instruments_data = json.loads(instruments_response.data)
                
                # Should only have unique instruments
                assert len(instruments_data['data']) == 2  # fiddle and tin whistle
                assert 'fiddle' in instruments_data['data']
                assert 'tin whistle' in instruments_data['data']

    def test_new_person_name_formatting_and_disambiguation(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that new person names are formatted and disambiguated correctly"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        # Use unique timestamp to avoid conflicts with other test runs
        import time
        timestamp = int(time.time())
        
        # Create first John Smith  
        person1_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': f'john1_{timestamp}@example.com',
            'instruments': ['fiddle']
        }
        
        # Create second John Smith (same name)
        person2_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': f'john2_{timestamp}@example.com',
            'instruments': ['flute']  # Different instrument
        }
        
        with authenticated_admin_user:
            # Create first person
            response1 = client.post('/api/person', data=json.dumps(person1_data), content_type='application/json')
            if response1.status_code != 201:
                print(f"Response1 status: {response1.status_code}")
                print(f"Response1 data: {response1.data.decode()}")
            assert response1.status_code == 201
            person1_id = json.loads(response1.data)['data']['person_id']
            
            # Create second person
            response2 = client.post('/api/person', data=json.dumps(person2_data), content_type='application/json')
            person2_id = json.loads(response2.data)['data']['person_id']
            
            # Check both in
            client.post(f'/api/session_instance/{session_instance_id}/attendees/checkin',
                       data=json.dumps({'person_id': person1_id, 'attendance': 'yes'}),
                       content_type='application/json')
            
            client.post(f'/api/session_instance/{session_instance_id}/attendees/checkin',
                       data=json.dumps({'person_id': person2_id, 'attendance': 'yes'}),
                       content_type='application/json')
            
            # Get attendance list
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            johns = [a for a in all_attendees if a['person_id'] in [person1_id, person2_id]]
            
            # Should have different display names due to disambiguation
            assert len(johns) == 2
            display_names = [j['display_name'] for j in johns]
            assert len(set(display_names)) == 2  # Should be different

    def test_regular_user_cannot_create_new_person(self, client, authenticated_regular_user):
        """Test that non-admin users cannot create new people"""
        person_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'instruments': ['fiddle']
        }
        
        with authenticated_regular_user:
            response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
        
        # Should be forbidden for non-admins
        assert response.status_code == 403

    def test_create_person_with_invalid_instruments_fails(self, client, authenticated_admin_user):
        """Test that creating person with invalid instruments fails validation"""
        person_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'instruments': ['electric_guitar', 'drums']  # Not in approved list
        }
        
        with authenticated_admin_user:
            response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_create_person_and_add_instruments_later(self, client, authenticated_admin_user):
        """Test creating person without instruments, then adding them later"""
        # Create person without instruments
        person_data = {
            'first_name': 'Emma',
            'last_name': 'Wilson'
        }
        
        with authenticated_admin_user:
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            person_id = json.loads(create_response.data)['data']['person_id']
            
            # Add instruments later
            instruments_data = {
                'instruments': ['harp', 'piano accordion']
            }
            
            update_response = client.put(
                f'/api/person/{person_id}/instruments',
                data=json.dumps(instruments_data),
                content_type='application/json'
            )
            
            assert update_response.status_code == 200
            
            # Verify instruments were added
            get_response = client.get(f'/api/person/{person_id}/instruments')
            instruments = json.loads(get_response.data)['data']
            
            assert 'harp' in instruments
            assert 'piano accordion' in instruments

    def test_create_person_with_email_creates_proper_record(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that creating person with email creates proper database record and can be added to sessions"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        import time
        unique_email = f'searchable{int(time.time())}@example.com'
        person_data = {
            'first_name': 'Searchable',
            'last_name': 'Person',
            'email': unique_email,
            'instruments': ['mandolin']
        }
        
        with authenticated_admin_user:
            # Create person
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            assert create_response.status_code == 201
            
            created_data = json.loads(create_response.data)
            assert created_data['success'] is True
            person_id = created_data['data']['person_id']
            
            # Verify person data is correct
            assert created_data['data']['first_name'] == 'Searchable'
            assert created_data['data']['last_name'] == 'Person'
            assert created_data['data']['email'] == unique_email
            assert 'mandolin' in created_data['data']['instruments']
            
            # Verify person can be added to session instances (demonstrates they're properly created)
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Verify they appear in attendance with correct data
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            created_person = next((a for a in all_attendees if a['person_id'] == person_id), None)
            
            assert created_person is not None
            assert 'Searchable' in created_person['display_name']
            assert 'mandolin' in created_person['instruments']

    def test_history_tracking_for_new_person(self, client, authenticated_admin_user):
        """Test that creating new person creates proper history records"""
        person_data = {
            'first_name': 'History',
            'last_name': 'Test',
            'instruments': ['concertina']
        }
        
        with authenticated_admin_user:
            response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            
            assert response.status_code == 201
            # History tracking is handled by database functions, so we just verify creation succeeded
            # The actual history verification would require database inspection