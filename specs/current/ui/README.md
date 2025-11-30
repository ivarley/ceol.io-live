# UI Layer

Frontend presentation, user interactions, visual design.

## Overview

- **Framework**: Bootstrap 4.5.2, mobile-first responsive
- **Templates**: Jinja2 in `templates/`
- **Styling**: Custom CSS with CSS variables for theming
- **Interactions**: AJAX-heavy, minimal full page reloads

## Components

### [Templates & Pages](templates.md)
HTML structure, base layouts, page-specific templates

### [Session Logging UI](session-logging.md)
Word-processor-style tune logging with drag-and-drop, undo/redo, ABC notation display

### [Dark Mode & Theming](theming.md)
CSS custom properties, theme switching, FOUC prevention

### [AJAX Patterns](ajax.md)
Frontend-backend integration, error handling, loading states

### [UI Styles](styles.md)
Standard form controls, search boxes, CSS variables

## Key Locations

- `templates/base.html` - Base layout with navigation, theme switching
- `templates/session_instance_detail.html` - Word-processor-style session logging
- `templates/admin_*.html` - Admin interface pages
- `static/` - CSS and images
