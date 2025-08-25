# Testing Examples and Usage Guide

This document provides practical examples of how to use the testing suite and write effective tests for the Irish Music Sessions application.

## Quick Start Examples

### Running Common Test Scenarios

```bash
# Run all tests
pytest

# Run only fast unit tests during development
pytest tests/unit/ -m "unit and not slow"

# Run integration tests for authentication
pytest tests/integration/test_auth_flow.py -v

# Run smoke tests before deployment
pytest tests/functional/test_smoke.py -v

# Generate coverage report
pytest --cov=. --cov-report=html
```

### Example Test Execution Output

```
$ pytest tests/unit/test_models.py -v

======================= test session starts ========================
collecting ... collected 15 items

tests/unit/test_models.py::TestUser::test_user_initialization PASSED [6%]
tests/unit/test_models.py::TestUser::test_user_get_id PASSED [13%]
tests/unit/test_models.py::TestUser::test_user_is_active_property PASSED [20%]
tests/unit/test_models.py::TestUser::test_get_by_id_success PASSED [26%]
tests/unit/test_models.py::TestUser::test_get_by_id_not_found PASSED [33%]
tests/unit/test_models.py::TestUser::test_check_password_valid PASSED [40%]
tests/unit/test_models.py::TestUser::test_check_password_invalid PASSED [46%]
...

======================= 15 passed in 2.34s =======================
```

## Unit Test Examples

### Testing Models

```python
def test_user_creation_with_all_fields(self):
    """Test creating a user with all optional fields."""
    user_data = {
        'user_id': 1,
        'person_id': 42,
        'username': 'testuser',
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john@example.com',
        'timezone': 'America/New_York',
        'is_system_admin': True,
        'email_verified': True,
        'auto_save_tunes': True
    }
    
    user = User(**user_data)
    
    assert user.first_name == 'John'
    assert user.is_system_admin is True
    assert user.auto_save_tunes is True
```

### Testing Route Handlers

```python
@patch('web_routes.get_db_connection')
def test_session_detail_page(self, mock_get_conn, client):
    """Test session detail page renders correctly."""
    # Arrange
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn
    
    # Mock database response
    mock_cursor.fetchone.return_value = (
        1, None, 'Test Session', 'test-session', 'Test Venue',
        'https://venue.com', '555-1234', '123 Main St',
        'Austin', 'TX', 'USA', 'Great session!', False,
        date(2023, 1, 1), None, 'weekly'
    )
    mock_cursor.fetchall.return_value = [
        (date(2023, 8, 15),), (date(2023, 8, 8),)
    ]
    
    # Act
    response = client.get('/sessions/test-session')
    
    # Assert
    assert response.status_code == 200
    assert b'Test Session' in response.data
    assert b'Test Venue' in response.data
```

### Testing Business Logic

```python
def test_normalize_apostrophes(self):
    """Test apostrophe normalization handles all variants."""
    test_cases = [
        ("O'Brien", "O'Brien"),  # Regular apostrophe unchanged
        ("O'Brien", "O'Brien"),  # Smart apostrophe normalized
        (""Hello"", "\"Hello\""),  # Smart quotes normalized
        ("Mixed 'quotes' and "apostrophes"", "Mixed 'quotes' and \"apostrophes\"")
    ]
    
    for input_text, expected in test_cases:
        result = normalize_apostrophes(input_text)
        assert result == expected, f"Failed for: {input_text}"
```

## Integration Test Examples

### Testing Database Operations

