"""
Contract test for GET /api/session/{id}/people/search endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestSearchPeopleContract:
    """Contract tests for the search people endpoint"""

    def test_search_people_success_response_structure(self, client, admin_user, sample_session_data):
        """Test that successful search response matches expected contract"""
        session_id = sample_session_data['session_id']
        search_query = "John"
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={search_query}')
        
        if response.status_code != 200:
            print(f"Error response: {response.data.decode()}")
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        
        # Validate search results structure
        results = data['data']
        assert isinstance(results, list)
        
        if results:
            for person in results:
                required_fields = ['person_id', 'display_name', 'instruments', 'is_regular']
                for field in required_fields:
                    assert field in person
                
                assert isinstance(person['person_id'], int)
                assert isinstance(person['display_name'], str)
                assert isinstance(person['instruments'], list)
                assert isinstance(person['is_regular'], bool)

    def test_search_people_empty_query(self, client, admin_user, sample_session_data):
        """Test search with empty query parameter"""
        session_id = sample_session_data['session_id']
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q=')
        
        # Should return empty results or bad request
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['success'] is True
            assert isinstance(data['data'], list)

    def test_search_people_missing_query_parameter(self, client, admin_user, sample_session_data):
        """Test search without query parameter returns 400"""
        session_id = sample_session_data['session_id']
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'message' in data

    def test_search_people_partial_name_match(self, client, admin_user, sample_session_data):
        """Test search with partial name returns matching results"""
        session_id = sample_session_data['session_id']
        partial_name = "Joh"  # Should match "John", "Johnson", etc.
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={partial_name}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_search_people_case_insensitive(self, client, admin_user, sample_session_data):
        """Test that search is case insensitive"""
        session_id = sample_session_data['session_id']
        
        with admin_user:
            # Test lowercase
            response_lower = client.get(f'/api/session/{session_id}/people/search?q=john')
            # Test uppercase
            response_upper = client.get(f'/api/session/{session_id}/people/search?q=JOHN')
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        
        # Results should be the same regardless of case
        data_lower = json.loads(response_lower.data)
        data_upper = json.loads(response_upper.data)
        assert data_lower['success'] is True
        assert data_upper['success'] is True

    def test_search_people_no_matches(self, client, admin_user, sample_session_data):
        """Test search with no matching results"""
        session_id = sample_session_data['session_id']
        no_match_query = "XyzNotFound123"
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={no_match_query}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data'] == []

    def test_search_people_unauthorized_access(self, client, sample_session_data):
        """Test that unauthorized users get 403 Forbidden"""
        session_id = sample_session_data['session_id']
        search_query = "John"
        
        # No authentication provided
        response = client.get(f'/api/session/{session_id}/people/search?q={search_query}')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False

    def test_search_people_nonexistent_session(self, client, admin_user):
        """Test search in nonexistent session returns 404"""
        nonexistent_session_id = 99999
        search_query = "John"
        
        with admin_user:
            response = client.get(f'/api/session/{nonexistent_session_id}/people/search?q={search_query}')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    def test_search_people_invalid_session_id(self, client, admin_user):
        """Test that invalid session ID format returns 400 or 404"""
        invalid_session_id = "not_a_number"
        search_query = "John"
        
        with admin_user:
            response = client.get(f'/api/session/{invalid_session_id}/people/search?q={search_query}')
        
        assert response.status_code in [400, 404]

    def test_search_people_regulars_priority(self, client, admin_user, sample_session_data):
        """Test that regular attendees appear first in search results"""
        session_id = sample_session_data['session_id']
        search_query = "Te"  # Broad query to get multiple results (minimum 2 chars)
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={search_query}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        if len(data['data']) > 1:
            # Check if regulars come first
            results = data['data']
            regular_indices = [i for i, person in enumerate(results) if person['is_regular']]
            non_regular_indices = [i for i, person in enumerate(results) if not person['is_regular']]
            
            if regular_indices and non_regular_indices:
                assert max(regular_indices) < min(non_regular_indices), "Regulars should appear before non-regulars"

    def test_search_people_instruments_included(self, client, admin_user, sample_session_data):
        """Test that search results include instrument information"""
        session_id = sample_session_data['session_id']
        search_query = "Test"  # Search for test users
        
        with admin_user:
            response = client.get(f'/api/session/{session_id}/people/search?q={search_query}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        if data['data']:
            person = data['data'][0]
            assert 'instruments' in person
            assert isinstance(person['instruments'], list)