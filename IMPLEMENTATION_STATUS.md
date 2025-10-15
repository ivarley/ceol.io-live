# Person Tune Customization Features - Implementation Status

## Overview
This document tracks the implementation of three new customization features for personal tune collections:

1. **Setting ID**: Store a thesession.org setting ID to link to a specific version/arrangement of a tune
2. **Name Alias**: Store a personal name/alias that the user calls the tune (e.g., "The Grumpy Old Man" instead of "The Little Beggarman")
3. **Heard Count**: Track how many times a tune has been heard before learning it (already existed, but needs UI enhancements)

## Work Completed ✅

### Backend Implementation (100% Complete)

#### 1. Database Schema (`schema/add_person_tune_setting_and_name.sql`)
- ✅ Added `setting_id INTEGER` column to `person_tune` table
- ✅ Added `name_alias VARCHAR(255)` column to `person_tune` table
- ✅ Updated `person_tune_history` table with same columns for audit trail
- ✅ Added column comments for documentation

**To apply migration:**
```bash
# Test database
PGDATABASE=ceol_test PGUSER=test_user PGPASSWORD=test_password psql -f schema/add_person_tune_setting_and_name.sql

# Production database
PGHOST=dpg-d1vqi3vdiees73bur7vg-a.oregon-postgres.render.com PGDATABASE=ceol_db PGUSER=ceol_user PGPASSWORD=smILztVeN8LKhzyUxvMJuE3aPyPjXt3j psql -f schema/add_person_tune_setting_and_name.sql
```

#### 2. PersonTune Model (`models/person_tune.py`)
- ✅ Added `setting_id` and `name_alias` parameters to `__init__()` method
- ✅ Updated all database queries (INSERT, UPDATE, SELECT) to include new fields
- ✅ Updated `to_dict()` method to include new fields in JSON responses
- ✅ Updated `__repr__()` and `__eq__()` methods for proper object representation
- ✅ Updated history logging to track changes to new fields

#### 3. PersonTune Service (`services/person_tune_service.py`)
- ✅ Updated `update_person_tune()` to accept `setting_id` and `name_alias` parameters
- ✅ Updated `get_person_tunes_with_details()` query to SELECT new columns
- ✅ Updated response building to include new fields in returned data

#### 4. API Routes (`api_person_tune_routes.py`)
- ✅ Created unified endpoint: `PUT /api/my-tunes/<person_tune_id>`
  - Accepts any combination of fields: `learn_status`, `notes`, `setting_id`, `name_alias` (all optional)
  - All fields treated equally - no artificial distinction between "regular" and "custom" fields
  - Validates setting_id is a positive integer if provided
  - Empty string values are converted to null to clear fields
  - Returns updated person_tune with tune details
- ✅ Updated `_build_person_tune_response()` helper function
  - Now includes `setting_id` in thesession.org URL as query parameter
  - Format: `https://thesession.org/tunes/{tune_id}?setting={setting_id}`
  - Falls back to base URL if no setting_id exists

#### 5. Route Registration (`app.py`)
- ✅ Imported `update_person_tune` function
- ✅ Registered unified route: `/api/my-tunes/<int:person_tune_id>` [PUT]
- ✅ Removed old separate endpoints for `/status`, `/notes`, `/custom`

#### 6. Existing Features (Already Working)
- ✅ Heard count field `heard_before_learning_count` already exists in database
- ✅ API endpoint `POST /api/my-tunes/<person_tune_id>/heard` already implemented
- ✅ Desktop UI already has "+" button to increment heard count

## Work Remaining ⏳

### Frontend/UI Implementation (0% Complete)

All remaining work is in the UI layer, specifically in `/templates/my_tunes.html`.

#### 1. Setting ID Field in Modal
**Location:** Tune detail modal (around line 1862 in my_tunes.html)

**Requirements:**
- Add an input field below the tune title in the modal
- Label: "Setting ID" or "TheSession.org Setting"
- Input type: text (to allow pasting URLs)
- Features needed:
  1. **URL parsing**: When user pastes a thesession.org URL containing `?setting=123` or `&setting=123`, extract just the numeric ID
     - Regex pattern: `[?&]setting=(\d+)`
  2. **Direct entry**: Allow user to type just the number (e.g., "123")
  3. **Clear button**: Allow user to clear/remove the setting ID
  4. **Save to API**: Call `PUT /api/my-tunes/{person_tune_id}` with `{setting_id: value}`
  5. **Display current value**: Show existing setting_id when modal opens (from `tune.setting_id`)