```python
def test_user_registration_database_integration(self, db_conn, db_cursor):
    """Test user registration creates proper database records."""
    # Arrange
    person_data = {
        'first_name': 'Integration',
        'last_name': 'Test',
        'email': 'integration@example.com'
    }
    
    # Act
    db_cursor.execute('''
        INSERT INTO person (first_name, last_name, email)
        VALUES (%s, %s, %s)
        RETURNING person_id
    ''', (person_data['first_name'], person_data['last_name'], person_data['email']))
    
    person_id = db_cursor.fetchone()[0]
    db_conn.commit()
    
    # Assert
    db_cursor.execute('SELECT * FROM person WHERE person_id = %s', (person_id,))
    person_record = db_cursor.fetchone()
    
    assert person_record is not None
    assert person_record[1] == 'Integration'  # first_name
    assert person_record[2] == 'Test'         # last_name
    assert person_record[3] == 'integration@example.com'  # email
```

### Testing API Workflows

```python
def test_add_tune_to_session_workflow(self, client, authenticated_user):
    """Test complete workflow of adding a tune to a session."""
    with patch('api_routes.get_db_connection') as mock_get_conn:
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock session and instance exist
        mock_cursor.fetchone.side_effect = [
            (1,),    # Session exists
            (123,),  # Session instance exists
        ]
        
        # Act
        response = client.post('/api/sessions/test-session/2023-08-15/add_tune',
                              json={
                                  'name': 'Test Reel',
                                  'continues_set': False
                              })
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify database calls
        assert mock_cursor.execute.call_count >= 2
```

## Functional Test Examples

### Testing User Journeys

```python
def test_new_user_complete_registration_journey(self, client):
    """Test complete new user journey from registration to email verification."""
    with patch('web_routes.send_verification_email') as mock_send_email:
        mock_send_email.return_value = True
        
        # Step 1: User accesses registration page
        response = client.get('/register')
        assert response.status_code == 200
        
        # Step 2: User submits registration form
        registration_data = {
            'username': 'journeytest',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'first_name': 'Journey',
            'last_name': 'Test',
            'email': 'journey@example.com'
        }
        
        response = client.post('/register', data=registration_data)
        assert response.status_code == 302  # Redirect to login
        
        # Step 3: Verify email was sent
        mock_send_email.assert_called_once()
        
        # Step 4: User clicks verification link (simulated)
        with patch('web_routes.get_db_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn
            
            # Mock successful verification
            mock_cursor.fetchone.return_value = (1, 'journeytest')
            
            response = client.get('/verify-email/test-token')
            assert response.status_code == 302  # Redirect to login
```

### Testing Error Scenarios

```python
def test_session_not_found_error_handling(self, client):
    """Test that non-existent session returns proper 404 page."""
    with patch('web_routes.get_db_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock session not found
        mock_cursor.fetchone.return_value = None
        
        response = client.get('/sessions/nonexistent-session')
        
        assert response.status_code == 404
        assert b'not found' in response.data.lower()
        # Should show friendly error page, not crash
```

## Testing with External Services

### Mocking thesession.org API

```python
@patch('api_routes.requests.get')
def test_refresh_tunebook_count_success(self, mock_requests, client, authenticated_user):
    """Test refreshing tunebook count from external API."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'tune': {
            'id': 1001,
            'name': 'The Butterfly',
            'tunebooks': 156
        }
    }
    mock_requests.return_value = mock_response
    
    with patch('api_routes.get_db_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Mock database lookups
        mock_cursor.fetchone.side_effect = [
            (1,),     # Session exists
            (1001,),  # Tune exists in session
        ]
        
        # Act
        response = client.post('/api/sessions/test-session/tunes/1001/refresh_tunebook_count')
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['tunebook_count'] == 156
        
        # Verify external API was called
        mock_requests.assert_called_once()
        assert 'tunes/1001' in mock_requests.call_args[0][0]
```

### Mocking Email Service

```python
@patch('email_utils.SendGridAPIClient')
def test_password_reset_email_success(self, mock_sg_client):
    """Test successful password reset email sending."""
    # Arrange
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_client.send.return_value = mock_response
    mock_sg_client.return_value = mock_client
    
    user = User(1, 42, 'testuser', email='test@example.com')
    token = 'reset-token-123'
    
    # Act
    with patch.dict(os.environ, {'SENDGRID_API_KEY': 'test-key'}):
        result = send_password_reset_email(user, token)
    
    # Assert
    assert result is True
    mock_client.send.assert_called_once()
    
    # Verify email content
    call_args = mock_client.send.call_args[0][0]  # Mail object
    assert 'reset-token-123' in str(call_args)
```

