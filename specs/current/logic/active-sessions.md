# Active Session Tracking

Real-time tracking of which sessions are happening now and which people are attending.

## Data Model

**session_instance.is_active**: TRUE when within active window | `schema/add_active_session_tracking.sql`

**Active Window**: `[start_time - buffer_before] to [end_time + buffer_after]`
- Default buffer_before: 30 minutes
- Default buffer_after: 60 minutes
- Example: 7pm-10pm session active 6:30pm-11pm

**person.active_session_instance_id**: Which session person is currently at (NULL if none)
- Index: `idx_person_active_session` WHERE NOT NULL (partial)

## Manager

**Function**: `update_active_sessions()` | `active_session_manager.py:23-150`

**Process**: Query sessions → calc time+1min in each timezone → query ±2 days → calc windows → activate/deactivate

**Lookahead**: 6:59pm activates 7pm session (smooth UX)

**Activate**: Set `is_active=TRUE`, update `person.active_session_instance_id`

**Deactivate**: Set `is_active=FALSE`, recalc person locations

## Cron Job

**File**: `jobs/check_active_sessions.py`

**Schedule**: Every 15 minutes

**Deployment**: Render.com cron job (see `render.yaml`)

**Why 15 min**: Balance near-real-time vs database load

**See**: [Active Sessions Cron](../services/active-sessions-cron.md)

## API Endpoints

**Get Person Active**: `GET /api/person/<id>/active_session` - Returns session details or null

**Manual Trigger**: `POST /api/session_instance/<id>/update_active_status` - Admin/testing

**Implementation**: `api_routes.py`

## UI Integration

**In Session Badge**: Header green dot | `templates/base.html:326-336`
- Appears when `person.active_session_instance_id` IS NOT NULL
- Hover: Popup with details
- Click: Navigate to session
- Data: Server-rendered from `current_user.active_session`
- JavaScript: `templates/base.html:644-831`

**Session Status**: "LIVE NOW" badge on session pages when `is_active=TRUE`

## Business Rules

**Multiple Sessions**: If person at 2+ active sessions, choose most recently started

**Time Changes**: Active window recalculates on next cron (within 15 min)

**Cancelled**: Never marked active (`WHERE is_cancelled=FALSE`)

**Manual Override**: Admin can set `is_active`, may be reverted by cron

## Performance

**Indexes** (both partial):
- `idx_session_instance_is_active` WHERE is_active=TRUE
- `idx_person_active_session` WHERE active_session_instance_id IS NOT NULL

**Query Scope**: Only ±2 days from current date

**Updates**: Batch committed per session

## Error Handling

**Invalid Timezone**: Log error, skip session, continue others

**Missing Times**: Skip instance (can't calc window)

**DB Connection**: Log error, retry next run (idempotent)

## Testing

**Manual**: `README-TESTING-CRON.md` - Create test session, run `check_active_sessions.py`, verify flags

**Scripts**: `jobs/test_scenarios.py`
