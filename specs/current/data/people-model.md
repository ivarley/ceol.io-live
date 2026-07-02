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
- arrival_seq - (Feature 024) superseded and unused; per-person live-logging color now lives in `session_logger_color`

### session_logger_color
Permanent per-session palette color for the live logger (Feature 024).
- (session_id, person_id) composite PK
- color - SMALLINT palette index, assigned on first appearance and reused every instance
- Deliberately its own table: holding a color in `session_person`/`session_instance_person`
  would inflate a casual logger into a member/attendee. See [Live Logging](../logic/live-logging.md).

### person_instrument
Instruments a person plays (many-to-many).
- (person_id, instrument) composite PK
- instrument - canonical value from `instruments.py` `CANONICAL_INSTRUMENTS` (Title Case),
  or free text for "Other". All save paths normalize via `normalize_instrument`.
- `is_auto` BOOLEAN (default TRUE) - "auto" (linked) instruments follow
  `person_tune.learn_status`; manual ones are a curated per-instrument list that starts empty.

### person_tune
Personal tune learning tracking (the instrument-agnostic / "auto instruments" status).
- person_tune_id, person_id, tune_id
- `learn_status` VARCHAR(20) - "want to learn" / "learning" / "learned" (spaces, CHECK-constrained)
- `heard_count`, `learned_date` (auto-set by trigger when status crosses to/from 'learned')
- notes - Personal notes
- UNIQUE(person_id, tune_id)

### person_tune_instrument
Sparse per-instrument status **overrides** (a second axis on top of person_tune).
- (person_id, tune_id, instrument) composite PK; FK (person_id, tune_id) → person_tune ON DELETE CASCADE
- `status` VARCHAR(20) - same ladder as learn_status
- A row exists **only** when a per-instrument status was set by hand. Resolution for
  (person, tune, instrument): override row → else instrument `is_auto` → `person_tune.learn_status`
  → else not tracked. So a single-instrument or all-auto user stores zero rows here.
- Written by the `set_instrument_status` op (absolute-set, idempotent). Setting an auto
  instrument back to `learn_status` deletes the row (snap-back); `status: null` deletes it.

## Key Operations

**Create Person**: POST /api/person
**Check In**: POST /api/session_instance/<id>/attendees/checkin
**Update Instruments**: PUT /api/person/<id>/instruments
**Search People**: GET /api/session/<id>/people/search?q=<query>
**Set per-instrument status**: POST /api/my-tunes/ops `{type:"set_instrument_status", tune_id, instrument, status}`
**Set instrument auto/manual**: PUT /api/my-tunes/instrument-auto `{instrument, is_auto}`
**My tunes (with per-instrument data)**: GET /api/my-tunes returns `instruments` (with is_auto)
  and each tune's `instrument_status` (sparse overrides)

## Related

- [Authentication](../logic/auth.md) - User accounts and login
- [Attendance](../logic/attendance.md) - Attendance workflows
- [Session Model](session-model.md) - Session structure
