# Session Model

Core data structures for tracking recurring and one-time music sessions.

## Tables

### `session` - Recurring Sessions
Represents a regular music session (e.g., "Mueller Monday Night Session").

**Key Fields**:
- `session_id` (PK) - Unique identifier
- `name` - Display name
- `path` - URL-friendly identifier (e.g., "austin/mueller")
- `location` - Physical location
- `recurrence` - JSON pattern (see Recurrence below)
- `default_start_time` - Typical start time
- `session_type` - "session" or "class"

**Location**: `schema/create_session_table.sql`

### `session_instance` - Specific Occurrences
Individual dated occurrences of sessions.

**Key Fields**:
- `session_instance_id` (PK)
- `session_id` (FK → session)
- `date` - Specific date of occurrence
- `start_time`, `end_time` - Time overrides
- `location_override` - Location override
- `is_cancelled` - Cancellation flag
- `comments` - Instance-specific notes
- `log_complete_date` - When log was marked complete

**Location**: `schema/create_session_instance_table.sql`

### `session_instance_tune` - Tune Logs
Individual tunes played during a session instance.

**Key Fields**:
- `session_instance_tune_id` (PK)
- `session_instance_id` (FK → session_instance)
- `tune_id` (FK → tune, nullable)
- `name` - Name as played
- `order_number` - Order within session
- `continues_set` - True if continues previous tune in a set
- `played_timestamp` - When tune was played
- `key_override` - Musical key override
- `setting_override` - Specific tune version/setting

**Location**: `schema/create_session_instance_tune_table.sql`

## Relationships

```
session (1) ──< session_instance (N)
session_instance (1) ──< session_instance_tune (N)
session_instance_tune (N) ──> tune (1, optional)
```

## Recurrence Patterns

Stored as JSON in `session.recurrence` field. Schema in `schema/recurrence_schema.json`.

**Examples**:
```json
// Every Monday
{"type": "weekly", "interval": 1, "daysOfWeek": [1]}

// First and third Tuesday
{"type": "monthly", "interval": 1, "daysOfWeek": [2], "setPositions": [1, 3]}

// One-time event
{"type": "one_time", "date": "2025-12-25"}
```

**Logic**: `session_instance_auto_create.py` generates instances from patterns

## Key Operations

### Create Session Instance
- Manual: `api_routes.py:/api/session_instance` POST
- Auto: `session_instance_auto_create.py:auto_create_session_instances()`

### Log Tunes
- Standard UI: `web_routes.py:session_instance_detail()` + `api_routes.py:/api/session_instance/<id>/tunes`
- Beta UI: `web_routes.py:session_instance_detail_beta()`

### Set Management
- Group tunes: Same `set_id` value
- Reorder: Update `sort_order` via API

## Access Patterns

### Get Session with Future Instances
```sql
SELECT s.*, si.date, si.session_instance_id
FROM session s
LEFT JOIN session_instance si ON s.session_id = si.session_id
WHERE s.session_id = ? AND si.date >= CURRENT_DATE
ORDER BY si.date
```

### Get Session Log
```sql
SELECT sit.*, st.tune_name, st.thesession_tune_id
FROM session_instance_tune sit
LEFT JOIN session_tune st ON sit.session_tune_id = st.session_tune_id
WHERE sit.session_instance_id = ?
ORDER BY sit.sort_order
```

## Related Specs

- [Tune Model](tune-model.md) - Linked tune metadata
- [People & Attendance](people-model.md) - Who attends sessions
- [Session Management Logic](../logic/session-logic.md) - Business rules
- [Session Logging UI](../ui/session-logging.md) - User interface
