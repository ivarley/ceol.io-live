# Template Structure and Base Layouts

Flask/Jinja2 template hierarchy and shared components.

## Base Template

**File**: `templates/base.html:1-840`

**Provides**:
- HTML structure, header, navigation
- Theme system (dark/light mode)
- Flash messages (toasts)
- In-session badge
- PWA features (service worker, pull-to-refresh)

**Blocks**:
```jinja2
{% block title %}      <!-- Page title -->
{% block description %} <!-- Meta description -->
{% block extra_css %}  <!-- Page CSS -->
{% block content %}    <!-- Main content -->
{% block extra_js %}   <!-- Page JavaScript -->
```

**Usage**: `{% extends "base.html" %}`

## Header

**Logo**: `base.html:317` - Responsive, theme-aware

**In Session Badge**: `base.html:326-336`, `:644-831` - Green dot when at active session, popup on hover/click

**Hamburger Menu**: `base.html:339-369` - Profile, Admin, My Tunes, Dark Mode, Log Out (authenticated) | Log In, Session Logs (unauthenticated)

## Theme

**Default**: Dark mode (localStorage 'theme')

**Toggle**: `toggleDarkMode()` | `base.html:409-418`

**FOUC Prevention**: Inline script | `base.html:48-73`

**CSS**: `static/css/theme.css` - Variables for dark/light

**See**: [Dark Mode & Theming](theming.md)

## Messages

**Server**: Flask `flash()` → toasts

**Client**: `showMessage(message, type)`

**Display**: Top-center, 4s auto-hide

**Code**: `base.html:109-146`, `:457-525`

## Page Templates

**Sessions**: `sessions.html`, `session_detail.html`, `session_instance_detail.html`

**Tunes**: `my_tunes.html`, `common_tunes.html`, `tune_detail_modal.html`

**Auth**: `auth/login.html`, `auth/register.html`, `auth/reset_password.html`

**Admin**: `admin_tabs.html`, `admin_sessions_list.html`, `admin_people.html`, `admin_tunes.html`

## Partials & Components

**Attendance Tab**: `partials/attendance_tab.html` - Reusable attendance UI

**Tune Search**: `components/tune_search_input.html` - Autocomplete search component

**Modals**: `modals/person_edit.html` - Person edit dialog

**Usage**: `{% include 'partials/attendance_tab.html' %}`

## Conventions

**URL Generation**: Always use `url_for()`, never hardcode
```jinja2
<a href="{{ url_for('session_detail', path=session.path) }}">Session</a>
<img src="{{ url_for('static', filename='images/logo.png') }}">
```

**Global Context**: `current_user`, `request`, `session` (Flask session)

**Common Variables**: `session` (session record), `session_instance`, `tunes`, `attendees`, `is_admin`

**Date Formatting**: `{{ session_instance.date.strftime('%A, %B %d, %Y') }}`

## Responsive & Layout

**Framework**: Bootstrap 4.5 (xs/sm/md/lg/xl breakpoints)

**Z-Index**: `static/css/z-index-layers.css` - Content (1) < Modals (1050) < Header (2000) < Toasts (9999)

**Critical**: Header z-index above modal overlay (keeps hamburger clickable)

## PWA

**Service Worker**: `static/service-worker.js` | `base.html:528-555`

**Manifest**: `static/manifest.json`

**Pull-to-Refresh**: PWA-only | `base.html:557-642`

## JavaScript

**Inline**: Base template (theme, menu, badge)

**Page**: `{% block extra_js %}`

**External**: `static/js/` (e.g., `utils/unaccent.js`)