## Data-Driven Testing

### Using Parametrized Tests

```python
import pytest

class TestTuneTypeValidation:
    """Test tune type validation with multiple inputs."""
    
    @pytest.mark.parametrize("tune_type,expected", [
        ('reel', True),
        ('jig', True),
        ('slip jig', True),
        ('hornpipe', True),
        ('invalid_type', False),
        ('', False),
        (None, False)
    ])
    def test_tune_type_validation(self, tune_type, expected):
        """Test tune type validation with various inputs."""
        result = validate_tune_type(tune_type)
        assert result == expected
    
    @pytest.mark.parametrize("tune_data,should_pass", [
        ({'name': 'The Butterfly', 'tune_type': 'slip jig'}, True),
        ({'name': '', 'tune_type': 'reel'}, False),
        ({'name': 'Test Tune', 'tune_type': 'invalid'}, False),
        ({'name': 'X' * 300, 'tune_type': 'jig'}, False),  # Too long
    ])
    def test_tune_creation_validation(self, tune_data, should_pass):
        """Test tune creation with various data combinations."""
        if should_pass:
            result = create_tune(tune_data)
            assert result['success'] is True
        else:
            with pytest.raises(ValidationError):
                create_tune(tune_data)
```

### Using Test Fixtures with Parameters

```python
@pytest.fixture(params=[
    'America/New_York',
    'America/Chicago', 
    'America/Los_Angeles',
    'Europe/Dublin',
    'UTC'
])
def timezone_name(request):
    """Parametrized fixture for testing different timezones."""
    return request.param

def test_timezone_conversion(timezone_name):
    """Test timezone conversion with multiple timezones."""
    utc_time = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    local_time = utc_to_local(utc_time, timezone_name)
    
    assert local_time is not None
    assert isinstance(local_time, datetime)
    # Time should be different unless UTC
    if timezone_name != 'UTC':
        assert local_time.hour != utc_time.hour or local_time != utc_time
```

## Performance Testing Examples

### Testing Response Times

```python
import time

def test_home_page_response_time(client):
    """Test that home page loads within acceptable time."""
    start_time = time.time()
    response = client.get('/')
    end_time = time.time()
    
    response_time = end_time - start_time
    
    assert response.status_code == 200
    assert response_time < 2.0  # Should respond in under 2 seconds
```

### Testing with Large Data Sets

```python
@pytest.mark.slow
def test_session_with_many_tunes_performance(client, db_conn, db_cursor):
    """Test session instance with many tunes performs adequately."""
    # Create session with 100+ tunes
    session_id = create_test_session(db_cursor)
    instance_id = create_test_instance(db_cursor, session_id)
    
    # Add 150 tunes to test performance
    for i in range(150):
        add_test_tune(db_cursor, instance_id, i)
    
    db_conn.commit()
    
    start_time = time.time()
    response = client.get('/sessions/test-session/2023-08-15')
    end_time = time.time()
    
    assert response.status_code == 200
    assert end_time - start_time < 5.0  # Should load in under 5 seconds
```

## Security Testing Examples

### Testing Input Sanitization

```python
class TestSecurityValidation:
    """Test security-related input validation."""
    
    def test_sql_injection_prevention_in_session_lookup(self, client):
        """Test that SQL injection attempts are handled safely."""
        malicious_input = "test'; DROP TABLE session; --"
        
        response = client.get(f'/sessions/{malicious_input}')
        
        # Should return 404 or error, not crash the application
        assert response.status_code in [404, 500]
        # Should not execute malicious SQL
    
    def test_xss_prevention_in_form_inputs(self, client):
        """Test XSS prevention in form inputs."""
        xss_payload = '<script>alert("xss")</script>'
        
        response = client.post('/register', data={
            'username': xss_payload,
            'password': 'password123',
            'confirm_password': 'password123',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com'
        })
        
        # Should not execute script, should escape or reject
        assert b'<script>' not in response.data or b'&lt;script&gt;' in response.data
```

