# Testing the Active Session Cron Job Locally

This guide explains how to test the active session cron job (`jobs/check_active_sessions.py`) locally on your Mac.

## Overview

The active session cron job runs every 15 minutes in production to:
- Activate session instances when they enter their active window (start_time - buffer_before)
- Deactivate session instances when they leave their active window (end_time + buffer_after)
- Update which people are "at" active sessions

Testing this locally requires:
1. A test database with sample sessions
2. The ability to simulate different times
3. Safe testing without affecting production data

## Quick Start

### 1. Set Up Test Database (One Time)

First, ensure you have the test database created:

```bash
# Create test database and user
psql -U postgres << EOF
CREATE DATABASE ceol_test;
CREATE USER test_user WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE ceol_test TO test_user;
EOF
```

Run the schema migrations against the test database:

```bash
# Run all schema files
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -f schema/add_active_session_tracking.sql
# ... run any other schema files you need
```

### 2. Create Test Data

The test wrapper can create sample sessions for you:

```bash
python3 jobs/test_active_sessions.py --setup-test-data
```

This creates 6 different test scenarios:
- **Evening Session (7pm)** - Thursday sessions that should activate at 6pm
- **Morning Session (9am)** - Wednesday sessions that end at 11am
- **Overlapping Sessions** - Friday sessions at 8pm and 9pm that overlap
- **NYC Timezone Session** - Tuesday session in Eastern Time
- **Future Session (2pm)** - Saturday sessions that shouldn't be active yet
- **Custom Buffer Session** - Sunday sessions with custom buffer times

### 3. Run Basic Tests

```bash
# Test with current time against test database
python3 jobs/test_active_sessions.py

# See what the output looks like
```

## Testing Options

### Test Against Test Database (Default)

```bash
# Basic run
python3 jobs/test_active_sessions.py

# With verbose logging
python3 jobs/test_active_sessions.py --verbose
```

### Test Against Production Database

**Caution:** This queries the real production database, but you can use `--dry-run` to make it safe.

```bash
# Dry run against production (safe - no changes)
python3 jobs/test_active_sessions.py --prod-db --dry-run

# Actually run against production (careful!)
python3 jobs/test_active_sessions.py --prod-db
```

### Simulate Different Times

The most powerful testing feature is time simulation:

```bash
# Simulate running at 6:59pm on a Thursday (evening sessions activate)
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 18:59:00"

# Simulate running at 9am on a Wednesday (morning sessions should be active)
python3 jobs/test_active_sessions.py --simulate-time "2025-10-22 09:00:00"

# Simulate running at midnight (deactivate evening sessions)
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 00:00:00"
```

### Use Predefined Scenarios

Quick scenarios for common testing situations:

```bash
# Test evening sessions activating
python3 jobs/test_active_sessions.py --scenario evening

# Test morning cleanup
python3 jobs/test_active_sessions.py --scenario morning

# Test overlapping sessions
python3 jobs/test_active_sessions.py --scenario overlap
```

## Understanding the Output

The test wrapper provides color-coded output:

### Example Output

```
================================================================================
Active Session Cron Job Tester
================================================================================

✓ Loaded test database configuration
🕐 Using current system time: 2025-10-22T18:59:00

Running active session check...

================================================================================
Summary
================================================================================

✓ Activated 2 session(s):
  • TEST: Evening Session (7pm) (session_id=101, instance_id=201)
  • TEST: Overlap Session A (8pm) (session_id=103, instance_id=205)

✓ Deactivated 1 session(s):
  • TEST: Morning Session (9am) (session_id=102, instance_id=203)

  No errors

✓ Test completed successfully
```

### Color Coding

- 🟢 **Green** - Successful activations
- 🔵 **Cyan** - Deactivations
- 🟡 **Yellow** - Warnings or dry-run mode
- 🔴 **Red** - Errors

## Testing Scenarios

### Scenario 1: Session Activation

Test that a session becomes active at the right time:

```bash
# Create test data
python3 jobs/test_active_sessions.py --setup-test-data

# Simulate 1 minute before session start (with 60min buffer, should activate)
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 18:00:00"

# Check that the session was activated
```

### Scenario 2: Session Deactivation

Test that a session deactivates after its active window:

```bash
# Simulate 61 minutes after session end time
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 23:31:00"

# Check that the evening session was deactivated
```

### Scenario 3: Multiple Active Sessions

Test that multiple sessions can be active simultaneously:

```bash
# Simulate Friday at 9:30pm (both overlap sessions should be active)
python3 jobs/test_active_sessions.py --scenario overlap
```

### Scenario 4: Time Zone Handling

Test that sessions activate based on local time, not UTC:

```bash
# The NYC session is in Eastern Time
# When it's 8pm in NYC, it's 7pm in Austin
python3 jobs/test_active_sessions.py --simulate-time "2025-10-21 20:00:00"
```

### Scenario 5: Dry Run Against Production

See what would happen in production without making changes:

```bash
python3 jobs/test_active_sessions.py --prod-db --dry-run
```

## Troubleshooting

### "Database connection failed"

**Problem:** Can't connect to the test database.

**Solution:**
1. Ensure PostgreSQL is running: `brew services start postgresql`
2. Check `.env.test` has correct credentials
3. Verify test database exists: `psql -U test_user -d ceol_test -c "SELECT 1"`

