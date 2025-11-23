# Data Layer

Database schema, models, persistence, relationships.

## Overview

- **Database**: PostgreSQL on Render
- **Connection**: `database.py:get_db_connection()`
- **ORM**: None - direct psycopg2 queries
- **Schema**: `schema/*.sql` DDL files
- **Audit**: Comprehensive history tables

## Components

### [Core Schema](schema.md)
Complete table structure, indices, constraints

### [Session Model](session-model.md)
`session` (recurring) → `session_instance` (specific date) → `session_instance_tune` (log entries)

### [Tune Model](tune-model.md)
`tune` (metadata) ← `session_tune` (aliases/settings) ← `session_instance_tune` (usage)

### [People & Attendance](people-model.md)
`user_account` (login) / `person` (identity) / `session_person` (membership) / `session_instance_person` (attendance)

### [History & Audit](history.md)
`*_history` tables, trigger functions, audit trail queries

## Key Locations

- `schema/schema.md` - Human-readable schema documentation
- `schema/create_*.sql` - Table DDL
- `database.py:insert_*_history()` - Audit trail functions
- `schema/initial_*.sql` - Seed data
