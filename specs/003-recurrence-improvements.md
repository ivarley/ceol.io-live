003 Recurrence Improvements

## Requirements

Recurrence Pattern Structure (session.recurrence) is a TEXT field storing a simple text description of the session's recurrence. This makes it hard to do things like automate current session status. For more robust scheduling, this should be formalized into a concrete structure. The structure should support recurrence such that you could pick any number of days of the week and have sessions at different times for different days, and also support only every N weeks, or patterns like "first tuesday of the month". For example these should all be valid:
- Every thursday from 7-10:30pm
- First and third sundays of the month from 4-8pm
- Tuesdays from 7-10pm and Sundays from 3-6pm
- Every other Thursday

To support "Tuesdays from 7-10pm and Sundays from 3-6pm", a session can have multiple separate recurrence rules.

The recurrence pattern is just for general automated recurrence, it doesn't have to handle exceptions because those are handled by updating individual session_instance records.

## Implementation Status

### ✅ Completed

1. **Core Utilities (`recurrence_utils.py`)**
   - `RecurrenceSchedule` class - handles individual schedule patterns
   - `SessionRecurrence` class - manages multiple schedules
   - `validate_recurrence_json()` - validates JSON format
   - `to_human_readable()` - converts JSON to readable text (e.g., "Thursdays from 7:00pm-10:30pm")
   - Support for:
     - Weekly patterns (every week, every N weeks)
     - Monthly nth weekday patterns (1st, 3rd, last, etc.)
     - Multiple schedules per session
     - Timezone-aware datetime calculations
   - All 41 unit tests passing

2. **JSON Schema (`schema/recurrence_schema.json`)**
   - Documented structure with examples
   - Two pattern types: `"weekly"` and `"monthly_nth_weekday"`
   - Weekday names as strings (lowercase)
   - Example:
     ```json
     {
       "schedules": [
         {
           "type": "weekly",
           "weekday": "thursday",
           "start_time": "19:00",
           "end_time": "22:30",
           "every_n_weeks": 1
         }
       ]
     }
     ```

3. **Database Migration (`schema/migrate_recurrence_to_json.py`)**
   - Converts existing freeform text recurrence to JSON
   - Attempts automatic conversion with validation
   - Flags unparseable patterns for manual review
   - Dry-run mode available

4. **API Validation (`api_routes.py`)**
   - Imported `validate_recurrence_json` and `to_human_readable`
   - Added validation in `update_session_ajax()` function
   - Returns friendly error messages for invalid patterns

### ✅ Completed (Continued)

5. **Display Human-Readable Recurrence**
   - Added `recurrence_readable` to session detail responses in `_get_session_data()` (web_routes.py:2412-2423)
   - Handles JSON recurrence patterns and legacy freeform text
   - Graceful error handling for invalid JSON

6. **UI: Read-Only View with Edit Button**
   - Location: Session admin page (`templates/session_admin.html:155-179`)
   - Displays human-readable text in bordered card: "Thursdays from 7:00pm-10:30pm"
   - Shows "Edit" button next to existing recurrence
   - Shows "Add Schedule" button if no recurrence
   - Click Edit/Add → swaps to structured form controls
   - Dark mode compatible styling (session_admin.html:495-510)

7. **UI: Structured Form Controls**
   - Location: `templates/session_admin.html:181-201` (HTML), 512-604 (CSS), 1168-1443 (JavaScript)
   - Features implemented:
     - "Add Schedule" button to create additional patterns
     - For each schedule:
       - Type dropdown (Weekly / Monthly Nth Weekday)
       - Weekday button selector (Mon-Sun)
       - For weekly: Frequency dropdown (every 1-4 weeks)
       - For monthly: Checkboxes for occurrences (1st, 2nd, 3rd, 4th, last)
       - Start time / End time pickers (24-hour HTML5 time inputs)
       - "Remove" button for each schedule
     - Preview section showing summary of schedules
     - Save/Cancel buttons
   - Dark mode compatible with proper color variables

8. **JavaScript for Mode Toggling**
   - Functions implemented in `templates/session_admin.html:1126-1443`:
     - `showRecurrenceEditMode()`: Loads existing JSON and creates form controls
     - `hideRecurrenceEditMode()`: Clears forms and returns to read-only view
     - `addScheduleForm(scheduleData)`: Dynamically creates schedule form HTML
     - `removeSchedule(scheduleId)`: Removes a schedule form
     - `selectWeekday()`: Weekday button toggle handler
     - `updateScheduleTypeUI()`: Shows/hides weekly vs monthly options
     - `collectSchedulesFromForm()`: Parses form into schedule objects
     - `updateRecurrencePreview()`: Live preview of schedule summary
     - `saveRecurrenceFromForm()`: Validates and saves JSON to backend
     - Client-side validation for required fields
     - Proper JSON generation with correct schema structure

9. **Auto-Create Next Week's Instances**
   - File: `session_instance_auto_create.py`
   - Function: `auto_create_next_week_instances(session_id)`:
     - Uses recurrence pattern to find occurrences in next 7 days (tomorrow through 7 days out)
     - Checks if session_instance already exists before creating
     - Creates missing instances only with proper start/end times
     - Comprehensive logging of all operations
     - Returns count and list of created dates
   - Function: `auto_create_instances_for_all_sessions()`:
     - Processes all active sessions with recurrence patterns
     - Can be run via cron for automated scheduling
     - Returns detailed statistics
   - Error handling and transaction management
   - Integration point ready for future scheduler

## Implementation Notes

- Recurrence field can be NULL (sessions without regular schedules are valid)
- All times stored in 24-hour format (HH:MM)
- Weekday names are lowercase strings
- Timezone handling uses session's timezone field
- Human-readable format uses 12-hour time with am/pm
- Multiple schedules display as: "Tuesdays from 7:00pm-10:00pm and Sundays from 3:00pm-6:00pm"
