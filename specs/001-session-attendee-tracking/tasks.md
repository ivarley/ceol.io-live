# Tasks: Session Attendee Tracking

**Input**: Design documents from `/specs/001-session-attendee-tracking/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- Flask monolith structure (existing application)
- Main app files at repository root
- Templates in `templates/`, static files in `static/`
- Tests in `tests/` with subdirectories for unit/integration/functional

## Phase 3.1: Database Setup
- [x] T001 Create person_instrument table migration in schema/create_person_instrument_table.sql
- [x] T002 Create person_instrument history table migration in schema/create_person_instrument_history_table.sql
- [x] T003 Apply database migrations to test database

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests
- [x] T004 [P] Contract test GET /api/session_instance/{id}/attendees in tests/contract/test_get_attendees.py
- [x] T005 [P] Contract test POST /api/session_instance/{id}/attendees/checkin in tests/contract/test_checkin_attendee.py
- [x] T006 [P] Contract test POST /api/person in tests/contract/test_create_person.py
- [x] T007 [P] Contract test GET /api/person/{id}/instruments in tests/contract/test_get_instruments.py
- [x] T008 [P] Contract test PUT /api/person/{id}/instruments in tests/contract/test_update_instruments.py
- [x] T009 [P] Contract test DELETE /api/session_instance/{id}/attendees/{person_id} in tests/contract/test_remove_attendee.py
- [x] T010 [P] Contract test GET /api/session/{id}/people/search in tests/contract/test_search_people.py

### Integration Tests
- [x] T011 [P] Integration test for viewing session attendance with permissions in tests/integration/test_attendance_permissions.py
- [x] T012 [P] Integration test for regular attendee self check-in in tests/integration/test_self_checkin.py
- [x] T013 [P] Integration test for admin adding new person with instruments in tests/integration/test_add_new_person.py
- [x] T014 [P] Integration test for searching and adding existing attendees in tests/integration/test_search_add_attendee.py

### Functional Tests
- [x] T015 [P] End-to-end test for complete attendance workflow in tests/functional/test_attendance_flow.py
- [x] T016 [P] End-to-end test for person management and instruments in tests/functional/test_person_management.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### API Endpoints
- [x] T017 Implement GET /api/session_instance/{id}/attendees endpoint in api_routes.py
- [x] T018 Implement POST /api/session_instance/{id}/attendees/checkin endpoint in api_routes.py
- [x] T019 Implement POST /api/person endpoint in api_routes.py
- [x] T020 Implement GET /api/person/{id}/instruments endpoint in api_routes.py
- [x] T021 Implement PUT /api/person/{id}/instruments endpoint in api_routes.py
- [x] T022 Implement DELETE /api/session_instance/{id}/attendees/{person_id} endpoint in api_routes.py
- [x] T023 Implement GET /api/session/{id}/people/search endpoint in api_routes.py

### TO23.1 - Extend permission to system admins

We missed an important criterion in our plan, which is that in addition to being a regular or admin for the session in question, you can also do anything if you're a global system admin (user_account.is_system_admin). Update the spec, plan, tasks, tests, and code accordingly for this change.
- [x] T023.1 - Include system admins as having full permission on these capabilities

### Database Functions
- [x] T024 [P] Create get_session_attendees() function in database.py
- [x] T025 [P] Create check_in_person() function in database.py
- [x] T026 [P] Create create_person_with_instruments() function in database.py
- [x] T027 [P] Create get_person_instruments() function in database.py
- [x] T028 [P] Create update_person_instruments() function in database.py
- [x] T029 [P] Create remove_person_attendance() function in database.py
- [x] T030 [P] Create search_session_people() function in database.py

### Permission Helpers
- [x] T031 Create can_view_attendance() permission check in auth.py
- [x] T032 Create can_manage_attendance() permission check in auth.py
- [x] T033 Create is_session_regular() helper in auth.py

## Phase 3.4: Frontend Implementation

### Templates
- [ ] T034 Create templates/partials/attendance_tab.html for attendance UI component
- [ ] T035 Create templates/modals/person_edit.html for person edit modal
- [ ] T036 Update templates/session_instance_detail.html to add attendance tab
- [ ] T037 Update templates/session_instance_detail_beta.html to add attendance tab

### JavaScript
- [ ] T038 Create static/js/attendance.js for attendance UI interactions
- [ ] T039 Add check-in functionality to static/js/attendance.js
- [ ] T040 Add person search autocomplete to static/js/attendance.js
- [ ] T041 Add instrument management UI to static/js/attendance.js

### CSS
- [ ] T042 [P] Create static/css/attendance.css for attendance-specific styles
- [ ] T043 [P] Add color coding for attendance status in static/css/attendance.css
- [ ] T044 [P] Add responsive styles for mobile attendance view in static/css/attendance.css

Now some additional tasks to get it to where I want it, in individual sections.

### T045 - Session Peson Records

Adding someone as attending a session (i.e. inserting in session_instance_person) should simultaneously add a record to session_person for them if it doesn't already exist, with is_regular defaulted to false. (If it already exists, no change is needed.)

If the last record for a person is deleted from session_instance_person (i.e. if no records remain in session_instance_person with that session_id and person_id) then they should be deleted from session_person for that session_id as well. (They may well exist for other sessions; this only affects the current session.)

Add tests for these cases first, and show them failing, and then implement the required changes and show the tests passing.

### T046 - Link To Edit Session person

For system and session admins, show an edit icon on the right edge of the person row in the attendance tab that takes you to the session admin page for that person (admin/sessions/{path}/players/{person_id}). This replaces the two non-functional buttons to the right of the yes/maybe/no buttons that aren't displaying correctly anyway. When you arrive at this page from this route, instead of:

"Player details for {session name}. ← Back to players list"

you should see:

"Player details for {session name}. ← Back to session on {session instance date}"

and it should return you to the attendance tab of the session instance detail page. 

### T047 - Always show regulars

The attendance list should always show the session regulars in the list, and if there's no record in the session_instance_person table for them they should show as not attending.
