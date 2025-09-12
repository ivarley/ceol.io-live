# Quickstart: Session Attendee Tracking

## Prerequisites
- Running ceol.io application
- PostgreSQL database with migrations applied
- Test user account with session admin privileges
- Test session with at least one session instance

## Setup Steps

### 1. Database Migration
```bash
# Apply the person_instrument table migration
psql -U $PGUSER -d $PGDATABASE -f schema/create_person_instrument_table.sql

# Verify table creation
psql -U $PGUSER -d $PGDATABASE -c "\\dt person_instrument"
```

### 2. Run Tests (TDD - should fail initially)
```bash
# Run integration tests for attendance API
pytest tests/integration/test_attendance_api.py -v

# Run functional tests for attendance flow
pytest tests/functional/test_attendance_flow.py -v
```

## Feature Walkthrough

### Scenario 1: View Session Attendance
1. **Login** as a session admin or regular attendee
2. **Navigate** to a session instance detail page
3. **Click** the "Attendees" tab
4. **Verify** you see:
   - List of regular attendees (green if attending, red if not, gray if unknown)
   - List of other attendees marked as present
   - Your own check-in status

### Scenario 2: Quick Check-in for Regulars
1. **As a regular attendee**, view the session instance
2. **Click** your name in the regulars list
3. **Select** "Check In" (one-click)
4. **Verify** your status changes to green (attending)

### Scenario 3: Add New Attendee
1. **As a session admin**, click "Add Attendee"
2. **Search** for existing person by typing their name
3. If not found, **click** "Add New Person"
4. **Enter**:
   - First Name: "John"
   - Last Name: "Smith"
   - Instruments: Select "Fiddle" and "Tin Whistle"
5. **Click** "Add and Check In"
6. **Verify** person appears in attendance list

### Scenario 4: Manage Person Details
1. **Click** on an attendee's name
2. **In the modal**, you can:
   - Edit their name
   - Update instruments
   - Change attendance status (Yes/Maybe/No)
   - Add a comment
   - Remove from this session
3. **Save** changes
4. **Verify** updates appear in the list

### Scenario 5: Search Previous Attendees
1. **Click** "Add Attendee"
2. **Type** partial name (e.g., "Joh")
3. **See** autocomplete suggestions of:
   - Previous attendees at this session
   - People from other sessions
4. **Select** a person from the list
5. **Verify** they're added with their instruments

## API Testing

### Test Attendance Retrieval
```bash
curl -X GET http://localhost:5000/api/session_instance/1/attendees \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

Expected Response:
```json
{
  "success": true,
  "data": {
    "regulars": [
      {
        "person_id": 1,
        "display_name": "John S.",
        "instruments": ["fiddle"],
        "attendance": "yes",
        "is_regular": true
      }
    ],
    "attendees": []
  }
}
```

### Test Check-in
```bash
curl -X POST http://localhost:5000/api/session_instance/1/attendees/checkin \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"person_id": 1, "attendance": "yes"}'
```

### Test Person Creation
```bash
curl -X POST http://localhost:5000/api/person \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "first_name": "Mary",
    "last_name": "O'\''Brien",
    "instruments": ["flute", "tin whistle"]
  }'
```

## Validation Checklist

### Functional Requirements
- [ ] FR-001: Can add people as attendees
- [ ] FR-002: Person info includes name and instruments
- [ ] FR-003: Can view all attendees for session
- [ ] FR-004: No duplicate attendance entries
- [ ] FR-005: Can search existing people
- [ ] FR-006: Can edit/remove attendees (with permissions)
- [ ] FR-007: Can view person's attendance history
- [ ] FR-008: Attendance linked to session instances

### Security & Privacy
- [ ] Only logged-in users can view attendance
- [ ] Only regulars/attendees can see attendance tab
- [ ] Only admins can edit other people's attendance
- [ ] Email/phone hidden from non-admins
- [ ] Self check-in works for any logged-in user

### UI/UX
- [ ] One-click check-in for regulars
- [ ] Search autocomplete works
- [ ] Names displayed as "First L."
- [ ] Instruments shown in small text
- [ ] Color coding for attendance status
- [ ] Mobile-responsive design

## Troubleshooting

### Issue: Cannot see Attendees tab
**Solution**: Ensure you're logged in and either a regular or admin for the session

### Issue: Search not finding people
**Solution**: Check that person exists in database and has attended sessions

### Issue: Cannot check in
**Solution**: Verify you have permission (self check-in or admin rights)

### Issue: Instruments not saving
**Solution**: Ensure instruments are from the approved list (see data-model.md)

## Performance Testing

```bash
# Load test with 100 concurrent check-ins
ab -n 100 -c 10 -p checkin.json -T application/json \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  http://localhost:5000/api/session_instance/1/attendees/checkin

# Verify response times < 200ms
```

## Rollback Procedure

If issues arise:
```bash
# Remove person_instrument table
psql -U $PGUSER -d $PGDATABASE -c "DROP TABLE IF EXISTS person_instrument CASCADE;"

# Revert API changes
git checkout main -- api_routes.py

# Clear browser cache
# Restart application
```