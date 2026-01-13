# Active Sessions Cron Job

Scheduled job tracking which sessions are currently happening.

## Overview

**Location**: `jobs/check_active_sessions.py`
**Schedule**: Every 15 minutes (at :14, :29, :44, :59 past each hour)
**Purpose**: Activate/deactivate sessions based on their timing and buffer windows
**Technology**: Python cron job on Render

## Functionality

### What It Does

1. **Activates Sessions**: Marks session instances as active when they enter their active window
2. **Deactivates Sessions**: Marks session instances as inactive when they leave their active window
3. **Updates Location**: Sets people's current location based on active sessions they're attending
4. **Auto-Creates Instances**: For sessions with `auto_create_instances=TRUE`, creates upcoming instances based on recurrence pattern

### Active Window Calculation

A session instance is considered "active" during:
- **Before session**: `buffer_before` minutes before start time (default: 30 min)
- **During session**: Between start and end time
- **After session**: `buffer_after` minutes after end time (default: 60 min)

All times calculated in session's local timezone.

### Lookahead

Uses 1-minute lookahead to ensure sessions scheduled for round times (e.g., 7:00pm) become active precisely at that time when cron runs at :59.

### Auto-Creation

For sessions with `auto_create_instances=TRUE`:
- Checks if any instances should be created within `auto_create_hours_ahead` hours
- Uses the session's recurrence pattern to determine occurrence dates and times
- Only creates instances that don't already exist
- Default lookahead is 24 hours (configurable from 1-168 hours per session)

## Implementation

### Core Logic

The cron job calls two separate functions:

**`active_session_manager.py:update_active_sessions()`** - Active status management:
1. Query all non-terminated sessions
2. For each session, calculate if instances should be active now
3. Check database for existing active session instances
4. Activate or deactivate as needed
5. Update `person.at_active_session_instance_id` for affected people

**`active_session_manager.py:auto_create_scheduled_instances()`** - Instance auto-creation:
1. Query sessions with `auto_create_instances=TRUE`
2. For each session, check if instances should be created within `hours_ahead` window
3. Create missing instances based on recurrence pattern

### Database Tables

**`session_instance.is_active`**: Boolean flag for currently active instances
**`session.active_buffer_minutes_before`**: Minutes before session is considered active (default: 60)
**`session.active_buffer_minutes_after`**: Minutes after session is considered active (default: 60)
**`session.auto_create_instances`**: Whether to auto-create instances (default: FALSE)
**`session.auto_create_hours_ahead`**: Hours ahead to auto-create (default: 24, range: 1-168)
**`person.at_active_session_instance_id`**: FK to session_instance (person's current location)

See `schema/add_active_session_tracking.sql` and `schema/add_auto_create_instances.sql`

### Return Value

```python
{
    'activated': [
        {'session_id': 7, 'instance_id': 123, 'session_name': 'Mueller Monday'},
        ...
    ],
    'deactivated': [
        {'session_id': 8, 'instance_id': 124, 'session_name': 'Saengerrunde'},
        ...
    ],
    'auto_created': [
        {'session_id': 7, 'session_name': 'Mueller Monday', 'instances_created': 1, 'dates': ['2025-01-20']},
        ...
    ],
    'errors': [
        {'session_id': 9, 'error': 'Invalid timezone'},
        ...
    ]
}
```

## Deployment

Configured in `render.yaml`:

```yaml
- type: cron
  name: ceol-io-active-sessions
  env: python
  schedule: "14,29,44,59 * * * *"
  buildCommand: "pip install -r requirements.txt"
  startCommand: "python3 jobs/check_active_sessions.py"
```

## Local Development

### Running Locally

```bash
# Basic run
python3 jobs/check_active_sessions.py

# Or use test wrapper
python3 jobs/test_active_sessions.py
```

### Testing Tools

**`jobs/test_active_sessions.py`**: Development testing wrapper with:
- Database selection (test or production)
- Time simulation
- Dry-run mode
- Predefined scenarios
- Test data generation

**Examples**:
```bash
# Test with dry run
python3 jobs/test_active_sessions.py --dry-run

# Simulate time
python3 jobs/test_active_sessions.py --simulate-time "2024-01-15 19:00"

# Test specific scenario
python3 jobs/test_active_sessions.py --scenario evening

# Set up test data
python3 jobs/test_active_sessions.py --setup-test-data
```

**`jobs/test_scenarios.py`**: Creates sample test sessions:
- Evening sessions (7pm Thursday)
- Morning sessions (9am Wednesday)
- Overlapping sessions (Friday 8pm and 9pm)
- Different timezone (NYC Tuesday)
- Future sessions (Saturday 2pm)
- Custom buffer times (Sunday 3pm)

### Documentation

See `jobs/README.md` and `README-TESTING-CRON.md` for comprehensive testing guide.

## Monitoring

**Logs**: Render dashboard shows cron execution logs

**Output Format**:
```
2024-01-15 19:14:00 - Starting active session check
2024-01-15 19:14:00 - Current UTC time: 2024-01-15T19:14:00+00:00
2024-01-15 19:14:01 - Activated: 2 sessions
  - Mueller Monday (session_id=7, instance_id=123)
  - Saengerrunde (session_id=8, instance_id=124)
2024-01-15 19:14:01 - Deactivated: 1 sessions
  - Old Session (session_id=5, instance_id=100)
2024-01-15 19:14:01 - Errors: 0
```

## Error Handling

- Non-fatal errors logged but don't stop processing other sessions
- Fatal errors exit with code 1 (Render will alert)
- Invalid timezone or recurrence patterns logged as errors

## Integration Points

### API Endpoints

**`GET /api/session/<id>/active_instance`**: Returns active instance IDs for session

**`GET /api/person/<id>/active_session`**: Returns person's active session

### UI Display

**Session detail page**: Shows "Currently Active" badge if session is active

**Person page**: Shows current location if person is at an active session

## Related Specs

- [Active Sessions Logic](../logic/active-sessions.md) - Business logic and API endpoints
- [Session Model](../data/session-model.md) - Database schema for active tracking
- [Session Management](../logic/session-logic.md) - Recurrence patterns used for timing
