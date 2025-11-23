# Session Logging UI

Word-processor-style interface for logging tunes played during sessions.

## Overview

**Template**: `templates/session_instance_detail.html`
**Route**: `web_routes.py:session_instance_detail()`

## Features

Word-processor-like editing experience:

- **Drag & Drop**: Reorder tunes by dragging
- **Copy/Paste**: Duplicate tunes or move between sets
- **Undo/Redo**: Full operation history
- **Keyboard Shortcuts**: Ctrl+Z (undo), Ctrl+Y (redo), Ctrl+C/V (copy/paste)
- **Inline Editing**: Click to edit any field
- **Auto-save**: Configurable intervals (10s, 30s, 60s) with countdown timer
- **Tune Search**: Link tunes to thesession.org database
- **Set Management**: Group consecutive tunes
- **ABC Notation**: Display tune sheet music
- **Mobile Support**: Touch-friendly with swipe gestures

## Implementation

**JavaScript**: Modular architecture with 13 separate modules

**Modules** (`templates/session_instance_detail.html`):
- `autoSave.js` - Auto-save timer and state
- `stateManager.js` - Core data state
- `cursorManager.js` - Cursor positioning
- `pillRenderer.js` - DOM rendering
- `pillSelection.js` - Multi-select operations
- `pillInteraction.js` - Click/touch handling
- `dragDrop.js` - Drag and drop
- `textInput.js` - Text input buffer
- `modalManager.js` - Modal dialogs
- `keyboardHandler.js` - Keyboard shortcuts
- `undoRedoManager.js` - Operation history
- `clipboardManager.js` - Copy/paste
- `contextMenu.js` - Right-click menu

**State Management**:
- Client-side tune array
- Dirty flag for unsaved changes
- Undo stack with action records
- Auto-save with configurable intervals

## AJAX Operations

All operations via `api_routes.py` using session path pattern:

- **Save tunes**: POST `/api/sessions/<path>/<date_or_id>/save_tunes` - Bulk save session log
- **Get tune detail**: GET `/api/sessions/<path>/<date_or_id>/tunes/<tune_id>`
- **Update tune**: PUT `/api/sessions/<path>/<date_or_id>/tunes/<tune_id>`
- **Match tune**: POST `/api/sessions/<path>/<date_or_id>/match_tune` - Link to thesession.org
- **Update instance**: PUT `/api/sessions/<path>/<date_or_id>/update` - Update session instance metadata
- **Mark complete**: POST `/api/sessions/<path>/<date_or_id>/mark_complete`

**URL Pattern**: Uses session path + date/instance ID rather than direct session_instance_id

## Set Management

A **set** is a group of tunes played consecutively without pause.

### Data Model

- `session_instance_tune.continues_set` - Boolean indicating tune continues previous tune in a set
- `session_instance_tune.order_number` - Order within entire session

### UI Representation

Visual grouping with borders and labels, drag handle for entire set

### Operations

- **Create set**: Mark tune as `continues_set = true`
- **Break set**: Mark tune as `continues_set = false`
- **Add to set**: Drag tune into set visual grouping
- **Remove from set**: Drag out or toggle `continues_set`

## Permissions

- **View**: Any logged-in user with session access
- **Edit**: Session admins and system admins
- **Delete**: Session admins and system admins

**Check**: `web_routes.py:can_edit_session()`

## Tune Linking

Connect session log entries to canonical tune records.

### Search Flow

1. Type tune name in search field
2. GET `/api/tunes/search?q=<query>` (searches local + thesession.org)
3. Select from dropdown results
4. PUT to link tune, populating metadata

### Benefits

- Consistent naming across sessions
- Automatic metadata (type, key, popularity)
- Links to tune recordings/ABC notation

### Visual Indicator

- Linked: Blue link icon, clickable to thesession.org
- Unlinked: Gray text, search available

## ABC Notation Display

Sheet music rendering via ABC renderer service.

**Integration**:
- Fetch ABC notation from thesession.org for linked tunes
- Send to ABC renderer service (POST `/api/render`)
- Display returned PNG image in modal or inline

See [ABC Renderer](../services/abc-renderer.md) for service details.

## Responsive Design

Mobile-optimized interface:

- Touch-friendly buttons (44px minimum)
- Swipe gestures for mobile
- Collapsible metadata fields
- Simplified edit mode on small screens

## Related Specs

- [Session Model](../data/session-model.md) - Data structure
- [Tune Model](../data/tune-model.md) - Tune linking
- [AJAX Patterns](ajax.md) - API integration
- [Tune Services](../logic/tune-logic.md) - Search logic
