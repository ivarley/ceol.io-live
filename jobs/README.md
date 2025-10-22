# Jobs Directory

This directory contains scheduled job scripts for the application.

## Scripts

### check_active_sessions.py
**Production cron job** that runs every 15 minutes (at :14, :29, :44, :59) to manage active session instances.

- Activates sessions when they enter their active window
- Deactivates sessions when they leave their active window
- Updates people's current location based on active sessions

**Do not modify this file for testing.** Use `test_active_sessions.py` instead.

### test_active_sessions.py
**Development testing wrapper** for the active session cron job.

Provides flexible testing with:
- Database selection (test or production)
- Time simulation
- Dry-run mode
- Predefined scenarios
- Test data generation

See `README-TESTING-CRON.md` for full documentation.

**Quick examples:**
```bash
# Basic test
python3 jobs/test_active_sessions.py

# Set up test data
python3 jobs/test_active_sessions.py --setup-test-data

# Dry run against production
python3 jobs/test_active_sessions.py --prod-db --dry-run

# Simulate evening sessions
python3 jobs/test_active_sessions.py --scenario evening
```

### test_scenarios.py
**Test data generator** that creates sample sessions for testing.

Creates 6 different scenarios:
- Evening sessions (7pm Thursday)
- Morning sessions (9am Wednesday)
- Overlapping sessions (Friday 8pm and 9pm)
- Different timezone (NYC Tuesday)
- Future sessions (Saturday 2pm)
- Custom buffer times (Sunday 3pm)

Can be run directly:
```bash
python3 jobs/test_scenarios.py
```

Or via the test wrapper:
```bash
python3 jobs/test_active_sessions.py --setup-test-data
```

## Documentation

- **README-TESTING-CRON.md** - Comprehensive guide for testing the cron job locally
  - Setup instructions
  - Usage examples
  - Testing scenarios
  - Troubleshooting

## Production Deployment

The production cron job is configured in `render.yaml`:

```yaml
- type: cron
  name: ceol-io-active-sessions
  env: python
  schedule: "14,29,44,59 * * * *"
  buildCommand: "pip install -r requirements.txt"
  startCommand: "python3 jobs/check_active_sessions.py"
```

## Development Workflow

1. **Make changes to `active_session_manager.py`**
2. **Test locally:** `python3 jobs/test_active_sessions.py`
3. **Test edge cases with time simulation**
4. **Dry run against production:** `python3 jobs/test_active_sessions.py --prod-db --dry-run`
5. **Deploy and monitor**
