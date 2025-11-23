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

### Active Window Calculation

A session instance is considered "active" during:
- **Before session**: `buffer_before` minutes before start time (default: 30 min)
- **During session**: Between start and end time
- **After session**: `buffer_after` minutes after end time (default: 60 min)

All times calculated in session's local timezone.

### Lookahead

Uses 1-minute lookahead to ensure sessions scheduled for round times (e.g., 7:00pm) become active precisely at that time when cron runs at :59.

## Implementation

### Core Logic

Located in `active_session_manager.py:update_active_sessions()`

**Process**:
1. Query all sessions with recurrence patterns
2. For each session, calculate if it should be active now
3. Check database for existing active session instance
4. Activate or deactivate as needed
5. Update `session_person.current_location` for affected people

### Database Tables

**`session.active_session_instance_id`**: Currently active instance (FK → session_instance)
**`session_person.current_location`**: Person's current location text

See `schema/add_active_session_tracking.sql`

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

**`GET /api/active-sessions`**: Returns currently active sessions (uses data set by cron)

**`GET /api/session/<id>/active`**: Check if specific session is active

### UI Display

**Session detail page**: Shows "Currently Active" badge if session is active

**Person page**: Shows current location if person is at an active session

## Related Specs

- [Active Sessions Logic](../logic/active-sessions.md) - Business logic and API endpoints
- [Session Model](../data/session-model.md) - Database schema for active tracking
- [Session Management](../logic/session-logic.md) - Recurrence patterns used for timing
