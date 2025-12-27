# Spec: Admin Tune Migration Screen

## Overview

When thesession.org merges two tunes, the old tune ID becomes a redirect to the new one. This feature provides an admin screen to migrate all references from an old tune ID to a new one in our system, preserving data integrity and preventing the old ID from being re-added.

## User Story

As a system admin, I want to migrate tune references when thesession.org merges tunes, so that our data stays consistent with the canonical tune database.

---

## Schema Changes

### New Column: `tune.redirect_to_tune_id`

```sql
ALTER TABLE tune ADD COLUMN redirect_to_tune_id INTEGER REFERENCES tune(tune_id);
```

**Purpose:** When set, indicates this tune has been merged into another. The old tune record is preserved for audit purposes but should not be used for new entries.

**Constraint:** Cannot redirect to a tune that is itself a redirect (no chains).

---

## Migration Logic

When migrating tune `OLD_ID` → `NEW_ID`:

### 1. Validation
- Both tune IDs must exist in `tune` table
- `OLD_ID` must not already be a redirect
- `NEW_ID` must not be a redirect (prevent chains)
- `OLD_ID` != `NEW_ID`

### 2. Preview Phase
Count affected records in each table:
- `tune_setting` rows with `tune_id = OLD_ID`
- `session_tune` rows with `tune_id = OLD_ID`
- `session_tune_alias` rows with `tune_id = OLD_ID`
- `session_instance_tune` rows with `tune_id = OLD_ID`
- `person_tune` rows with `tune_id = OLD_ID`

### 3. Execution Phase (in transaction)

**Order matters due to foreign key constraints:**

1. **session_instance_tune** - UPDATE `tune_id` to `NEW_ID`
   - Handle potential duplicates: if same session_instance already has `NEW_ID`, keep existing

2. **session_tune_alias** - UPDATE `tune_id` to `NEW_ID`
   - Handle potential duplicates: if (session_id, tune_id) already exists for `NEW_ID`, delete old alias

3. **session_tune** - UPDATE or merge
   - If `(session_id, NEW_ID)` already exists: merge settings, delete old row
   - If not: UPDATE `tune_id` to `NEW_ID`

4. **person_tune** - UPDATE or merge
   - If `(person_id, NEW_ID)` already exists: keep existing, delete old row
   - If not: UPDATE `tune_id` to `NEW_ID`

5. **tune_setting** - UPDATE `setting_id` assignments
   - UPDATE `tune_id` to `NEW_ID` (setting_id is unique globally from thesession.org, no conflicts expected)

6. **tune** - Mark old tune as redirect
   - UPDATE `redirect_to_tune_id = NEW_ID` for `OLD_ID`

### 4. History Tracking
All updates trigger existing history table triggers, providing full audit trail.

---

## API Endpoint

### `POST /api/admin/tunes/migrate`

**Request:**
```json
{
  "old_tune_id": 1234,
  "new_tune_id": 5678
}
```

**Response (Preview mode - no `confirm` flag):**
```json
{
  "success": true,
  "preview": true,
  "old_tune": {
    "tune_id": 1234,
    "name": "The Old Tune Name",
    "type": "Reel"
  },
  "new_tune": {
    "tune_id": 5678,
    "name": "The Canonical Tune Name",
    "type": "Reel"
  },
  "affected_records": {
    "tune_settings": 3,
    "session_tunes": 12,
    "session_tune_aliases": 2,
    "session_instance_tunes": 47,
    "person_tunes": 8
  },
  "warnings": [
    "2 session_tune records will be merged (session already has new tune)",
    "1 person_tune record will be merged"
  ]
}
```

**Request (Execute mode):**
```json
{
  "old_tune_id": 1234,
  "new_tune_id": 5678,
  "confirm": true
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Migrated tune 1234 → 5678",
  "migrated_records": {
    "tune_settings": 3,
    "session_tunes": 10,
    "session_tunes_merged": 2,
    "session_tune_aliases": 2,
    "session_instance_tunes": 47,
    "person_tunes": 7,
    "person_tunes_merged": 1
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Tune 1234 is already a redirect to tune 9999"
}
```

---

## UI Design

### Location
`/admin/tunes/migrate` - New page accessible from Admin > Tunes tab

