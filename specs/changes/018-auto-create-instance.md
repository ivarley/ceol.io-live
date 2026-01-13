# 018 Auto Create Instance

**Status: Implemented**

Make a setting at the session level as to whether the system should automatically create instances at schedule times, and how far in advance to create them (with a default of 24 hours). Do the creation (if configured) in the same cron job that sets a session instance to active.

## Implementation

### Database Changes
- Added `auto_create_instances` column (BOOLEAN, default FALSE) to `session` table
- Added `auto_create_hours_ahead` column (INTEGER, default 24, range 1-168) to `session` table
- Migration: `schema/add_auto_create_instances.sql`

### Code Changes
- `session_instance_auto_create.py`: Added `auto_create_instances_hours_ahead()` function
- `active_session_manager.py`: Added new `auto_create_scheduled_instances()` function (separate from `update_active_sessions()`)
- `jobs/check_active_sessions.py`: Calls both `update_active_sessions()` and `auto_create_scheduled_instances()`

### How It Works
1. The cron job runs every 15 minutes
2. First calls `update_active_sessions()` to manage active/inactive status
3. Then calls `auto_create_scheduled_instances()` which:
   - Queries sessions with `auto_create_instances=TRUE`
   - For each, checks if instances should be created within `auto_create_hours_ahead` hours
   - Uses the session's recurrence pattern to determine occurrence dates and times
   - Only creates instances that don't already exist
4. Stats are returned separately for each operation