**API Integration:**
```javascript
// Save setting ID
fetch(`/api/my-tunes/${personTuneId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setting_id: extractedSettingId })
})
```

**URL Parsing Example:**
```javascript
function extractSettingId(input) {
    // If it's already a number, return it
    if (/^\d+$/.test(input.trim())) {
        return parseInt(input.trim());
    }

    // Try to extract from URL
    const match = input.match(/[?&]setting=(\d+)/);
    return match ? parseInt(match[1]) : null;
}
```

#### 2. Name Alias Field in Modal
**Location:** Tune detail modal, triggered by clicking tune title

**Requirements:**
- Make the tune title clickable in modal (around line 1863)
- On click, show an editable field below the title
- Label: "I call this:"
- Input type: text
- Pre-populate with `tune.name_alias` if exists, otherwise `tune.tune_name`
- Features needed:
  1. **Inline editing**: Click title → shows text input
  2. **Save to API**: Call `PUT /api/my-tunes/{person_tune_id}` with `{name_alias: value}`
  3. **Clear option**: Allow user to remove alias (revert to standard name)
  4. **Update display**: After saving, update the title display to show the alias

**Future enhancement (not required now):**
- Autocomplete from other known tune names (would need new API endpoint)

**API Integration:**
```javascript
// Save name alias
fetch(`/api/my-tunes/${personTuneId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name_alias: newAlias })
})
```

#### 3. Update TheSession.org Links
**Status:** Mostly automatic

The backend already generates URLs with `?setting={setting_id}` parameter when a setting_id exists. The frontend should automatically receive these in API responses.

**Verify locations where thesession.org links appear:**
1. Tune card "View on TheSession.org" button (line ~1679)
2. Modal link icon (line ~1857)
3. Both should use `tune.thesession_url` from API response

**If manual updates needed:**
```javascript
// Build URL with setting ID
const baseUrl = `https://thesession.org/tunes/${tune.tune_id}`;
const url = tune.setting_id ? `${baseUrl}?setting=${tune.setting_id}` : baseUrl;
```

#### 4. Swipe Gesture for Heard Count (Mobile)
**Location:** Tune cards in main list (mobile view)

**Requirements:**
- Add swipe-right gesture detection on tune cards
- When swiped right, reveal a "+" button
- Button calls existing API: `POST /api/my-tunes/{person_tune_id}/heard`
- Only works for tunes with `learn_status === 'want to learn'`

**Implementation approach:**
```javascript
// Add to tune card rendering or event handlers
let touchStartX = 0;
let touchCurrentX = 0;

tuneCard.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
});

tuneCard.addEventListener('touchmove', (e) => {
    touchCurrentX = e.touches[0].clientX;
    const deltaX = touchCurrentX - touchStartX;

    if (deltaX > 50) {
        // Show "+" button
        showHeardButton(tuneCard);
    }
});

tuneCard.addEventListener('touchend', (e) => {
    // If button was revealed and tapped, increment count
    // Otherwise, hide the button
});
```

**Note:** The desktop UI already has the "+" button working (around line 1669). This is just adding the swipe gesture for mobile convenience.

## API Endpoints Reference

### Available Endpoints
- `GET /api/my-tunes` - Get user's tune collection
- `GET /api/my-tunes/<person_tune_id>` - Get single tune details with all fields
- `PUT /api/my-tunes/<person_tune_id>` - **Update any person_tune fields** ✨
  - Request body (all optional): `{ "learn_status": "learning", "notes": "text", "setting_id": 123, "name_alias": "My Name" }`
  - Only provided fields will be updated
  - All fields have equal standing - no concept of "custom" vs "regular" fields
  - Pass empty string or null to clear a field
- `POST /api/my-tunes/<person_tune_id>/heard` - Increment heard count ✅ (already working)

## Data Flow

### Current Modal Data Loading
```javascript
// When modal opens (line ~1761)
fetch(`/api/my-tunes/${personTuneId}`)
    .then(response => response.json())
    .then(data => {
        const tune = data.person_tune;
        // tune.setting_id - available but not displayed
        // tune.name_alias - available but not displayed
        // tune.thesession_url - already includes ?setting= param if applicable
    });