### Navigation
Add "Migrate Tunes" link/button to admin tunes page header area

### Page Layout

```
Admin >> Tunes >> Migrate Tune

┌─────────────────────────────────────────────────────────────┐
│  Migrate Tune                                               │
│                                                             │
│  Use this tool when thesession.org has merged two tunes.    │
│  All references to the old tune will be updated to point    │
│  to the new tune.                                           │
│                                                             │
│  Old Tune ID: [________] (tune being retired)               │
│  New Tune ID: [________] (tune to migrate to)               │
│                                                             │
│  [Preview Migration]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Preview Results Display

```
┌─────────────────────────────────────────────────────────────┐
│  Migration Preview                                          │
│                                                             │
│  Old Tune: #1234 "The Maid Behind the Bar" (Reel)          │
│  New Tune: #5678 "Maid Behind the Bar" (Reel)              │
│                                                             │
│  Records to migrate:                                        │
│  ┌─────────────────────────────────────┬─────────┐         │
│  │ Table                               │ Count   │         │
│  ├─────────────────────────────────────┼─────────┤         │
│  │ Tune Settings (ABC notation)        │ 3       │         │
│  │ Session Tunes                       │ 12      │         │
│  │ Session Tune Aliases                │ 2       │         │
│  │ Session Log Entries                 │ 47      │         │
│  │ Personal Tune Collections           │ 8       │         │
│  └─────────────────────────────────────┴─────────┘         │
│                                                             │
│  ⚠ Warnings:                                                │
│  • 2 session_tune records will be merged                    │
│  • 1 person_tune record will be merged                      │
│                                                             │
│  [Cancel]  [Confirm Migration]                              │
└─────────────────────────────────────────────────────────────┘
```

### Success State

```
┌─────────────────────────────────────────────────────────────┐
│  ✓ Migration Complete                                       │
│                                                             │
│  Tune #1234 has been migrated to #5678                     │
│                                                             │
│  • 3 tune settings migrated                                 │
│  • 10 session tunes updated, 2 merged                       │
│  • 2 session tune aliases updated                           │
│  • 47 session log entries updated                           │
│  • 7 personal tune records updated, 1 merged                │
│                                                             │
│  The old tune has been marked as a redirect and will not   │
│  appear in searches or be re-added to the system.          │
│                                                             │
│  [Migrate Another]  [Back to Tunes]                         │
└─────────────────────────────────────────────────────────────┘
```

---

## System-Wide Redirect Handling

### Prevent Adding Redirected Tunes

Modify tune creation/linking logic to check for redirects:

**In `link_tune_ajax()` (api_routes.py):**
```python
# After fetching tune, check if it's a redirect
if tune.redirect_to_tune_id:
    return jsonify({
        "success": False,
        "error": f"Tune {tune_id} has been merged into tune {tune.redirect_to_tune_id}",
        "redirect_to": tune.redirect_to_tune_id
    })
```

### Exclude Redirects from Search

**In tune search queries:**
```sql
WHERE redirect_to_tune_id IS NULL
```

### Admin Tunes List

Show redirected tunes with indicator badge, or filter them out by default with toggle to show.

---

## Files to Modify

| File | Changes |
|------|---------|
| `schema/` | New migration SQL for `redirect_to_tune_id` column |
| `api_routes.py` | New `/api/admin/tunes/migrate` endpoint |
| `api_routes.py` | Update `link_tune_ajax()` to check for redirects |
| `web_routes.py` | New `/admin/tunes/migrate` route |
| `templates/admin_tunes.html` | Add "Migrate Tunes" button |
| `templates/admin_tune_migrate.html` | New template for migration UI |
| `database.py` or new service | Migration logic functions |

---

## Testing Considerations

1. **Normal migration** - Both tunes exist, no conflicts
2. **Duplicate session_tune** - Session already has both old and new tune
3. **Duplicate person_tune** - Person already has both tunes
4. **Invalid IDs** - Non-existent tune IDs
5. **Chain prevention** - Attempting to redirect to a redirect
6. **Self-redirect** - OLD_ID == NEW_ID
7. **Already redirected** - Old tune already has redirect_to_tune_id set
8. **Rollback on error** - Transaction fails partway through
