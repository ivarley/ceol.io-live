"""
Integration test for searching and adding existing attendees
Tests the complete flow of finding and adding people who have previously attended sessions.
"""

import pytest
import json


class TestSearchAddAttendee:
    """Integration tests for searching and adding existing attendees"""

    def test_search_finds_previous_session_attendees(self, client, authenticated_admin_user, session_with_previous_attendees):
        """Test that search returns people who have attended this session before"""
        session_id = session_with_previous_attendees['session_id']
        previous_attendee_name = session_with_previous_attendees['previous_attendees'][0]['first_name']
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={previous_attendee_name}')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Should find the previous attendee
            assert len(data['data']) > 0
            found_person = data['data'][0]
            assert previous_attendee_name.lower() in found_person['display_name'].lower()

    def test_search_prioritizes_regulars_over_non_regulars(self, client, authenticated_admin_user, session_with_mixed_attendees):
        """Test that search results show regular attendees before non-regulars"""
        session_id = session_with_mixed_attendees['session_id']
        search_term = "a"  # Broad search to get multiple results
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={search_term}')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            if len(data['data']) > 1:
                results = data['data']
                
                # Find indices of regulars and non-regulars
                regular_indices = [i for i, person in enumerate(results) if person['is_regular']]
                non_regular_indices = [i for i, person in enumerate(results) if not person['is_regular']]
                
                # Regulars should appear before non-regulars
                if regular_indices and non_regular_indices:
                    assert max(regular_indices) < min(non_regular_indices)

    def test_search_includes_instrument_information(self, client, authenticated_admin_user, session_with_instrumentalists):
        """Test that search results include instrument information for each person"""
        session_id = session_with_instrumentalists['session_id']
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q=fiddle')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            if data['data']:
                person = data['data'][0]
                assert 'instruments' in person
                assert isinstance(person['instruments'], list)
                # Should have found someone who plays fiddle
                assert 'fiddle' in person['instruments']

    def test_add_found_person_to_current_session_instance(self, client, authenticated_admin_user, sample_session_instance_data, existing_person_not_attending):
        """Test adding a person found through search to current session instance"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        session_id = sample_session_instance_data['session_id']
        person = existing_person_not_attending
        
        with authenticated_admin_user:
            # First, search to find the person
            response = client.get(f'/api/session/{session_id}/people/search?q={person["first_name"]}')
            search_data = json.loads(response.data)
            found_person = search_data['data'][0]
            
            # Then add them to the session instance
            checkin_data = {
                'person_id': found_person['person_id'],
                'attendance': 'yes'
            }
            
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            assert checkin_response.status_code in [200, 201]
            
            # Verify they now appear in attendance list
            attendance_response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            attendance_data = json.loads(attendance_response.data)
            
            all_attendees = attendance_data['data']['regulars'] + attendance_data['data']['attendees']
            attendee_ids = [a['person_id'] for a in all_attendees]
            
            assert found_person['person_id'] in attendee_ids

    def test_search_case_insensitive(self, client, authenticated_admin_user, session_with_attendees):
        """Test that search is case insensitive"""
        session_id = session_with_attendees['session_id']
        attendee_name = session_with_attendees['attendees'][0]['first_name']
        
        with authenticated_admin_user:
            # Test various case combinations
            test_cases = [
                attendee_name.lower(),
                attendee_name.upper(),
                attendee_name.title(),
                attendee_name[:3].lower() + attendee_name[3:].upper()
            ]
            
            results = []
            for test_case in test_cases:
                response = client.get(f'/api/session/{session_id}/people/search?q={test_case}')
                data = json.loads(response.data)
                results.append(len(data['data']))
            
            # All searches should return the same number of results
            assert all(r == results[0] for r in results)

    def test_search_partial_name_matching(self, client, authenticated_admin_user, session_with_attendees):
        """Test that search works with partial names"""
        session_id = session_with_attendees['session_id']
        full_name = session_with_attendees['attendees'][0]['first_name']
        
        with authenticated_admin_user:
            # Search with just first 2-3 characters
            partial_search = full_name[:3]
            response = client.get(f'/api/session/{session_id}/people/search?q={partial_search}')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should find matches
            if data['data']:
                found_names = [p['display_name'] for p in data['data']]
                # At least one result should contain the partial search term
                assert any(partial_search.lower() in name.lower() for name in found_names)

    def test_search_across_multiple_session_instances(self, client, authenticated_admin_user, session_with_multiple_instances):
        """Test that search finds people across all instances of a session"""
        session_id = session_with_multiple_instances['session_id']
        instances = session_with_multiple_instances['instances']
        
        # Person who attended instance 1 but not instance 2
        person_name = instances[0]['unique_attendees'][0]['first_name']
        
        with authenticated_admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={person_name}')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should find the person even though they only attended one instance
            assert len(data['data']) > 0
            found_names = [p['display_name'] for p in data['data']]
            assert any(person_name.lower() in name.lower() for name in found_names)

    def test_add_attendee_updates_search_results(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that adding someone to a session makes them appear in future searches"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        session_id = sample_session_instance_data['session_id']
        
        with authenticated_admin_user:
            # Create a new person
            person_data = {
                'first_name': 'NewSearch',
                'last_name': 'Person',
                'instruments': ['viola']
            }
            
            create_response = client.post('/api/person', data=json.dumps(person_data), content_type='application/json')
            new_person_id = json.loads(create_response.data)['data']['person_id']
            
            # Add them to the session
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': new_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # They should now appear in search results for this session
            search_response = client.get(f'/api/session/{session_id}/people/search?q=NewSearch')
            search_data = json.loads(search_response.data)
            
            found_person = next((p for p in search_data['data'] if p['person_id'] == new_person_id), None)
            assert found_person is not None

    def test_search_respects_session_boundaries(self, client, authenticated_admin_user, multiple_different_sessions):
        """Test that search only returns people associated with the specific session"""
        session_a = multiple_different_sessions['session_a']
        session_b = multiple_different_sessions['session_b']
        
        # Person only associated with session A
        person_a_only = session_a['unique_attendees'][0]
        
        with authenticated_admin_user:
            # Search in session A should find the person
            response_a = client.get(f'/api/session/{session_a["session_id"]}/people/search?q={person_a_only["first_name"]}')
            data_a = json.loads(response_a.data)
            person_ids_a = [p['person_id'] for p in data_a['data']]
            assert person_a_only['person_id'] in person_ids_a
            
            # Search in session B should NOT find the person
            response_b = client.get(f'/api/session/{session_b["session_id"]}/people/search?q={person_a_only["first_name"]}')
            data_b = json.loads(response_b.data)
            person_ids_b = [p['person_id'] for p in data_b['data']]
            assert person_a_only['person_id'] not in person_ids_b

    def test_search_returns_alphabetical_within_priority_groups(self, client, authenticated_admin_user, session_with_many_attendees):
        """Test that search results are alphabetical within regular and non-regular groups"""
        session_id = session_with_many_attendees['session_id']
        
        with authenticated_admin_user:
            # Broad search to get multiple results
            response = client.get(f'/api/session/{session_id}/people/search?q=a')
            data = json.loads(response.data)
            
            if len(data['data']) > 2:
                results = data['data']
                regulars = [p for p in results if p['is_regular']]
                non_regulars = [p for p in results if not p['is_regular']]
                
                # Within each group, should be alphabetical
                if len(regulars) > 1:
                    regular_names = [p['display_name'] for p in regulars]
                    assert regular_names == sorted(regular_names)
                
                if len(non_regulars) > 1:
                    non_regular_names = [p['display_name'] for p in non_regulars]
                    assert non_regular_names == sorted(non_regular_names)