# Test Suite Documentation

This directory contains all tests for the Irish Music Sessions Flask application.

## Quick Start

```bash
# Run all tests
pytest

# Run specific test types
make test-unit        # Unit tests only
make test-integration # Integration tests only
make test-functional  # Functional tests only
```

## Documentation

- [TEST_SETUP.md](TEST_SETUP.md) - Complete setup instructions for the test environment
- [TEST_EXAMPLES.md](TEST_EXAMPLES.md) - Examples and patterns for writing tests

## Test Structure

```
tests/
├── unit/           # Fast, isolated component tests
├── integration/    # Tests with database/external services
├── functional/     # End-to-end user journey tests
└── fixtures/       # Shared test data and utilities
```

## Current Test Status

✅ **151 tests passing** (100% success rate)
- 22 unit tests
- 67 integration tests  
- 62 functional tests

## Key Testing Patterns

1. **UUID-based unique test data** - Prevents database conflicts
2. **Comprehensive mocking** - For external services and database
3. **Journey-based functional tests** - Real user workflows
4. **Fixture reuse** - Shared setup in conftest.py