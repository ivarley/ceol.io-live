# Dark Mode & Theming

CSS custom properties system for light/dark theme switching.

## Implementation

### Theme Switching

**Storage**: `localStorage.getItem('theme')` - "light" or "dark"

**Application**: `[data-theme="dark"]` attribute on `<html>` element

**Toggle**: JavaScript in `templates/base.html` inline script

### CSS Variables

Defined in `templates/base.html` `<style>` block.

**Light Theme**:
```css
:root {
  --bg-color: #fff;
  --text-color: #252930;
  --primary-color: #00a1e0;
  --secondary-text: #adb4c0;
  --border-color: #ddd;
  --input-bg: #fff;
  --hover-bg: #f8f9fa;
  --link-color: #00a1e0;
  --link-hover-color: #005b7f;
  --table-header-bg: #f5f6f8;
  --header-bg: #fff;
  --dropdown-bg: #fff;
  --dropdown-border: #ddd;
  --dropdown-shadow: rgba(0,0,0,0.15);
}
```

**Dark Theme** (default):
```css
[data-theme="dark"] {
  --bg-color: #1a1a1a;
  --text-color: #e0e0e0;
  --primary-color: #4da6ff;
  --secondary-text: #888;
  --border-color: #444;
  --input-bg: #2d2d2d;
  --hover-bg: #3d3d3d;
  --link-color: #4da6ff;
  --link-hover-color: #80c0ff;
  --table-header-bg: #2d2d2d;
  --header-bg: #2d2d2d;
  --dropdown-bg: #2d2d2d;
  --dropdown-border: #444;
  --dropdown-shadow: rgba(0,0,0,0.3);
}
```

### Logo Switching

**Light**: `static/images/logo2-1.png`
**Dark**: `static/images/logo2-dark-1.png`

**Implementation**: JavaScript updates `<img src>` on theme change (in `base.html` head script).

## FOUC Prevention

Flash of Unstyled Content prevented by inline script in `<head>`:

```javascript
// Runs before page render
(function() {
  const theme = localStorage.getItem('theme') || 'dark';  // Default: dark
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

## Mobile/Responsive Standards

**Breakpoints** (Bootstrap 4.5):
- `max-width: 767.98px` - Mobile devices
- `max-width: 1199.98px` - Tablets and small desktops

**Padding Standards**:
- Desktop: `2rem` (32px) for content areas like `.docs-article`
- Mobile (≤767.98px): `1rem` (16px) for content areas

**Form Inputs**:
All form inputs must use CSS variables for dark mode compatibility:
```css
.form-control {
  background-color: var(--input-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}
```

## Related Specs

- [Templates](templates.md) - Base layout structure
- [AJAX Patterns](ajax.md) - JavaScript patterns
