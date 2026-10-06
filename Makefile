# Makefile for Irish Music Sessions Flask App Testing

.PHONY: help install test test-unit test-integration test-functional test-smoke test-coverage clean setup-test-db reset-test-db seed-test-db schema-test-db lint format prod-parity

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies"
	@echo "  lab-install      Install the Ceol Listen lab's extra deps into venv (spec 053)"
	@echo "  setup-test-db    Set up local test database (creates if not exists)"
	@echo "  reset-test-db    Drop and recreate test database from scratch"
	@echo "  seed-test-db     Refresh seed data only (keeps schema)"
	@echo "  schema-test-db   Run schema only (no seed data)"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  lab-test         Run the lab's own tests (lab/pytest.ini, no coverage)"
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
	@echo ""
	@echo "iOS (ios/, spec 052):"
	@echo "  ios-test         CeolKit tests on the Mac, then the app's tests in the simulator"
	@echo "  ios-build        Build the app for the simulator"
	@echo "  ios-ui-test      Sign-in UI tests in the simulator, against a local server"
	@echo "  ios-fixtures     Re-capture the API responses CeolKit's decoding tests read"

# Installation
install:
	pip install -r requirements.txt
	pip install -r requirements-test.txt

# Ceol Listen lab (spec 053). Same venv on purpose: lab code imports recording.py
# and services/; deploy safety comes from Render installing only requirements.txt.
lab-install:
	venv/bin/pip install -r lab/requirements.txt

lab-test:
	cd lab && ../venv/bin/python -m pytest

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
	$(MAKE) test-frontend

# Live-logging Svelte bundle unit/component tests (Vitest, in frontend/).
test-frontend:
	cd frontend && npm test

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-functional:
	pytest tests/functional/ -v -m functional

test-smoke:
	pytest tests/functional/test_smoke.py -v -m functional

test-e2e:
	npx playwright test

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

tokens: ## Regenerate the design tokens (CSS + Swift) from design/tokens.json
	python3 scripts/build_tokens.py

tokens-check: ## Fail if the generated tokens have drifted from design/tokens.json
	python3 scripts/build_tokens.py --check

# --- iOS (spec 052) ----------------------------------------------------------
# The app lives in ios/Ceol; everything that is not a screen is the CeolKit package
# in ios/CeolKit, whose API client is generated from specs/api/native-surface.yaml.
IOS_SIM ?= platform=iOS Simulator,name=iPhone 17 Pro
IOS_DERIVED ?= ios/.derived

ios-test: ## iOS: CeolKit tests on the Mac (no simulator), then the app's tests in the simulator
	cd ios/CeolKit && swift test
	xcodebuild -project ios/Ceol/Ceol.xcodeproj -scheme Ceol -destination '$(IOS_SIM)' \
		-derivedDataPath $(IOS_DERIVED) -skipPackagePluginValidation -only-testing:CeolTests test

ios-build: ## iOS: build the app for the simulator
	xcodebuild -project ios/Ceol/Ceol.xcodeproj -scheme Ceol -destination 'generic/platform=iOS Simulator' \
		-derivedDataPath $(IOS_DERIVED) -skipPackagePluginValidation build

# Sign-in UI tests, driven through the app in the simulator. They need the app running
# on a LOCAL server first (./start, or flask on IOS_TEST_SERVER's port), and use the
# seeded accounts only: a password login, and a magic-link token minted straight into
# the local database, so nothing is emailed.
IOS_TEST_SERVER ?= http://127.0.0.1:5031

ios-ui-test: ## iOS: sign-in UI tests in the simulator, against a local server (IOS_TEST_SERVER)
	@case "$(IOS_TEST_SERVER)" in http://127.0.0.1:*|http://localhost:*) ;; *) echo "IOS_TEST_SERVER must be local"; exit 1;; esac
	TOKEN=$$(./venv/bin/python scripts/mint_login_token.py) && \
	DELETE_TOKEN=$$(./venv/bin/python scripts/mint_login_token.py ios-delete-$$$$@example.com --create) && \
	TEST_RUNNER_CEOL_TEST_SERVER=$(IOS_TEST_SERVER) TEST_RUNNER_CEOL_TEST_LOGIN_TOKEN=$$TOKEN \
	TEST_RUNNER_CEOL_TEST_DELETE_TOKEN=$$DELETE_TOKEN TEST_RUNNER_CEOL_TEST_DELETE_EMAIL=ios-delete-$$$$@example.com \
	xcodebuild -project ios/Ceol/Ceol.xcodeproj -scheme Ceol -destination '$(IOS_SIM)' \
		-derivedDataPath $(IOS_DERIVED) -skipPackagePluginValidation -only-testing:CeolUITests test

ios-fixtures: ## iOS: re-capture the real API responses CeolKit's decoding tests read (seeded local DB)
	./venv/bin/python scripts/capture_native_fixtures.py


# Spec 057: the server's and the templates' Irish catalog. extract -> update merges new
# strings into translations/ga/LC_MESSAGES/messages.po; compile writes the .mo the
# server reads. tests/unit/test_i18n_catalogs.py fails while any string lacks Irish.
I18N_IGNORE = --ignore-dirs='venv node_modules lab spike tests frontend static ios streaming listen abc-renderer e2e scripts .git .claude'
i18n-extract: ## i18n: extract the server's and templates' strings into translations/messages.pot
	./venv/bin/pybabel extract -F babel.cfg $(I18N_IGNORE) -k _l -k lazy_gettext -k js_ngettext:1,2 --sort-by-file --no-wrap -o translations/messages.pot .
	./venv/bin/pybabel update -i translations/messages.pot -d translations -l ga --no-wrap --no-fuzzy-matching --ignore-obsolete

i18n-compile: ## i18n: compile translations/ga/LC_MESSAGES/messages.po to the .mo the server reads
	./venv/bin/pybabel compile -d translations -l ga --statistics

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

prod-parity: ## Sample production (read-only, signed out); check the app decodes and orders it as the web does
	./venv/bin/python scripts/prod_parity/capture.py $(or $(SAMPLES),/tmp/ceol-prod)
	node scripts/prod_parity/web_summary.mjs $(or $(SAMPLES),/tmp/ceol-prod)
	cd ios/CeolKit && CEOL_PROD_SAMPLES=$(or $(SAMPLES),/tmp/ceol-prod) swift test --filter Production
