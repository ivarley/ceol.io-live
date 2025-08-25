# Testing Setup Guide

This document provides comprehensive instructions for setting up and running the testing suite for the Irish Music Sessions Flask application.

## Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Virtual environment (recommended)

## Installation

### 1. Install Test Dependencies

```bash
# Install main dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r requirements-test.txt
```

### 2. Set Up Test Database

Create a separate test database to avoid interfering with development data:

```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE ceol_test;
CREATE USER test_user WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE ceol_test TO test_user;
```

### 3. Configure Test Environment

Create a `.env.test` file with test-specific configuration:

```env
# Test Environment Configuration
FLASK_ENV=testing
FLASK_SESSION_SECRET_KEY=test-secret-key-change-me
PGHOST=localhost
PGDATABASE=ceol_test
PGUSER=test_user
PGPASSWORD=test_password
PGPORT=5432
SENDGRID_API_KEY=test-sendgrid-key
MAIL_DEFAULT_SENDER=test@ceol.io
```

### 4. Initialize Test Database Schema

```bash
# Run schema creation scripts against test database
psql -h localhost -U test_user -d ceol_test -f schema/create_session_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_person_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_user_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_tune_tables.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_session_tune_alias_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_session_instance_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_session_instance_tune_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_session_person_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_user_session_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_history_tables.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_login_history_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_session_instance_person_table.sql
psql -h localhost -U test_user -d ceol_test -f schema/create_audit_views.sql
```

## Running Tests

### Run All Tests

```bash
# Run complete test suite
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -m unit

# Integration tests only
pytest tests/integration/ -m integration

# Functional/smoke tests only
pytest tests/functional/ -m functional

# Skip slow tests
pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Test authentication flows
pytest tests/integration/test_auth_flow.py

# Test API endpoints
pytest tests/integration/test_api_endpoints.py

# Test database operations
pytest tests/integration/test_database.py

# Test user journeys
pytest tests/functional/test_user_journeys.py

# Test smoke tests
pytest tests/functional/test_smoke.py
```

### Run Specific Test Functions

```bash
# Test specific authentication function
pytest tests/unit/test_models.py::TestUser::test_user_initialization

# Test login workflow
pytest tests/integration/test_auth_flow.py::TestLoginFlow::test_successful_login_flow
```

## Test Configuration

### Pytest Configuration

The `pytest.ini` file contains standard configuration:

- Test discovery patterns
- Coverage settings
- Markers for test categorization
- Warning filters

### Fixtures and Test Data

Tests use several fixtures defined in `conftest.py`:

- `client`: Flask test client
- `db_conn` / `db_cursor`: Database connections
- `authenticated_user` / `admin_user`: User sessions
- `sample_*_data`: Test data generators

### Mock Services

Tests mock external services:

- **SendGrid**: Email sending service
- **thesession.org API**: Tune and session data
- **Database connections**: For unit tests

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── unit/                      # Unit tests
│   ├── test_models.py         # Model and business logic tests
│   ├── test_routes.py         # Route handler tests
│   └── test_utils.py          # Utility function tests
├── integration/               # Integration tests
│   ├── test_auth_flow.py      # Authentication workflows
│   ├── test_api_endpoints.py  # API endpoint tests
│   └── test_database.py       # Database operation tests
├── functional/                # Functional tests
│   ├── test_smoke.py          # Critical path smoke tests
│   └── test_user_journeys.py  # End-to-end user workflows
└── fixtures/                  # Test data and mocks
    ├── sample_data.py         # Generated test data
    └── mock_responses.py      # External service mocks
```

## Test Categories

### Unit Tests (`-m unit`)
- Test individual functions and classes
- No external dependencies
- Fast execution
- High coverage of business logic

### Integration Tests (`-m integration`)
- Test component interactions
- Real database connections
- API endpoint testing
- Authentication workflows

### Functional Tests (`-m functional`)
- End-to-end user scenarios
- Complete workflows
- Cross-component testing
- Browser-like interactions

### Slow Tests (`-m slow`)
- Performance baseline tests
- Large data set tests
- Complex workflows
- Use `pytest -m "not slow"` to skip

## Coverage Reports

### Generate Coverage

```bash
# HTML coverage report
pytest --cov=. --cov-report=html