### Testing Authentication Edge Cases

```python
def test_session_hijacking_prevention(self, client):
    """Test that session tokens are properly validated."""
    # Create legitimate session
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['db_session_id'] = 'legitimate-session-123'
    
    # Try to access with manipulated session
    with client.session_transaction() as sess:
        sess['db_session_id'] = 'fake-session-456'
    
    response = client.get('/admin')  # Protected route
    
    # Should redirect to login or show access denied
    assert response.status_code in [302, 401, 403]
```

## Custom Test Utilities

### Creating Helper Functions

```python
# In tests/conftest.py or test files

def create_test_user(db_cursor, username="testuser", email="test@example.com"):
    """Helper function to create a test user."""
    # Create person first
    db_cursor.execute('''
        INSERT INTO person (first_name, last_name, email)
        VALUES (%s, %s, %s)
        RETURNING person_id
    ''', ('Test', 'User', email))
    person_id = db_cursor.fetchone()[0]
    
    # Create user account
    hashed_password = bcrypt.hashpw(b'testpass123', bcrypt.gensalt()).decode()
    db_cursor.execute('''
        INSERT INTO user_account (person_id, username, user_email, hashed_password, email_verified)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING user_id
    ''', (person_id, username, email, hashed_password, True))
    user_id = db_cursor.fetchone()[0]
    
    return {'user_id': user_id, 'person_id': person_id, 'username': username}

def assert_flash_message(response, message_type, message_text):
    """Helper to assert flash messages in responses."""
    # This would need to be implemented based on how flash messages
    # are rendered in your templates
    assert message_type.encode() in response.data
    assert message_text.encode() in response.data
```

### Using Custom Assertions

```python
def assert_valid_session_data(session_data):
    """Custom assertion for session data validation."""
    required_fields = ['session_id', 'name', 'path', 'city', 'state']
    for field in required_fields:
        assert field in session_data, f"Missing required field: {field}"
        assert session_data[field] is not None, f"Field {field} cannot be None"
    
    # Validate path format
    assert session_data['path'].replace('-', '').replace('_', '').isalnum(), \
           "Session path must be URL-safe"

def test_session_creation_with_custom_assertion(client, authenticated_user):
    """Test using custom assertion helper."""
    session_data = {
        'session_id': 1,
        'name': 'Test Session',
        'path': 'test-session',
        'city': 'Austin',
        'state': 'TX'
    }
    
    # Use custom assertion
    assert_valid_session_data(session_data)
```

## Debugging Test Failures

### Using pytest debugger

```bash
# Drop into debugger on test failure
pytest --pdb tests/unit/test_models.py::TestUser::test_user_creation

# Debug specific test
pytest -s tests/integration/test_auth_flow.py::TestLoginFlow::test_successful_login_flow --pdb
```

### Adding Debug Information

```python
def test_complex_workflow_with_debug_info(self, client, capsys):
    """Test with debug output for troubleshooting."""
    print("Starting complex workflow test")
    
    # Step 1
    response1 = client.get('/sessions')
    print(f"Step 1 response status: {response1.status_code}")
    
    # Step 2
    response2 = client.post('/api/sessions/test/add_tune', json={'name': 'Test Tune'})
    print(f"Step 2 response: {response2.data}")
    
    # Capture printed output
    captured = capsys.readouterr()
    print("Debug output:", captured.out)
    
    assert response2.status_code == 200
```

This examples guide provides practical patterns for writing and running tests effectively. Use these patterns as templates for your own test development.