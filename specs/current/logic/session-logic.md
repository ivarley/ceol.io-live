# Session Management Logic

Recurrence patterns, auto-creation, and timezone handling for sessions and instances.

## Recurrence System

**File**: `recurrence_utils.py` - `SessionRecurrence` class

**JSON Storage**: `session.recurrence` field (schema: `schema/recurrence_schema.json`)

**Pattern Types**:
```json
// Weekly: Every Monday
{"type": "weekly", "interval": 1, "daysOfWeek": [1]}

// Monthly: First and third Tuesday
{"type": "monthly", "interval": 1, "daysOfWeek": [2], "setPositions": [1, 3]}

// One-time
{"type": "one_time", "date": "2025-12-25"}
```

**Day Numbers**: ISO 8601 (Monday=1, Sunday=7)

**Key Methods**:
- `get_occurrences(start_date, end_date)` - Generate dates in range
- `validate()` - Check pattern validity

## Auto-Creation

**Function**: `auto_create_next_week_instances(session_id)` | `session_instance_auto_create.py:17-100`

**Process**: Parse recurrence → calc tomorrow+7 days → check existing → insert missing → return (count, dates)

**API**: `POST /api/session/<id>/auto_create_instances`

## Session States

**Active Query**:
```sql
WHERE (termination_date IS NULL OR termination_date >= CURRENT_DATE)
```

**States**:
- Future: `initiation_date` > today
- Active: Between initiation and termination (or no termination)
- Terminated: `termination_date` < today

## Instance States

- Future/Past/Today: Based on `date` field
- Cancelled: `is_cancelled = TRUE` (still visible, strikethrough in UI)
- Active: `is_active = TRUE` (managed by `active_session_manager.py` cron)
- Complete: `log_complete_date` IS NOT NULL (tune log finalized)

**Active Status**: See [Active Sessions](active-sessions.md)

## Timezone Handling

**Field**: `session.timezone` - IANA identifier (e.g., "America/Chicago")

**Storage**: All TIMESTAMPTZ in UTC, convert to local for display via `zoneinfo`

## Session Path

**Format**: `{city}/{venue-slug}` (e.g., `austin/mueller`)

**URL**: `/sessions/{path}/{date}`

**Constraints**: Unique, lowercase, hyphens for spaces, no special chars

**Generation**: `web_routes.py` (session creation)

## Key APIs

**Sessions**: `POST /api/session`, `GET /sessions/{path}` | `api_routes.py`, `web_routes.py`

**Instances**: `POST /api/session_instance`, `GET /sessions/{path}/{date}`

**Auto-create**: `POST /api/session/<id>/auto_create_instances`

**Cancellation**: `PUT /api/session_instance/<id>` with `{"is_cancelled": true}`
