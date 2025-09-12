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
- [ ] T024 [P] Create get_session_attendees() function in database.py
- [ ] T025 [P] Create check_in_person() function in database.py
- [ ] T026 [P] Create create_person_with_instruments() function in database.py
- [ ] T027 [P] Create get_person_instruments() function in database.py
- [ ] T028 [P] Create update_person_instruments() function in database.py
- [ ] T029 [P] Create remove_person_attendance() function in database.py
- [ ] T030 [P] Create search_session_people() function in database.py

### Permission Helpers
- [ ] T031 Create can_view_attendance() permission check in auth.py
- [ ] T032 Create can_manage_attendance() permission check in auth.py
- [ ] T033 Create is_session_regular() helper in auth.py

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

## Phase 3.5: Integration & Polish

### Data Display
- [ ] T045 Implement attendee name disambiguation logic in api_routes.py
- [ ] T046 Add instrument display formatting in templates
- [ ] T047 Implement alphabetical sorting with regular priority

### Performance
- [ ] T048 Add database indexes for attendance queries (if not existing)
- [ ] T049 Implement attendance data caching
- [ ] T050 Performance test attendance operations (<200ms)

### Documentation
- [ ] T051 [P] Update CLAUDE.md with attendance feature documentation
- [ ] T052 [P] Create attendance API documentation in docs/
- [ ] T053 [P] Update user guide with attendance instructions

### Validation
- [ ] T054 Run quickstart.md validation checklist
- [ ] T055 Test with multiple concurrent users
- [ ] T056 Verify backward compatibility with existing data

## Dependencies
- Database setup (T001-T003) must complete first
- All tests (T004-T016) must be written and failing before implementation (T017-T033)
- API endpoints (T017-T023) require database functions (T024-T030)
- Permission checks (T031-T033) needed for API endpoints
- Frontend (T034-T044) depends on API being complete
- Polish tasks (T045-T056) come last

## Parallel Execution Examples

### Parallel Test Creation (Phase 3.2)
```bash
# Launch T004-T010 together (contract tests):
Task: "Contract test GET /api/session_instance/{id}/attendees in tests/contract/test_get_attendees.py"
Task: "Contract test POST /api/session_instance/{id}/attendees/checkin in tests/contract/test_checkin_attendee.py"
Task: "Contract test POST /api/person in tests/contract/test_create_person.py"
Task: "Contract test GET /api/person/{id}/instruments in tests/contract/test_get_instruments.py"
Task: "Contract test PUT /api/person/{id}/instruments in tests/contract/test_update_instruments.py"
Task: "Contract test DELETE /api/session_instance/{id}/attendees/{person_id} in tests/contract/test_remove_attendee.py"
Task: "Contract test GET /api/session/{id}/people/search in tests/contract/test_search_people.py"

# Launch T011-T016 together (integration/functional tests):
Task: "Integration test for viewing session attendance with permissions in tests/integration/test_attendance_permissions.py"
Task: "Integration test for regular attendee self check-in in tests/integration/test_self_checkin.py"
Task: "Integration test for admin adding new person with instruments in tests/integration/test_add_new_person.py"
Task: "Integration test for searching and adding existing attendees in tests/integration/test_search_add_attendee.py"
Task: "End-to-end test for complete attendance workflow in tests/functional/test_attendance_flow.py"
Task: "End-to-end test for person management and instruments in tests/functional/test_person_management.py"
```

### Parallel Database Function Implementation (Phase 3.3)
```bash
# Launch T024-T030 together (database functions):
Task: "Create get_session_attendees() function in database.py"
Task: "Create check_in_person() function in database.py"
Task: "Create create_person_with_instruments() function in database.py"
Task: "Create get_person_instruments() function in database.py"
Task: "Create update_person_instruments() function in database.py"
Task: "Create remove_person_attendance() function in database.py"
Task: "Create search_session_people() function in database.py"
```

### Parallel CSS Development (Phase 3.4)
```bash
# Launch T042-T044 together (CSS files):
Task: "Create static/css/attendance.css for attendance-specific styles"
Task: "Add color coding for attendance status in static/css/attendance.css"
Task: "Add responsive styles for mobile attendance view in static/css/attendance.css"
```

### Parallel Documentation (Phase 3.5)
```bash
# Launch T051-T053 together (documentation):
Task: "Update CLAUDE.md with attendance feature documentation"
Task: "Create attendance API documentation in docs/"
Task: "Update user guide with attendance instructions"
```

## Notes
- **TDD Enforcement**: Tests MUST fail before implementation
- **API Consistency**: Follow existing Flask patterns in api_routes.py
- **Permission Checks**: Every endpoint must validate user permissions
- **History Tracking**: All database changes must use save_to_history()
- **Mobile First**: UI must be responsive and work on mobile devices
- **Backward Compatibility**: Don't break existing session functionality
- **Commit Strategy**: Commit after each completed task for easy rollback

## Validation Checklist
- [ ] All 6 API endpoints have contract tests
- [ ] Person_Instrument entity has migration
- [ ] All endpoints check permissions appropriately
- [ ] Attendance tab integrated into session detail pages
- [ ] Search functionality works for existing people
- [ ] Instruments can be managed per person
- [ ] Regular attendees can self check-in
- [ ] Name disambiguation implemented
- [ ] Performance targets met (<200ms)