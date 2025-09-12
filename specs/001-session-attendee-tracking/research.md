# Research: Session Attendee Tracking

## Executive Summary
Research confirms that the ceol.io codebase already has robust infrastructure for implementing session attendee tracking. The database schema exists with proper tables and relationships, authentication/authorization is mature, and UI/API patterns are well-established. The feature can be implemented by extending existing patterns rather than creating new architecture.

## Key Findings

### 1. Database Architecture
**Decision**: Use existing schema with minor additions  
**Rationale**: 
- `person`, `session_instance`, and `session_instance_person` tables already exist
- Proper foreign keys and constraints in place
- History tracking system already captures all changes
**Alternatives Considered**:
- Separate attendee service: Rejected - unnecessary complexity
- NoSQL for attendance: Rejected - loses relational integrity

### 2. Authentication & Authorization
**Decision**: Extend existing Flask-Login system  
**Rationale**:
- Role-based access control already implemented
- Session admins and regulars have appropriate permission levels
- Secure token management in place
**Alternatives Considered**:
- OAuth integration: Rejected - overkill for internal feature
- Separate auth for attendance: Rejected - fragments user experience

### 3. UI Implementation
**Decision**: Add attendance tab to existing session detail pages  
**Rationale**:
- Session detail pages are the natural location for attendance
- Tab pattern already used for organizing session information
- Mobile-responsive Bootstrap framework in place
**Alternatives Considered**:
- Separate attendance page: Rejected - disrupts workflow
- Modal-only interface: Rejected - limited functionality

### 4. API Design
**Decision**: RESTful endpoints following existing patterns  
**Rationale**:
- Consistent with current API structure
- JSON response format already standardized
- Error handling patterns established
**Alternatives Considered**:
- GraphQL: Rejected - inconsistent with existing APIs
- WebSocket for real-time: Rejected - unnecessary complexity

### 5. Testing Strategy
**Decision**: pytest with existing fixture infrastructure  
**Rationale**:
- Comprehensive test fixtures already available
- Database transaction rollback keeps tests isolated
- Mock infrastructure for external services exists
**Alternatives Considered**:
- Separate test framework: Rejected - fragments testing
- E2E only: Rejected - violates TDD principles

## Technical Discoveries

### Existing Infrastructure
1. **Person Management**: Complete CRUD operations already implemented
2. **Session Relationships**: `session_person` table tracks regulars/admins
3. **History Tracking**: `save_to_history()` function captures all changes
4. **Permission System**: Decorators like `@api_login_required` enforce access
5. **UI Components**: Admin interfaces demonstrate patterns for person management

### Schema Analysis
```sql
-- Existing tables support requirements
person (person_id, first_name, last_name, email)
session_instance (session_instance_id, session_id, date)
session_instance_person (session_instance_id, person_id, attendance, comment)
session_person (session_id, person_id, is_regular, is_admin)

-- Only addition needed
person_instrument (person_id, instrument)
```

### API Patterns
```python
# Standard response format
{"success": bool, "data": {}, "error": "message"}

# Authentication decorator
@api_login_required

# Database transaction pattern
conn = get_db_connection()
try:
    # operations
    conn.commit()
except:
    conn.rollback()
```

## Implementation Recommendations

### Phase 1 Priorities
1. Create `person_instrument` table
2. Extend person API with instrument management
3. Add attendance tab to session detail page
4. Implement check-in API endpoints

### Security Considerations
1. Validate user permissions for attendance viewing
2. Ensure regulars can only check themselves in
3. Admins can manage all attendance
4. Sanitize person data in public views

### Performance Optimizations
1. Index `session_instance_person` on session_instance_id
2. Batch attendance updates
3. Lazy load attendance data

### UI/UX Guidelines
1. One-click check-in for regulars (green button)
2. Search-as-you-type for adding attendees
3. Instrument icons for visual recognition
4. Mobile-first responsive design

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Duplicate person entries | Data integrity | Implement fuzzy matching, admin merge tool |
| Performance with large sessions | Slow UI | Pagination, virtual scrolling |
| Privacy concerns | Legal/trust | Role-based viewing, data minimization |
| Backwards compatibility | Breaking changes | Version APIs, migration scripts |

## Conclusion
The ceol.io codebase is well-prepared for session attendee tracking. Implementation should follow existing patterns, leverage current infrastructure, and maintain consistency with the established architecture. No significant technical blockers identified.