# Terminal coverage report
pytest --cov=. --cov-report=term-missing

# Coverage with minimum threshold
pytest --cov=. --cov-fail-under=80
```

### View Coverage

```bash
# Open HTML coverage report
open htmlcov/index.html
```

## Continuous Integration

### GitHub Actions

The test suite is designed for CI/CD integration. Example workflow:

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: ceol_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: pytest --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## Debugging Tests

### Run Tests in Debug Mode

```bash
# Run with Python debugger
pytest --pdb

# Run specific test with debugger
pytest tests/unit/test_models.py::TestUser::test_user_initialization --pdb

# Show local variables on failure
pytest -l
```

### Verbose Output

```bash
# Maximum verbosity
pytest -vvv

# Show captured output
pytest -s

# Show test duration
pytest --durations=10
```

## Common Issues and Solutions

### Database Connection Issues

**Issue**: Tests fail with database connection errors

**Solution**:
1. Ensure PostgreSQL is running
2. Verify test database exists and credentials are correct
3. Check `.env.test` configuration
4. Ensure test user has proper permissions

### Import Errors

**Issue**: `ModuleNotFoundError` when running tests

**Solution**:
1. Ensure you're in the project root directory
2. Check that `PYTHONPATH` includes the project root
3. Verify all dependencies are installed

### Mock Issues

**Issue**: External service calls aren't mocked properly

**Solution**:
1. Check mock decorators are applied correctly
2. Verify mock return values match expected format
3. Ensure mocks are reset between tests

### Slow Tests

**Issue**: Tests run too slowly

**Solution**:
1. Use `pytest -m "not slow"` to skip slow tests during development
2. Run slow tests separately in CI
3. Consider mocking database operations in unit tests

## Best Practices

### Writing New Tests

1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Use Descriptive Names**: Test names should describe behavior
3. **Keep Tests Independent**: Each test should be self-contained
4. **Use Appropriate Test Type**: Unit for logic, integration for workflows
5. **Mock External Dependencies**: Don't rely on external services

### Test Data

1. **Use Fixtures**: Reuse test data through fixtures
2. **Generate Realistic Data**: Use factories for realistic test scenarios
3. **Test Edge Cases**: Include boundary values and error conditions
4. **Clean Up**: Ensure tests don't leave artifacts

### Maintaining Tests

1. **Keep Tests Updated**: Update tests when code changes
2. **Review Coverage**: Maintain good test coverage
3. **Run Tests Frequently**: Run tests before committing
4. **Document Complex Tests**: Add comments for complex test scenarios

## Performance Guidelines

### Test Performance Targets

- **Unit tests**: < 1 second per test
- **Integration tests**: < 5 seconds per test
- **Functional tests**: < 30 seconds per test
- **Full suite**: < 10 minutes

### Optimization Tips

1. **Use transactions**: Wrap database tests in transactions
2. **Mock external calls**: Don't make real HTTP requests
3. **Parallel execution**: Use `pytest-xdist` for parallel runs
4. **Database fixtures**: Reuse database setup across tests

## Reporting Issues

If you encounter issues with the test suite:

1. Check this documentation for common solutions
2. Verify your environment setup matches requirements
3. Run individual test files to isolate problems
4. Check the project's issue tracker for known problems
5. Provide full error messages and environment details when reporting

## Extending the Test Suite

### Adding New Tests

1. Choose appropriate test directory (`unit/`, `integration/`, `functional/`)
2. Follow existing naming conventions
3. Add appropriate markers (`@pytest.mark.unit`, etc.)
4. Include proper documentation and comments
5. Update this documentation if adding new categories

### Adding New Fixtures

1. Add to `conftest.py` for global fixtures
2. Add to test files for test-specific fixtures
3. Use appropriate scope (`function`, `class`, `module`, `session`)
4. Document fixture purpose and usage

For additional help, refer to the [pytest documentation](https://docs.pytest.org/) and the project's existing test examples.