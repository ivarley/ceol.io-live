# Database Schema Reference

28 tables organized into core domain, tunes, people, and audit tracking.

## Tables by Category

### Core Domain (8)
- `session` - Recurring session definitions | `schema/create_session_table.sql:2`
- `session_instance` - Specific dated occurrences | `schema/create_session_instance_table.sql:2`
- `session_instance_tune` - Tune log entries (order, sets) | `schema/create_session_instance_tune_table.sql:2`
- `session_tune` - Session-specific tune settings (key, alias) | `schema/create_tune_tables.sql:13`
- `session_tune_alias` - Additional tune names | `schema/create_session_tune_alias_table.sql:2`
- `session_person` - Membership & roles | `schema/create_session_person_table.sql:3`
- `session_instance_person` - Attendance records | `schema/create_session_instance_person_table.sql:3`
- `user_session` - "My Sessions" tracking | `schema/create_user_session_table.sql:2`

### Tunes (3)
- `tune` - Canonical metadata from thesession.org | `schema/create_tune_tables.sql:2`
- `tune_setting` - ABC notation & images (cached) | `schema/create_tune_setting_table.sql:5`
- `person_tune` - Personal learning status | `schema/create_person_tune_table.sql:2`

### People (3)
- `person` - Attendees, musicians | `schema/create_person_table.sql:2`
- `user_account` - Login credentials | `schema/create_user_table.sql:2`
- `person_instrument` - Instruments played | `schema/create_person_instrument_table.sql:3`

### Audit (13)
All core tables have `*_history` tables tracking INSERT/UPDATE/DELETE. See [History](history.md).

### Tracking (1)
- `login_history` - Login event tracking | `schema/create_login_history_table.sql:2`

## Key Fields Quick Reference

### session
- `path` VARCHAR(255) UNIQUE - URL slug (e.g., "austin/mueller")
- `timezone` VARCHAR(50) - IANA timezone for local times
- `recurrence` TEXT - JSON pattern (parsed by `recurrence_utils.py`)
- `initiation_date` / `termination_date` - Active date range

### session_instance
- `date` DATE - Occurrence date
- `is_active` BOOLEAN - Currently happening (cron-managed)
- `is_cancelled` BOOLEAN - Cancelled flag
- `log_complete_date` TIMESTAMPTZ - Tune log finalized timestamp

### session_instance_tune
- `tune_id` INTEGER (nullable) - Link to canonical tune
- `name` VARCHAR(255) - Tune name as played
- `order_position` VARCHAR(32) - Fractional index for ordering (base-62 CRDT string)
- `continues_set` BOOLEAN - Set continuation flag

### tune
- `tune_id` INTEGER PK - thesession.org ID
- `tune_type` VARCHAR(50) - Jig, Reel, etc. (15 types)
- `tunebook_count_cached` INTEGER - Popularity metric

### tune_setting
- `setting_id` INTEGER PK - thesession.org setting ID
- `abc` TEXT - Full ABC notation
- `incipit_abc` TEXT - First 2 bars
- `image` / `incipit_image` BYTEA - Rendered PNGs

### person
- `active_session_instance_id` INTEGER - Currently at session (cron-managed)
- `thesession_user_id` INTEGER - External ID

### user_account
- `person_id` INTEGER UNIQUE - One user per person
- `is_system_admin` BOOLEAN - Admin flag
- `email_verified` BOOLEAN - Email verification status

## Important Indexes

**Performance:**
- `idx_session_instance_session_date` UNIQUE (session_id, date) - No duplicate dates
- `idx_session_instance_is_active` WHERE is_active = TRUE - Partial index
- `idx_tune_tunebook_count` (tunebook_count_cached DESC) - Popularity sorting
- `idx_person_active_session` WHERE active_session_instance_id IS NOT NULL

**Search:**
- `idx_tune_name` - Tune name searches
- `idx_person_name` (last_name, first_name)

## Key Concepts

**Recurrence:** JSON in `session.recurrence` (weekly/monthly/one-time patterns)

**Active Sessions:** `is_active` managed by `active_session_manager.py` (15-min cron)

**Tune Linking:** `tune_id` NULL = unlinked, non-NULL = linked to thesession.org

**Sets:** Adjacent tunes with `continues_set = TRUE`

**History:** `database.py:save_to_history()` logs before UPDATE/DELETE

**unaccent**: Accent-insensitive searches | `schema/add_unaccent_extension.sql`

## Key Migrations

- `add_active_session_tracking.sql` - Active session tracking
- `expand_key_field_length.sql` - Key field VARCHAR(10) → VARCHAR(20)
- `optimize_session_tune_performance.sql` - Performance indexes

## Procedures

**merge_person_ids** - Merge duplicate person records | `schema/merge_person_ids_procedure.sql`
