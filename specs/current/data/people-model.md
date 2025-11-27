# People & Attendance Model

User accounts, person identities, session membership, attendance tracking.

## Overview

**Separation**: person (identity) vs user_account (authentication)
- person can exist without user account (for attendance tracking)
- user_account must link to person for login

## Tables

### person
Individual identity (with or without login).
- person_id, first_name, last_name, email, phone, location
- active - Boolean, default true. When false, person is deactivated.
- at_active_session_instance_id - Currently attending session (FK)

#### Deactivation
When a person is deactivated (active=false):
- They don't appear in session people lists
- They cannot be added to sessions, session instances, or set as "started by" on tune sets
- Existing associations (session memberships, attendance records) are preserved but hidden
- Admin can reactivate from admin/people/{id} page (Danger Zone section)

### user_account
Login credentials and preferences.
- user_id, person_id (FK), username, hashed_password
- is_system_admin, is_active, email_verified
- timezone, auto_save_tunes, auto_save_interval (10/30/60 seconds)
- verification_token, password_reset_token

See [Authentication](../logic/auth.md) for details.

### session_person
Session membership (regular members and admins).
- (session_id, person_id) composite PK
- is_regular - Regular member (quick check-in)
- is_admin - Session admin (can edit session, manage attendance)

### session_instance_person
Attendance records for specific instances.
- (session_instance_id, person_id) composite PK
- attendance - "yes", "maybe", or "no"
- checked_in_at timestamp

### person_instrument
Instruments a person plays (many-to-many).
- (person_id, instrument) composite PK
- instrument is free text (fiddle, guitar, banjo, etc.)

### person_tune
Personal tune learning tracking.
- person_tune_id, person_id, tune_id
- status - "want_to_learn", "learning", "learned"
- times_heard, last_heard_date
- notes - Personal notes

## Key Operations

**Create Person**: POST /api/person
**Check In**: POST /api/session_instance/<id>/attendees/checkin
**Update Instruments**: PUT /api/person/<id>/instruments
**Search People**: GET /api/session/<id>/people/search?q=<query>

## Related

- [Authentication](../logic/auth.md) - User accounts and login
- [Attendance](../logic/attendance.md) - Attendance workflows
- [Session Model](session-model.md) - Session structure
