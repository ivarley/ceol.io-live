# 011 Activity View

Admin-only page showing recent site activity in a unified feed.

## Primary View
Shows creates and modifications from core tables (using `created_date`/`last_modified_date`).

## Filters

**Category buttons**: All | Sessions | People | Tunes | Logs
Junction tables appear in multiple categories:

- Sessions: session, session_tune, session_tune_alias, session_person
- People: person, user_account, person_instrument, person_tune, session_person, session_instance_person, login
- Tunes: tune, tune_setting, session_tune, session_tune_alias
- Logs: session_instance, session_instance_tune, session_instance_person

**Additional filters**: Time range, activity type (created/modified), session, user search

## Drill-Down
Click any row to see full change history for that record (from `*_history` tables).

## Display
- Timestamp, entity type, entity name (linked), activity type, user
- Paginated, 50 per page