### "No sessions to activate/deactivate"

**Problem:** Test runs but nothing happens.

**Solution:**
1. Make sure you ran `--setup-test-data`
2. Check that the simulated time matches the test data days
3. Use `--verbose` to see debug output

### "test_scenarios.py not found"

**Problem:** Can't set up test data.

**Solution:**
Make sure you're running from the project root directory and `jobs/test_scenarios.py` exists.

### "Import errors"

**Problem:** Can't import modules.

**Solution:**
```bash
# Make sure you're in the project root
cd /path/to/ceol.io-live

# Ensure dependencies are installed
pip install -r requirements.txt
```

## Manual Testing Workflow

Here's a complete workflow for thorough testing:

```bash
# 1. Set up fresh test data
python3 jobs/test_active_sessions.py --setup-test-data

# 2. Test that nothing is active right now
python3 jobs/test_active_sessions.py

# 3. Test evening session activation (6pm Thursday)
python3 jobs/test_active_sessions.py --scenario evening

# 4. Test that sessions stay active during their window
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 20:00:00"

# 5. Test session deactivation (after 11:30pm)
python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 23:35:00"

# 6. Test with production data (dry run)
python3 jobs/test_active_sessions.py --prod-db --dry-run

# 7. Inspect database state
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
SELECT s.name, si.date, si.start_time, si.is_active
FROM session_instance si
JOIN session s ON si.session_id = s.session_id
WHERE s.name LIKE 'TEST:%'
ORDER BY si.date, si.start_time"
```

## Verifying Results in Database

After running tests, you can check the database state:

```bash
# Check which instances are currently active
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
SELECT
    s.name,
    si.session_instance_id,
    si.date,
    si.start_time,
    si.end_time,
    si.is_active
FROM session_instance si
JOIN session s ON si.session_id = s.session_id
WHERE s.name LIKE 'TEST:%'
ORDER BY si.is_active DESC, si.date, si.start_time"

# Check which people are at active sessions
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
SELECT
    p.person_id,
    p.first_name,
    p.last_name,
    p.at_active_session_instance_id,
    si.date,
    s.name
FROM person p
JOIN session_instance si ON p.at_active_session_instance_id = si.session_instance_id
JOIN session s ON si.session_id = s.session_id
WHERE p.at_active_session_instance_id IS NOT NULL"
```

## Production Testing

Before deploying to production:

1. **Test against production with dry-run:**
   ```bash
   python3 jobs/test_active_sessions.py --prod-db --dry-run
   ```

2. **Verify the output makes sense** - Check that:
   - Sessions are activating/deactivating at the right times
   - Time zones are handled correctly
   - Buffer windows are applied correctly

3. **Check production cron configuration** in `render.yaml`:
   ```yaml
   - type: cron
     name: ceol-io-active-sessions
     schedule: "14,29,44,59 * * * *"
   ```

4. **Monitor production logs** after deployment to verify it's working

## Advanced Testing

### Test with Real User Data

To test how the system handles people checking in:

```bash
# 1. Set up test data
python3 jobs/test_active_sessions.py --setup-test-data

# 2. Manually check in a person to a session instance
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
VALUES (
    (SELECT session_instance_id FROM session_instance WHERE session_id =
        (SELECT session_id FROM session WHERE name = 'TEST: Evening Session (7pm)') LIMIT 1),
    1,
    'yes'
)"

# 3. Activate the session
python3 jobs/test_active_sessions.py --scenario evening

# 4. Check that person is now "at" the session
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
SELECT at_active_session_instance_id FROM person WHERE person_id = 1"
```

### Performance Testing

To test performance with many sessions:

```bash
# Modify test_scenarios.py to create 100+ sessions
# Then run with timing:
time python3 jobs/test_active_sessions.py --verbose
```

## Cleanup

To clean up test data:

```bash
# Remove all test sessions
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -c "
DELETE FROM session_instance WHERE session_id IN (
    SELECT session_id FROM session WHERE name LIKE 'TEST:%'
);
DELETE FROM session WHERE name LIKE 'TEST:%';
"

# Or just drop and recreate the entire test database
dropdb -U test_user ceol_test
createdb -U test_user ceol_test
# Then re-run schema migrations
```

## Tips

1. **Use descriptive simulate times** - Pick times that make sense for your test (6:59pm for evening sessions, etc.)

2. **Test edge cases:**
   - Exactly at buffer boundary times
   - Midnight crossover (11:59pm to 12:01am)
   - Daylight saving time transitions
   - Leap seconds (probably not needed!)

3. **Keep test data fresh** - Run `--setup-test-data` regularly to reset to a known state

4. **Use dry-run liberally** - When in doubt, use `--dry-run` to see what would happen

5. **Check the database** - Don't just trust the output; verify the database state matches expectations

## Next Steps

After testing locally:

1. Verify the production cron job configuration in `render.yaml`
2. Deploy to production
3. Monitor logs in Render dashboard
4. Set up alerts for cron job failures

## Support

If you encounter issues:

1. Check this documentation
2. Use `--verbose` flag for more details
3. Check the database state manually
4. Review `active_session_manager.py` for the core logic
