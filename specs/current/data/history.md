# History & Audit Trail

Every change to core tables automatically logged to `*_history` tables before modification.

## Implementation

**Core Function**: `database.py:238+` (`save_to_history()`)

**Pattern**: Call before UPDATE/DELETE, manual INSERT after creation

```python
# Before update/delete
save_to_history(cur, 'session', 'UPDATE', session_id, user_id=current_user.user_id)
cur.execute("UPDATE session SET name = %s WHERE session_id = %s", (new_name, session_id))

# Composite keys (session_tune, person_instrument)
save_to_history(cur, 'session_tune', 'DELETE', (session_id, tune_id), user_id=user_id)

# Helper function for getting current user_id
from database import get_current_user_id
user_id = get_current_user_id()  # Returns None outside request context
```

## User Tracking Columns

**Core Tables** (14 tables have these columns):
- `created_by_user_id INTEGER` - User who created the record
- `last_modified_user_id INTEGER` - User who last modified the record

**History Tables** (13 tables have these columns):
- `changed_by_user_id INTEGER` - User who made this specific change
- `created_by_user_id INTEGER` - Snapshot of original record's creator
- `last_modified_user_id INTEGER` - Snapshot of original record's last modifier

**NULL Values**: NULL indicates system/automated actions (cron jobs, imports, etc.)

## History Table Structure

**Common Fields** (all history tables):
- `history_id` SERIAL PRIMARY KEY
- `<table>_id` - Original record ID
- `operation` - 'INSERT', 'UPDATE', or 'DELETE'
- `changed_by_user_id` INTEGER - User ID who made the change, or NULL for system
- `changed_at` TIMESTAMPTZ - When change occurred
- All original table fields - Full snapshot

**Location**: `schema/create_history_tables.sql` (most)

## History Tables (13)

| Table | Tracks | Implementation | Schema |
|-------|--------|----------------|--------|
| `session_history` | Session definitions | Auto | `create_history_tables.sql:11-35` |
| `session_instance_history` | Instance dates/times | Auto | `create_history_tables.sql:38-55` |
| `session_instance_tune_history` | Tune log entries | `database.py:283-296` | `create_history_tables.sql:90-108` |
| `session_tune_history` | Session tune settings | `database.py:270-281` | `create_history_tables.sql:74-87` |
| `session_tune_alias_history` | Tune aliases | Auto | `create_history_tables.sql:133-149` |
| `session_person_history` | Membership | Auto | `create_history_tables.sql:152-167` |
| `session_instance_person_history` | Attendance | `database.py:341-352` | `create_history_tables.sql:170-183` |
| `tune_history` | Tune metadata | Auto | `create_history_tables.sql:58-71` |
| `tune_setting_history` | ABC cache | `database.py:259-268` | `create_tune_setting_table.sql` |
| `person_history` | Person records | `database.py:298-309` | `create_history_tables.sql:195-212` |
| `person_instrument_history` | Instruments | `database.py:328-339` | `create_person_instrument_history_table.sql` |
| `person_tune_history` | Learning status | Auto | `create_person_tune_history_table.sql` |
| `user_account_history` | Login accounts | `database.py:311-326` | `create_history_tables.sql:215-245` |

**Composite Keys**: `session_tune_history`, `person_instrument_history` use tuple IDs

## Common Indexes

All history tables have:
- `idx_<table>_history_<table>_id` - Find changes for record
- `idx_<table>_history_changed_at` - Time-based queries
- `idx_<table>_history_operation` - Filter by operation type
- `idx_<table>_history_changed_by_user` - Find changes by user

Core tables have:
- `idx_<table>_created_by` - Find records by creator

## Query Patterns

**All changes for record:**
```sql
SELECT * FROM session_history WHERE session_id = 123 ORDER BY changed_at DESC;
```

**Who changed what (by user_id):**
```sql
SELECT h.changed_by_user_id, u.username, h.changed_at, h.operation, h.name
FROM session_history h
LEFT JOIN user_account u ON h.changed_by_user_id = u.user_id
WHERE h.session_id = 123 AND h.operation = 'UPDATE'
ORDER BY h.changed_at DESC;
```

**Point-in-time recovery:**
```sql
SELECT * FROM session_history WHERE session_id = 123
AND changed_at <= '2025-06-01 23:59:59' ORDER BY changed_at DESC LIMIT 1;
```

**All changes by a specific user:**
```sql
SELECT * FROM session_history WHERE changed_by_user_id = 5 ORDER BY changed_at DESC;
```

## Change Attribution

**Values**:
- `NULL` - Automated/system actions (cron jobs, imports, scripts)
- `user_id INTEGER` - ID of the user who made the change

**Helper Function**: `get_current_user_id()` in `database.py`
- Returns current user's user_id within Flask request context
- Returns NULL when outside request context (background jobs, scripts)

**Best Practice**: Always pass `user_id` parameter in save_to_history()

## Login Tracking

**Table**: `login_history` (not a standard history table)
**Purpose**: Security auditing, failed login detection
**Fields**: user_id, login_timestamp, ip_address, user_agent, success
**Location**: `schema/create_login_history_table.sql:2`

## Audit Views

**Script**: `schema/create_audit_views.sql` - Simplified views for common queries

## Migration

**Schema Migration**: `schema/add_user_action_logging.sql`
- Adds `created_by_user_id` and `last_modified_user_id` to core tables
- Adds `changed_by_user_id` to history tables
- Drops legacy `changed_by` VARCHAR column from history tables
