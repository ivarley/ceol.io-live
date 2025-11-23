# Attendance System (Feature 001)

Track who attends each session instance with attendance status and instruments.

## Overview

- **Feature ID**: Feature 001
- **Purpose**: Record attendance at session instances
- **Roles**: Regular members, session admins, system admins
- **Status**: Active, in production

## Data Model

### Tables
- `session_person` - Session membership (is_regular, is_admin flags)
- `session_instance_person` - Attendance records per instance
- `person_instrument` - Instruments a person plays

See [People Model](../data/people-model.md) for schema details.

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
    "is_regular": true,
    "is_admin": false,
    "instruments": ["fiddle", "guitar"]
  }
]
```

**Permissions**: Regulars and admins can view

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
Search people associated with a session (past attendees, regulars).

**Returns**: Array of person objects matching query

## Business Rules

### Permissions

**View Attendance** (GET attendees):
- System admins: Always
- Session admins: If is_admin for this session
- Session regulars: If is_regular for this session
- Others: No access

**Edit Attendance** (POST/DELETE):
- System admins: Always
- Session admins: Only for their sessions
- Others: No access

**Implementation**: `api_routes.py:can_view_attendance()`, `can_edit_attendance()`

### Regular Members

- Tracked in `session_person.is_regular`
- One-click check-in available in UI
- Displayed prominently in attendance UI

### Instruments

- Many-to-many via `person_instrument`
- Free text (not constrained to list)
- Editable per person, not per attendance

## UI Integration

### Templates

**`templates/session_detail.html`**:
- Attendance list display
- Check-in buttons for regulars
- Search interface for adding people
- Create new person form

**Components** (`templates/components/`):
- Attendance status badges
- Instrument tags

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
- [Authentication](auth.md) - User/person relationship
