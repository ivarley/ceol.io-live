"""
Contract test for POST /api/person endpoint
This test validates the API contract and must FAIL until the endpoint is implemented.
"""

import pytest
import json


class TestCreatePersonContract:
    """Contract tests for the create person endpoint"""

    def test_create_person_success_response_structure(self, client, authenticated_admin_user):
        """Test that successful person creation response matches expected contract"""
        import uuid
        person_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': f'john.smith.{uuid.uuid4()}@example.com',
            'instruments': ['fiddle', 'tin whistle']
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(person_data),
                content_type='application/json'
            )
        
        if response.status_code != 201:
            print(f"Error response: {response.data.decode()}")
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        
        # Validate person creation response structure
        person_info = data['data']
        assert 'person_id' in person_info
        assert 'display_name' in person_info
        assert isinstance(person_info['person_id'], int)
        assert isinstance(person_info['display_name'], str)
        assert person_info['person_id'] > 0

    def test_create_person_minimal_data(self, client, authenticated_admin_user):
        """Test person creation with only required fields"""
        minimal_data = {
            'first_name': 'Jane',
            'last_name': 'Doe'
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(minimal_data),
                content_type='application/json'
            )
        
        if response.status_code != 201:
            print(f"Error response: {response.data.decode()}")
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'person_id' in data['data']

    def test_create_person_with_instruments(self, client, authenticated_admin_user):
        """Test person creation with instruments"""
        person_data = {
            'first_name': 'Mary',
            'last_name': 'O\'Brien',
            'instruments': ['flute', 'piano accordion', 'bodhrán']
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(person_data),
                content_type='application/json'
            )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True

    def test_create_person_missing_required_fields(self, client, authenticated_admin_user):
        """Test that missing required fields return 400"""
        incomplete_data = {
            'first_name': 'John'
            # Missing last_name
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(incomplete_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'message' in data

    def test_create_person_invalid_instrument(self, client, authenticated_admin_user):
        """Test that invalid instrument names are rejected"""
        invalid_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'instruments': ['fiddle', 'electric_guitar']  # electric_guitar not in approved list
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(invalid_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_create_person_invalid_email_format(self, client, authenticated_admin_user):
        """Test that invalid email formats are rejected"""
        invalid_email_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'not_a_valid_email'
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(invalid_email_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_create_person_unauthorized_access(self, client):
        """Test that unauthorized users get 403 Forbidden"""
        person_data = {
            'first_name': 'John',
            'last_name': 'Smith'
        }
        
        # No authentication provided
        response = client.post(
            '/api/person',
            data=json.dumps(person_data),
            content_type='application/json'
        )
        
        assert response.status_code == 401

    def test_create_person_duplicate_instruments(self, client, authenticated_admin_user):
        """Test that duplicate instruments in the same request are handled properly"""
        duplicate_instruments_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'instruments': ['fiddle', 'fiddle', 'tin whistle']
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(duplicate_instruments_data),
                content_type='application/json'
            )
        
        # Should either succeed (deduplicating) or return 400
        assert response.status_code in [201, 400]

    def test_create_person_empty_names(self, client, authenticated_admin_user):
        """Test that empty or whitespace-only names are rejected"""
        empty_name_data = {
            'first_name': '   ',
            'last_name': 'Smith'
        }
        
        with authenticated_admin_user:
            response = client.post(
                '/api/person',
                data=json.dumps(empty_name_data),
                content_type='application/json'
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False