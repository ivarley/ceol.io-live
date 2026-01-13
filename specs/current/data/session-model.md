# Session Model

Core data structures for tracking recurring and one-time music sessions.

## Tables

### `session` - Recurring Sessions
Represents a regular music session (e.g., "Mueller Monday Night Session").

**Key Fields**:
- `session_id` (PK) - Unique identifier
- `name` - Display name
- `path` - URL-friendly identifier (e.g., "austin/mueller")
- `location_name` - Location name
- `location_street` - Street address
- `location_website` - Venue website
- `location_phone` - Venue phone number
- `city`, `state`, `country` - Geographic location
- `timezone` - IANA timezone identifier (default: UTC)
- `recurrence` - JSON pattern (see Recurrence below)
- `session_type` - "regular" or "class" (default: "regular")
- `active_buffer_minutes_before` - Minutes before session is considered active (default: 60)
- `active_buffer_minutes_after` - Minutes after session is considered active (default: 60)
- `auto_create_instances` - Whether to auto-create instances ahead of schedule (default: FALSE)
- `auto_create_hours_ahead` - Hours ahead to auto-create instances (default: 24, range: 1-168)
- `created_date`, `last_modified_date` - Audit timestamps

**Note**: Times are stored on `session_instance`, not `session`. The recurrence pattern may contain default times.

**Location**: `schema/create_session_table.sql`

### `session_instance` - Specific Occurrences
Individual dated occurrences of sessions.

**Key Fields**:
- `session_instance_id` (PK)
- `session_id` (FK → session)
- `date` - Specific date of occurrence
- `start_time`, `end_time` - Start and end times
- `location_override` - Location override
- `is_cancelled` - Cancellation flag
- `is_active` - Currently active (managed by cron job)
- `comments` - Instance-specific notes
- `log_complete_date` - When log was marked complete
- `created_date`, `last_modified_date` - Audit timestamps

**Location**: `schema/create_session_instance_table.sql`

### `session_instance_tune` - Tune Logs
Individual tunes played during a session instance.

**Key Fields**:
- `session_instance_tune_id` (PK)
- `session_instance_id` (FK → session_instance)
- `tune_id` (FK → tune, nullable)
- `name` - Name as played
- `order_number` - Order within session (typically increments of 1000)
- `continues_set` - True if continues previous tune in a set
- `played_timestamp` - When tune was played
- `inserted_timestamp` - When log entry was created
- `key_override` - Musical key override (VARCHAR(20))
- `setting_override` - Specific thesession.org setting ID
- `created_date`, `last_modified_date` - Audit timestamps

**Constraint**: `tune_id IS NOT NULL OR name IS NOT NULL` (must have one)

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
- Group tunes: Set `continues_set = TRUE` to continue previous tune
- Break set: Set `continues_set = FALSE`
- Reorder: Update `order_number` via API

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
SELECT sit.*, t.name as canonical_name, t.type, t.thesession_tune_id
FROM session_instance_tune sit
LEFT JOIN tune t ON sit.tune_id = t.tune_id
WHERE sit.session_instance_id = ?
ORDER BY sit.order_number
```

## Related Specs

- [Tune Model](tune-model.md) - Linked tune metadata
- [People & Attendance](people-model.md) - Who attends sessions
- [Session Management Logic](../logic/session-logic.md) - Business rules
- [Session Logging UI](../ui/session-logging.md) - User interface
