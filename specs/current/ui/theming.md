# Dark Mode & Theming

CSS custom properties system for light/dark theme switching.

## Implementation

### Theme Switching

**Storage**: `localStorage.getItem('theme')` - "light" or "dark"

**Application**: `[data-theme="dark"]` attribute on `<html>` element

**Toggle**: JavaScript in `templates/base.html` inline script

### CSS Variables

Defined in `templates/base.html` `<style>` block.

**Light Theme** (default):
```css
:root {
  --bg-color: #ffffff;
  --text-color: #333333;
  --primary-color: #4a90e2;
  --secondary-text: #666666;
  --border-color: #dee2e6;
  --input-bg: #ffffff;
  --hover-bg: #f8f9fa;
  --link-color: #007bff;
  --table-header-bg: #f8f9fa;
}
```

**Dark Theme**:
```css
[data-theme="dark"] {
  --bg-color: #1e1e1e;
  --text-color: #e0e0e0;
  --primary-color: #6db3f2;
  --secondary-text: #a0a0a0;
  --border-color: #404040;
  --input-bg: #2d2d2d;
  --hover-bg: #2d2d2d;
  --link-color: #6db3f2;
  --table-header-bg: #2d2d2d;
}
```

### Logo Switching

**Light**: `static/logo1.png`
**Dark**: `static/logo1-dark-transparent.png`

**Implementation**: JavaScript updates `<img src>` on theme change.

## FOUC Prevention

Flash of Unstyled Content prevented by inline script in `<head>`:

```javascript
// Runs before page render
(function() {
  const theme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
})();
```

**Location**: `templates/base.html` - before any CSS loads

## Theme Toggle UI

**Location**: Navigation bar in `base.html`

**Elements**:
- Moon icon (☾) for dark mode activation
- Sun icon (☀) for light mode activation
- Toggle updates localStorage and `data-theme` attribute
- Logo src updated dynamically

## Usage in Components

All colors reference CSS variables:

```css
.my-component {
  background-color: var(--bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}
```

**Never hard-code colors** - always use variables.

## Browser Support

- Modern browsers with CSS custom properties support
- Fallback: Light theme for browsers without localStorage

## Related Specs

- [Templates](templates.md) - Base layout structure
- [AJAX Patterns](ajax.md) - JavaScript patterns
