# Makefile for Irish Music Sessions Flask App Testing

.PHONY: help install test test-unit test-integration test-functional test-smoke test-coverage clean setup-test-db reset-test-db seed-test-db schema-test-db lint format

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies"
	@echo "  setup-test-db    Set up local test database (creates if not exists)"
	@echo "  reset-test-db    Drop and recreate test database from scratch"
	@echo "  seed-test-db     Refresh seed data only (keeps schema)"
	@echo "  schema-test-db   Run schema only (no seed data)"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-functional  Run functional tests only"
	@echo "  test-smoke       Run smoke tests only"
	@echo "  test-fast        Run fast tests (exclude slow)"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  test-watch       Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run code linting"
	@echo "  format           Format code"
	@echo "  clean            Clean up test artifacts"

# Installation
install:
	pip install -r requirements.txt
	pip install -r requirements-test.txt

# Database setup
setup-test-db:
	@./scripts/setup_local_db.sh

reset-test-db:
	@./scripts/setup_local_db.sh --reset

seed-test-db:
	@./scripts/setup_local_db.sh --seed-only

schema-test-db:
	@./scripts/setup_local_db.sh --schema-only

# Testing targets
test:
	pytest
	npm test

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-functional:
	pytest tests/functional/ -v -m functional

test-smoke:
	pytest tests/functional/test_smoke.py -v -m functional

test-fast:
	pytest -v -m "not slow"

test-coverage:
	pytest --cov=. --cov-report=html --cov-report=term-missing

test-coverage-xml:
	pytest --cov=. --cov-report=xml

test-watch:
	pytest-watch

test-parallel:
	pytest -n auto

# Code quality
lint:
	flake8 . --exclude=venv,env,htmlcov --ignore=E501,W503,F403,F405,E402,E712 --per-file-ignores="tests/*:F401,F841,scripts/*:F541"
	black . --check

format:
	black .

# Debugging
test-debug:
	pytest --pdb -s

test-verbose:
	pytest -vvv --tb=long

test-durations:
	pytest --durations=10

# Specific test patterns
test-auth:
	pytest tests/ -k "auth" -v

test-api:
	pytest tests/ -k "api" -v

test-routes:
	pytest tests/ -k "route" -v

test-database:
	pytest tests/ -k "database" -v

# CI targets
ci-test:
	pytest --cov=. --cov-report=xml --junitxml=test-results.xml

# Clean up
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf test-results.xml
	rm -rf coverage.xml
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete

# Development helpers
dev-setup: install setup-test-db
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything works"

# Production testing (for CI/CD)
prod-test: clean ci-test
	@echo "Production test run complete"

# Security testing
test-security:
	pytest tests/ -k "security" -v

# Performance testing
test-performance:
	pytest tests/ -m "slow" -v

# Test specific areas
test-models:
	pytest tests/unit/test_models.py -v

test-web-routes:
	pytest tests/unit/test_routes.py -v

test-auth-flow:
	pytest tests/integration/test_auth_flow.py -v

test-user-journeys:
	pytest tests/functional/test_user_journeys.py -v

# JavaScript/TypeScript testing targets
test-js:
	npm test

test-js-coverage:
	npm run test:coverage

test-js-watch:
	npm run test:watch