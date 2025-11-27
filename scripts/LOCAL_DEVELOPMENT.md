# Local Development Setup

This guide explains how to set up a local development environment for ceol.io.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ installed locally
- Node.js 18+ (for the abc-renderer service)

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Set up the local database
make setup-test-db

# 3. Copy test environment to local
cp .env.test .env

# 4. Run the app
flask --app app run --debug
```

The app will be available at http://127.0.0.1:5001

## Database Setup

### First Time Setup

```bash
make setup-test-db
```

This will:
- Create the `ceol_test` database
- Create the `test_user` user with password `test_password`
- Load the complete schema from `schema/full_schema.sql`
- Load realistic seed data from `schema/seed_data.sql`

### Reset Database

To completely wipe and rebuild the database:

```bash
make reset-test-db
```

### Refresh Seed Data Only

To clear all data and reload seed data (without dropping tables):

```bash
make seed-test-db
```

### Load Schema Only (No Seed Data)

For testing with an empty database:

```bash
make schema-test-db
```

## Test Accounts

All test accounts use password: `password123`

| Username | Email | Role |
|----------|-------|------|
| `ian` | ian@ceol.io | System Admin |
| `sarah_fiddle` | sarah.oconnor@example.com | Regular User |
| `siobhan_flute` | siobhan.w@example.com | Regular User |
| `sean_banjo` | sobrien@example.com | Regular User |
| `maeve_accordion` | maeve.brennan@example.com | Regular User (unverified) |

## Database Connection

### Environment Variables

The local database uses these settings (from `.env.test`):

```
PGHOST=localhost
PGDATABASE=ceol_test
PGUSER=test_user
PGPASSWORD=test_password
PGPORT=5432
```

### Direct Connection

```bash
# Using psql
PGPASSWORD=test_password psql -h localhost -U test_user -d ceol_test

# Or with connection string
psql "postgresql://test_user:test_password@localhost:5432/ceol_test"
```

## Schema Files

| File | Description |
|------|-------------|
| `schema/full_schema.sql` | Complete schema for creating database from scratch |
| `schema/seed_data.sql` | Realistic test data (sessions, tunes, people, etc.) |
| `schema/schema.md` | Human-readable schema documentation |
| `schema/*.sql` | Individual migration files (for reference) |

## Seed Data Contents

The seed data includes:

- **50 tunes**: Popular Irish reels, jigs, hornpipes, slip jigs, polkas, slides
- **5 sessions**: Austin (2), Boston, Chicago, San Francisco
- **20 people**: Musicians with instruments
- **5 user accounts**: Admin and regular users
- **Session instances**: Past 3 months of sessions
- **Tune logs**: Example tune sets played at sessions
- **Attendance records**: Who attended which sessions

## Running Tests

```bash
# All tests
make test

# Just Python tests
pytest

# Just JavaScript tests
npm test

# With coverage
make test-coverage
```

## Common Tasks

### Sync Schema from Production

If you need to update your local schema to match production changes:

```bash
# Re-run full setup
make reset-test-db
```

### Backup/Restore Production Data

See [DATABASE_BACKUP.md](./DATABASE_BACKUP.md) for instructions on backing up and restoring production data.

### Manual Schema Changes

For quick schema testing, you can run SQL files directly:

```bash
PGPASSWORD=test_password psql -h localhost -U test_user -d ceol_test -f schema/your_migration.sql
```

## Troubleshooting

### PostgreSQL Not Running

```bash
# macOS (Homebrew)
brew services start postgresql@16

# Ubuntu/Debian
sudo systemctl start postgresql
```

### Permission Denied

If you get permission errors:

```bash
# Connect as postgres superuser and grant permissions
sudo -u postgres psql
postgres=# GRANT ALL PRIVILEGES ON DATABASE ceol_test TO test_user;
postgres=# ALTER DATABASE ceol_test OWNER TO test_user;
```

### Port Already in Use

If port 5432 is in use:

```bash
# Check what's using the port
lsof -i :5432

# Kill the process or use a different port
export PGPORT=5433
```

### Schema Out of Sync

If tables are missing columns or behaving unexpectedly:

```bash
# Nuclear option - completely rebuild
make reset-test-db
```
