# AJAX Patterns and API Integration

Frontend-backend communication using fetch API for dynamic updates.

## Standard Pattern

**Basic Fetch**:
```javascript
fetch('/api/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => {
  if (data.success) showMessage(data.message, 'success');
  else showMessage(data.error, 'error');
})
.catch(error => showMessage('An error occurred', 'error'));
```

**With Loading State**:
```javascript
button.disabled = true;
button.textContent = 'Saving...';
// ... fetch request ...
.finally(() => {
  button.disabled = false;
  button.textContent = 'Save';
});
```

## Key Operations

**Save Tunes**: `POST /api/sessions/<path>/<date_or_id>/save_tunes` - Auto-save (3s debounce) | `session_instance_detail.html`

**Check-In**: `POST /api/session_instance/<id>/attendees/checkin` - Button disabled, spinner | `partials/attendance_tab.html`

**Tune Search**: `GET /api/tunes/search?q=<query>` - 300ms debounce, dropdown | `components/tune_search_input.html`

**Link Tune**: `POST /api/sessions/<path>/<date_or_id>/match_tune` - Modal overlay, link icon update

## Loading States

**Buttons**: Disable + text change ("Saving...")

**Spinner**: `<i class="fas fa-spinner fa-spin"></i>`

**Ellipsis**: CSS animation | `session_instance_detail.html:16-32`

**Overlay**: Full-page for long operations

## Error Handling

**Response**: `{"success": false, "error": "Message"}`

**Client**: Check `data.success`, show `data.error` via `showMessage()`

**Network**: Catch block, generic message

**Status**: 200 (OK), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500 (Server)

## Debouncing

**Search**: 300ms delay
```javascript
let searchTimeout;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => performSearch(), 300);
});
```

**Auto-Save**: 3000ms delay
```javascript
let saveTimeout;
function scheduleAutoSave() {
  clearTimeout(saveTimeout);
  saveTimeout = setTimeout(saveTunes, 3000);
}
```

## Patterns

**Optimistic Update**: Update UI first, revert on error

**Form Submit**: Intercept with `preventDefault()`, fetch with JSON

**File Upload**: FormData (don't set Content-Type)

**Modal Loading**: Show "Loading...", fetch data, render

## API Response Conventions

**Success**: `{"success": true, "message": "...", "data": {...}}`

**Error**: `{"success": false, "error": "...", "code": "..."}`

**List**: `{"success": true, "items": [...], "total": 42, "page": 1, "per_page": 20}`

## Key Endpoints

**Routes**: `api_routes.py` (JSON APIs), `web_routes.py` (HTML pages)

**Common**: Save tunes, check-in, tune search, tune linking, session management
