# Implementation Plan: Session Attendee Tracking

**Branch**: `001-session-attendee-tracking` | **Date**: 2025-09-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-session-attendee-tracking/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Implement session attendee tracking to allow organizers and regular attendees to track who attends music sessions. The system will enable one-click check-in for regulars, search/add previous attendees, and add new people with their instruments. The implementation leverages existing database schema (person, session_instance_person tables) and extends current Flask API patterns with new attendance management endpoints and UI components.

## Technical Context
**Language/Version**: Python 3.11 (Flask 2.3.x)  
**Primary Dependencies**: Flask, Flask-Login, psycopg2, Jinja2, Bootstrap 4.5.2  
**Storage**: PostgreSQL with existing schema  
**Testing**: pytest with comprehensive fixtures  
**Target Platform**: Web application (mobile-responsive)  
**Project Type**: web - Flask backend with Jinja2 templates  
**Performance Goals**: <200ms response time for attendance operations  
**Constraints**: Must maintain backward compatibility with existing session data  
**Scale/Scope**: ~100 concurrent users, ~1000 sessions, ~10000 people

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 2 (backend API, frontend UI)
- Using framework directly? YES (Flask, Jinja2, no wrappers)
- Single data model? YES (existing schema, no DTOs)
- Avoiding patterns? YES (direct DB queries, no repository pattern)

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? YES
- Git commits show tests before implementation? YES
- Order: Contract→Integration→E2E→Unit strictly followed? YES
- Real dependencies used? YES (test database)
- Integration tests for: new APIs, UI changes, attendance workflows? YES
- FORBIDDEN: Implementation before test, skipping RED phase

**Observability**:
- Structured logging included? YES (existing patterns)
- Frontend logs → backend? YES (via existing error handlers)
- Error context sufficient? YES

**Versioning**:
- Version number assigned? N/A (monolithic app)
- BUILD increments on every change? N/A
- Breaking changes handled? YES (backward compatible)

## Project Structure

### Documentation (this feature)
```
specs/001-session-attendee-tracking/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Existing Flask application structure
/
├── api_routes.py        # New attendance API endpoints
├── web_routes.py        # New attendance page routes
├── templates/
│   ├── session_instance_detail.html  # Add attendance tab
│   ├── partials/
│   │   └── attendance_tab.html       # New attendance UI component
│   └── modals/
│       └── person_edit.html          # Person edit modal
├── static/
│   ├── css/
│   │   └── attendance.css            # Attendance-specific styles
│   └── js/
│       └── attendance.js             # Attendance UI logic
├── schema/
│   └── (existing, already updated)
└── tests/
    ├── integration/
    │   └── test_attendance_api.py    # API tests
    └── functional/
        └── test_attendance_flow.py    # E2E tests
```

**Structure Decision**: Extending existing Flask monolith (matches current architecture)

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - ✓ Database schema exists (person, session_instance_person)
   - ✓ Authentication/authorization patterns established
   - ✓ UI patterns exist (session detail pages, admin interfaces)
   - ✓ API patterns established (JSON responses, decorators)
   - ✓ Testing framework in place (pytest, fixtures)

2. **Generate and dispatch research agents**:
   ```
   ✓ Completed - research found:
   - Existing person and attendance tables
   - Flask-Login authentication with role-based access
   - Bootstrap UI with dark mode support
   - Comprehensive test infrastructure
   ```

3. **Consolidate findings** in `research.md`:
   - Decision: Extend existing schema and patterns
   - Rationale: Infrastructure already supports requirements
   - Alternatives considered: Separate microservice (rejected - overkill)

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Person (existing): first_name, last_name, email
   - Person_Instrument (new): person_id, instrument
   - Session_Instance_Person (existing): attendance status
   - Validation: Unique person per session instance
   - State transitions: unknown → yes/maybe/no

2. **Generate API contracts** from functional requirements:
   - GET /api/session_instance/{id}/attendees
   - POST /api/session_instance/{id}/attendees/checkin
   - PUT /api/person/{id}/instruments
   - DELETE /api/session_instance/{id}/attendees/{person_id}
   - Output OpenAPI schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - test_get_attendance_list.py
   - test_checkin_person.py
   - test_update_instruments.py
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Regular user one-click check-in
   - Search and add previous attendee
   - Add new person with instruments
   - View attendance with proper permissions

5. **Update agent file incrementally**:
   - Update CLAUDE.md with attendance feature details
   - Add new API endpoints documentation
   - Update testing section with new test files

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, CLAUDE.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Create person_instrument table migration [P]
- Add attendance API endpoints (4 tasks) [P]
- Create attendance UI components (3 tasks)
- Add permission checks for attendance viewing
- Create integration tests (4 test scenarios)
- Update session detail page with attendance tab
- Add instrument management UI
- Create attendance summary views

**Ordering Strategy**:
- Database changes first (migrations)
- API endpoints before UI
- Tests before implementation (TDD)
- Permission checks early

**Estimated Output**: 20-25 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following TDD principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*No violations - following existing patterns*

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*