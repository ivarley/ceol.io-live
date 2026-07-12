# Attendance System (Feature 001)

Track who attends each session instance with attendance status and instruments.

## Overview

- **Feature ID**: Feature 001
- **Purpose**: Record attendance at session instances
- **Roles**: Regular members, session admins, system admins
- **Status**: Active, in production

## Data Model

### Tables
- `session_person` - A person's relationship to a session: `relationship` ('member'|'visitor'),
  `confirmed`, `archived`, `is_admin` (spec 034)
- `session_instance_person` - Attendance records per instance
- `person_instrument` - Instruments a person plays

See [People Model](../data/people-model.md) for schema details.

**Check-in auto-creates a `session_person` row** if none exists, as
`relationship='visitor', confirmed=FALSE`. It never confirms, never un-archives, and never
downgrades an existing member — being logged as present tonight is not a claim about
belonging.

## API Endpoints

All in `api_routes.py`:

### GET `/api/session_instance/<id>/attendees`
Returns list of attendees for a session instance.

**Response**:
```json
[
  {
    "person_id": 123,
    "first_name": "John",
    "last_name": "Doe",
    "attendance": "yes",
    "relationship": "member",
    "is_admin": false,
    "instruments": ["fiddle", "guitar"]
  }
]
```

**Permissions**: `is_admin OR confirmed` (see Business Rules)

### POST `/api/session_instance/<id>/attendees/checkin`
Check in a person (creates attendance record).

**Body**:
```json
{
  "person_id": 123,
  "attendance": "yes"  // "yes", "maybe", or "no"
}
```

**Permissions**: Admins only

### POST `/api/person`
Create new person with optional instruments.

**Body**:
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane@example.com",
  "instruments": ["banjo", "mandolin"]
}
```

**Returns**: `{"person_id": 456}`

### GET/PUT `/api/person/<id>/instruments`
Get or update person's instruments.

**PUT Body**: `{"instruments": ["fiddle", "whistle"]}`

### DELETE `/api/session_instance/<id>/attendees/<person_id>`
Remove attendance record.

**Permissions**: Admins only

### GET `/api/session/<id>/people/search?q=<query>`
Search people **on this session's roster**. There is no global person search: you can never
discover people from other sessions (spec 034). Archived people are excluded from the default
list but returned by an explicit query.

**Returns**: Array of person objects matching query

## Business Rules

### Permissions

**People-visibility** — the People tab, person detail sheets, and all attendance lists:
- System admins: Always
- Session admins (`is_admin`): Always
- Anyone whose `session_person.confirmed` is TRUE — member **or** visitor
- Everyone else, *including unconfirmed members*: No access

One predicate, `is_admin OR confirmed`, replacing the two contradictory gates that used to
exist. People-visibility is granted **by the session**, never claimed by joining it: self-join
lands `confirmed = FALSE`, and check-in never confirms anyone.

Everything else about a session — tunes, logs, history — stays visible to everyone.

**Edit Attendance** (POST/DELETE):
- System admins: Always
- Session admins: Only for their sessions
- Others: No access

**Implementation**: `auth.py:can_view_attendance()`, `auth.py:can_manage_attendance()`

### Instruments

- Many-to-many via `person_instrument`
- Free text (not constrained to list)
- Editable per person, not per attendance

## UI Integration

### Templates

**`templates/session_instance_players.html`** (+ `partials/attendance_tab.html`,
`static/js/shared/attendance.js`):
- Attendance list display
- Check-in buttons for regulars

**Session page People tab** (`frontend/src/sessionpage/PeopleTab.svelte` —
the session-detail page is a Svelte shell, spec 035):
- Session members list (regulars/all filter + search)
- Search interface for adding existing people
- Create new person form
- Person-detail modal with `/people/<id>` deep link

### AJAX Workflows

**Check-in Regular**:
1. Click name → POST `/api/session_instance/<id>/attendees/checkin`
2. Update UI with attendance badge
3. Show success message

**Add Previous Attendee**:
1. Search → GET `/api/session/<id>/people/search?q=...`
2. Select person → POST checkin
3. Update attendance list

**Create New Person**:
1. Fill form → POST `/api/person`
2. Receive person_id → POST checkin
3. Add to attendance list

## Error Handling

- **403**: User lacks permission
- **404**: Session instance or person not found
- **409**: Person already checked in
- **400**: Invalid attendance status or missing required fields

## Testing

**Contract tests** (`tests/contract/`):
- `test_get_attendees.py`
- `test_checkin_attendee.py`
- `test_search_people.py`
- `test_remove_attendee.py`
- `test_get_instruments.py`

**Unit tests** (`tests/unit/`):
- `test_routes.py` - Permission logic

## Related Specs

- [People Model](../data/people-model.md) - Database schema
- [Session Model](../data/session-model.md) - Session structure
- [Authentication](auth.md) - User/person relationship and permission system