```

### Saving Fields
```javascript
// Update any person_tune fields - all fields treated equally
async function updatePersonTune(personTuneId, updates) {
    const response = await fetch(`/api/my-tunes/${personTuneId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)  // e.g., { setting_id: 123, name_alias: "My Name" }
    });

    const data = await response.json();
    if (data.success) {
        // Update local tune data
        // Refresh modal display
        // Update tune list if needed
    }
}

// Examples:
// Update just setting_id: updatePersonTune(id, { setting_id: 123 })
// Update just name_alias: updatePersonTune(id, { name_alias: "My Name" })
// Update multiple fields: updatePersonTune(id, { setting_id: 123, notes: "Great tune!" })
```

## Testing Checklist

### Backend Testing (via API)
- [ ] Run database migration on test database
- [ ] Test `PUT /api/my-tunes/<id>` with setting_id only
- [ ] Test `PUT /api/my-tunes/<id>` with name_alias only
- [ ] Test `PUT /api/my-tunes/<id>` with multiple fields (e.g., setting_id + notes)
- [ ] Test clearing fields by passing null/empty string
- [ ] Verify thesession.org URLs include ?setting= parameter in GET responses

### UI Testing
- [ ] Setting ID field displays correctly in modal
- [ ] Setting ID can be saved and retrieved
- [ ] URL parsing extracts setting_id from thesession.org URLs
- [ ] Direct numeric entry works for setting_id
- [ ] Tune title is clickable and shows name alias field
- [ ] Name alias can be saved and displayed
- [ ] TheSession.org links include setting parameter when set
- [ ] Swipe-right gesture reveals heard count button (mobile)
- [ ] Heard count increments correctly via swipe gesture
- [ ] All changes persist after page reload

## File Locations

### Modified Backend Files
- `schema/add_person_tune_setting_and_name.sql` - Database schema (new fields added)
- `models/person_tune.py` - Data model (17 occurrences of `name_alias` added)
- `services/person_tune_service.py` - Business logic (8 occurrences updated)
- `api_person_tune_routes.py` - API endpoints (refactored to single unified endpoint)
  - Removed: `update_tune_status()`, `update_tune_notes()`, `update_tune_custom_fields()`
  - Added: `update_person_tune()` (handles all fields)
- `app.py` - Route registration (consolidated from 3 routes to 1 unified route)

### Files Needing UI Updates
- `templates/my_tunes.html` - Main tune list and modal (ALL remaining work)
  - Modal structure: Lines ~1046-1053
  - Modal display functions: Lines ~1761-2073
  - Tune card rendering: Lines ~1663-1707

## Notes

### Design Decisions
1. **Field name**: Changed from `custom_name` to `name_alias` for clarity
2. **API architecture**: Unified PUT endpoint treats all fields equally - no artificial hierarchy
   - Previous approach had separate `/status`, `/notes`, `/custom` endpoints
   - Now: single `PUT /api/my-tunes/<id>` accepts any combination of fields
   - This reflects the reality that all fields are just attributes on the same object
3. **URL format**: Setting ID added as query parameter (standard thesession.org format)
4. **Null handling**: Empty strings converted to null to properly clear fields
5. **Validation**: Setting ID must be positive integer; name_alias has no restrictions

### Known Limitations
1. Name alias autocomplete not implemented (future enhancement)
2. No UI to show when a tune has been heard X times in sessions (could derive from session_instance_tune)
3. Swipe gesture might conflict with existing modal swipe-to-close gesture (test needed)

### Future Enhancements (Out of Scope)
- Autocomplete name alias from known tune name variations
- Auto-populate setting_id from most commonly used setting in user's sessions
- Bulk update setting_id for multiple tunes
- Show "last heard at [session name] on [date]" in modal
- Auto-increment heard count when tune is played at a session you attended

## Getting Started (Next Session)

To continue implementation:

1. **Apply database migration** (if not done)
2. **Start with Setting ID field** (simplest UI addition)
   - Add input field to modal HTML structure
   - Implement URL parsing logic
   - Wire up save functionality
   - Test thoroughly
3. **Add Name Alias field** (requires click handler on title)
4. **Verify URL updates** (should be automatic)
5. **Implement swipe gesture** (most complex - touch event handling)

Focus on one feature at a time and test each thoroughly before moving to the next.
