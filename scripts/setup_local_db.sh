#!/bin/bash
# =============================================================================
# Local Database Setup Script for ceol.io
# =============================================================================
# This script sets up or resets the local development database.
#
# Usage:
#   ./scripts/setup_local_db.sh         # Setup database (creates if not exists)
#   ./scripts/setup_local_db.sh --reset # Drop and recreate database
#   ./scripts/setup_local_db.sh --help  # Show help
#
# Requirements:
#   - PostgreSQL installed and running locally
#   - psql command available
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration (matches .env.test)
DB_NAME="ceol_test"
DB_USER="test_user"
DB_PASSWORD="test_password"
DB_HOST="localhost"
DB_PORT="5432"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Schema files
SCHEMA_FILE="$PROJECT_ROOT/schema/full_schema.sql"
SEED_FILE="$PROJECT_ROOT/schema/seed_data.sql"

# Parse arguments
RESET=false
SEED_ONLY=false
SCHEMA_ONLY=false

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Setup or reset the local development database."
    echo ""
    echo "Options:"
    echo "  --reset       Drop existing database and recreate from scratch"
    echo "  --seed-only   Only run seed data (assumes schema exists)"
    echo "  --schema-only Only run schema (no seed data)"
    echo "  --help        Show this help message"
    echo ""
    echo "Database configuration:"
    echo "  Database: $DB_NAME"
    echo "  User:     $DB_USER"
    echo "  Host:     $DB_HOST:$DB_PORT"
    echo ""
    echo "Examples:"
    echo "  $0              # Setup database if not exists, add seed data"
    echo "  $0 --reset      # Drop and recreate database with seed data"
    echo "  $0 --seed-only  # Just refresh the seed data"
}

for arg in "$@"; do
    case $arg in
        --reset)
            RESET=true
            shift
            ;;
        --seed-only)
            SEED_ONLY=true
            shift
            ;;
        --schema-only)
            SCHEMA_ONLY=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            show_help
            exit 1
            ;;
    esac
done

echo "============================================"
echo "ceol.io Local Database Setup"
echo "============================================"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: psql command not found${NC}"
    echo "Please install PostgreSQL:"
    echo "  macOS:   brew install postgresql@16"
    echo "  Ubuntu:  sudo apt install postgresql postgresql-contrib"
    exit 1
fi

# Check if PostgreSQL is running
echo "Checking PostgreSQL connection..."
if ! pg_isready -h $DB_HOST -p $DB_PORT &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not running${NC}"
    echo "Please start PostgreSQL:"
    echo "  macOS:   brew services start postgresql@16"
    echo "  Ubuntu:  sudo systemctl start postgresql"
    exit 1
fi
echo -e "${GREEN}PostgreSQL is running${NC}"

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}Error: Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi

# Check if seed file exists
if [ ! -f "$SEED_FILE" ]; then
    echo -e "${RED}Error: Seed file not found: $SEED_FILE${NC}"
    exit 1
fi

# Function to run SQL as postgres superuser
# Tries: postgres user, current user, then sudo (macOS Homebrew usually uses current user)
run_as_postgres() {
    psql -h $DB_HOST -p $DB_PORT -U postgres -c "$1" 2>/dev/null || \
    psql -h $DB_HOST -p $DB_PORT -U $(whoami) -c "$1" 2>/dev/null || \
    psql -h $DB_HOST -p $DB_PORT -c "$1" 2>/dev/null || \
    sudo -u postgres psql -c "$1" 2>/dev/null
}

# Function to check if database exists
db_exists() {
    psql -h $DB_HOST -p $DB_PORT -U postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw $DB_NAME || \
    psql -h $DB_HOST -p $DB_PORT -U $(whoami) -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw $DB_NAME || \
    psql -h $DB_HOST -p $DB_PORT -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw $DB_NAME || \
    sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw $DB_NAME
}

# Function to check if user exists
user_exists() {
    psql -h $DB_HOST -p $DB_PORT -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null | grep -q 1 || \
    psql -h $DB_HOST -p $DB_PORT -U $(whoami) -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null | grep -q 1 || \
    psql -h $DB_HOST -p $DB_PORT -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null | grep -q 1 || \
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null | grep -q 1
}

# Handle --seed-only
if [ "$SEED_ONLY" = true ]; then
    echo "Running seed data only..."

    if ! db_exists; then
        echo -e "${RED}Error: Database $DB_NAME does not exist. Run without --seed-only first.${NC}"
        exit 1
    fi

    echo "Clearing existing data..."
    # Truncate in reverse dependency order to avoid FK violations
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
        TRUNCATE TABLE
            login_history,
            user_session,
            session_instance_person,
            session_instance_tune,
            session_person,
            session_tune,
            session_tune_alias,
            person_instrument,
            person_tune,
            tune_setting,
            session_instance,
            user_account,
            person,
            tune,
            session
        RESTART IDENTITY CASCADE;
    " > /dev/null

    echo "Loading seed data..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$SEED_FILE" > /dev/null

    echo -e "${GREEN}Seed data loaded successfully!${NC}"
    exit 0
fi

# Handle --reset
if [ "$RESET" = true ]; then
    echo -e "${YELLOW}WARNING: This will DROP the database $DB_NAME${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    echo "Dropping database $DB_NAME..."
    run_as_postgres "DROP DATABASE IF EXISTS $DB_NAME;" || true
fi

# Create user if not exists
echo ""
echo "Setting up database user..."
if user_exists; then
    echo -e "${GREEN}User $DB_USER already exists${NC}"
else
    echo "Creating user $DB_USER..."
    run_as_postgres "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    echo -e "${GREEN}User $DB_USER created${NC}"
fi

# Create database if not exists
echo ""
echo "Setting up database..."
if db_exists; then
    if [ "$RESET" = false ]; then
        echo -e "${YELLOW}Database $DB_NAME already exists${NC}"
        echo "Use --reset to drop and recreate, or --seed-only to refresh data"
        exit 0
    fi
fi

echo "Creating database $DB_NAME..."
run_as_postgres "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
run_as_postgres "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
echo -e "${GREEN}Database $DB_NAME created${NC}"

# Run schema
echo ""
echo "Loading schema..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$SCHEMA_FILE" > /dev/null 2>&1
echo -e "${GREEN}Schema loaded successfully${NC}"

# Run seed data (unless --schema-only)
if [ "$SCHEMA_ONLY" = false ]; then
    echo ""
    echo "Loading seed data..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$SEED_FILE" > /dev/null 2>&1
    echo -e "${GREEN}Seed data loaded successfully${NC}"
fi

echo ""
echo "============================================"
echo -e "${GREEN}Database setup complete!${NC}"
echo "============================================"
echo ""
echo "Connection details:"
echo "  Host:     $DB_HOST"
echo "  Port:     $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "To use this database, set these environment variables:"
echo "  export PGHOST=$DB_HOST"
echo "  export PGDATABASE=$DB_NAME"
echo "  export PGUSER=$DB_USER"
echo "  export PGPASSWORD=$DB_PASSWORD"
echo ""
echo "Or copy .env.test to .env for local development:"
echo "  cp .env.test .env"
echo ""
echo "Test login credentials:"
echo "  Admin:    ian / password123"
echo "  Regular:  sarah_fiddle / password123"
