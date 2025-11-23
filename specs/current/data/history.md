# History & Audit Trail

Every change to core tables automatically logged to `*_history` tables before modification.

## Implementation

**Core Function**: `database.py:216-353` (`save_to_history()`)

**Pattern**: Call before UPDATE/DELETE, manual INSERT after creation

```python
# Before update/delete
save_to_history(cur, 'session', 'UPDATE', session_id, changed_by=current_user.username)
cur.execute("UPDATE session SET name = %s WHERE session_id = %s", (new_name, session_id))

# Composite keys (session_tune, person_instrument)
save_to_history(cur, 'session_tune', 'DELETE', (session_id, tune_id), changed_by)
```

## History Table Structure

**Common Fields** (all history tables):
- `history_id` SERIAL PRIMARY KEY
- `<table>_id` - Original record ID
- `operation` - 'INSERT', 'UPDATE', or 'DELETE'
- `changed_by` VARCHAR(255) - Username or 'system'
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

## Query Patterns

**All changes for record:**
```sql
SELECT * FROM session_history WHERE session_id = 123 ORDER BY changed_at DESC;
```

**Who changed what:**
```sql
SELECT changed_by, changed_at, operation, name FROM session_history
WHERE session_id = 123 AND operation = 'UPDATE' ORDER BY changed_at DESC;
```

**Point-in-time recovery:**
```sql
SELECT * FROM session_history WHERE session_id = 123
AND changed_at <= '2025-06-01 23:59:59' ORDER BY changed_at DESC LIMIT 1;
```

## Change Attribution

**Values**: `'system'` (automated), `'admin'`, or username

**Best Practice**: Always pass `changed_by` parameter in save_to_history()

## Login Tracking

**Table**: `login_history` (not a standard history table)
**Purpose**: Security auditing, failed login detection
**Fields**: user_id, login_timestamp, ip_address, user_agent, success
**Location**: `schema/create_login_history_table.sql:2`

## Audit Views

**Script**: `schema/create_audit_views.sql` - Simplified views for common queries
