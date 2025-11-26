# Person Tune Authentication & Authorization - Requirements Mapping

This document maps the implementation in `person_tune_auth.py` to the requirements from Requirement 7.

## Requirement 7.1: Authentication Verification
**Requirement:** WHEN a user accesses any personal tune functionality THEN the system SHALL verify the user is authenticated

**Implementation:**
- `person_tune_login_required` decorator checks `current_user.is_authenticated`
- Returns 401 Unauthorized with JSON error if not authenticated
- Can be applied to any personal tune endpoint

**Tests:**
- `test_authenticated_user_can_access` - verifies authenticated users can access
- `test_unauthenticated_user_denied` - verifies 401 response for unauthenticated users

---

## Requirement 7.2: User Data Isolation
**Requirement:** WHEN displaying personal tune data THEN the system SHALL only show tunes belonging to the current logged-in user

**Implementation:**
- `get_user_person_id()` function retrieves current user's person_id
- `filter_person_tunes_by_user()` function returns filtering parameters for queries
- `can_access_person_tunes(person_id)` checks if user can access specific person's tunes
- All functions ensure users only see their own data (unless admin)

**Tests:**
- `test_returns_person_id_for_authenticated_user` - verifies person_id retrieval
- `test_regular_user_gets_own_person_id` - verifies filtering by user's own ID
- `test_user_can_access_own_tunes` - verifies access to own tunes
- `test_user_cannot_access_other_tunes` - verifies no access to other users' tunes

---

## Requirement 7.3: Ownership Verification for Modifications
**Requirement:** WHEN a user attempts to modify tune data THEN the system SHALL verify they own that person_tune record or are a system admin

**Implementation:**
- `verify_person_tune_ownership(person_tune_id, user)` function checks ownership
- Queries database to verify person_id matches current user
- `require_person_tune_ownership` decorator enforces ownership on endpoints
- System admins bypass ownership checks

**Tests:**
- `test_owner_can_access_own_tune` - verifies owners can modify their tunes
- `test_non_owner_denied_access` - verifies non-owners cannot modify
- `test_owner_can_access_endpoint` - verifies decorator allows owners
- `test_non_owner_receives_403` - verifies 403 for non-owners

---

## Requirement 7.4: Redirect Unauthenticated Users
**Requirement:** IF an unauthenticated user tries to access personal tune features THEN the system SHALL redirect to the login page

**Implementation:**
- `person_tune_login_required` decorator returns 401 for API endpoints
- Note: For web routes (not API), Flask-Login's `@login_required` handles redirects
- API endpoints return JSON error (401) instead of redirecting

**Tests:**
- `test_unauthenticated_user_denied` - verifies 401 response for API endpoints

---

## Requirement 7.5: Forbidden Access to Other Users' Data
**Requirement:** IF a user tries to access another user's tune data THEN the system SHALL return a 403 Forbidden error

**Implementation:**
- `verify_person_tune_ownership()` returns error dict when ownership check fails
- `require_person_tune_ownership` decorator returns 403 status code
- Error message: "You do not have permission to access this tune"

**Tests:**
- `test_non_owner_denied_access` - verifies ownership check fails for non-owners
- `test_non_owner_receives_403` - verifies 403 status code returned
- `test_user_cannot_access_other_tunes` - verifies access control

---

## Requirement 7.6: System Admin Access
**Requirement:** WHEN a system admin accesses tune data THEN the system SHALL allow viewing and modifying any user's tune collection for support purposes

**Implementation:**
- `is_system_admin()` function checks if user is admin
- `verify_person_tune_ownership()` returns True immediately for admins
- `can_access_person_tunes()` returns True for admins regardless of person_id
- `filter_person_tunes_by_user()` allows admins to specify person_id parameter

**Tests:**
- `test_admin_can_access_any_tune` - verifies admins bypass ownership checks
- `test_returns_true_for_admin` - verifies admin detection
- `test_admin_can_access_any_tunes` - verifies admin access to any tunes
- `test_admin_with_person_id_param_gets_specified_id` - verifies admin filtering

---

## Additional Features

### Error Handling
- Non-existent tunes return appropriate error messages
- Invalid person_tune_id returns 400 Bad Request
- Database connection properly closed in all cases

### Helper Functions
- `get_user_person_id()` - Safe retrieval of current user's person_id
- `is_system_admin()` - Check admin status
- `can_access_person_tunes(person_id)` - Check access permissions
- `filter_person_tunes_by_user(query_params)` - Get filtering parameters

---

## Test Coverage Summary

Total Tests: 24
- Authentication: 2 tests
- Ownership Verification: 4 tests  
- Decorator Authorization: 3 tests
- Helper Functions: 15 tests

All tests passing ✓

## Usage Examples

### Protecting an API Endpoint
```python
from person_tune_auth import person_tune_login_required

@app.route('/api/my-tunes')
@person_tune_login_required
def get_my_tunes():
    # User is guaranteed to be authenticated
    person_id = get_user_person_id()
    # ... fetch tunes for person_id
```

### Protecting Modification Endpoints
```python
from person_tune_auth import person_tune_login_required, require_person_tune_ownership

@app.route('/api/my-tunes/<int:person_tune_id>', methods=['PUT'])
@person_tune_login_required
@require_person_tune_ownership
def update_tune_status(person_tune_id):
    # User is authenticated AND owns this person_tune record
    # ... update the tune
```

### Filtering Queries by User
```python
from person_tune_auth import filter_person_tunes_by_user

@app.route('/api/my-tunes')
@person_tune_login_required
def get_my_tunes():
    filters = filter_person_tunes_by_user(request.args)
    person_id = filters['person_id']
    # Query only returns tunes for this person_id
```
