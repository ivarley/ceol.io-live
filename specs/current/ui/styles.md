# UI Styles

Standard styling for common UI components across the application.

## Form Controls

### Text Input (`.form-control`)

The standard text input style used throughout the application, including search boxes.

```css
.form-control {
    display: block;
    width: 100%;
    padding: 0.375rem 0.75rem;
    font-size: 1rem;
    font-weight: 400;
    line-height: 1.5;
    color: var(--text-color);
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 0.25rem;
    transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.form-control:focus {
    color: var(--text-color);
    background-color: var(--bg-color);
    border-color: var(--primary);
    outline: 0;
    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}
```

**Properties:**
- **Padding**: `0.375rem 0.75rem` (6px 12px) - comfortable click/tap target
- **Font size**: `1rem` (16px) - prevents iOS zoom on focus
- **Border**: 1px solid using `--border-color` CSS variable
- **Border radius**: `0.25rem` (4px) - subtle rounded corners
- **Focus state**: Primary color border with subtle glow

**Usage:**
```html
<input type="text" class="form-control" placeholder="Search...">
```

### Search Box in Toolbar

For admin pages with a search box and action button on the same row:

```html
<div class="[page]-toolbar">
    <input type="text" class="form-control [page]-search-input" placeholder="Search...">
    <a href="..." class="btn btn-primary btn-add-[item]">Add [Item]</a>
</div>
```

```css
.[page]-toolbar {
    display: flex;
    gap: 1rem;
    align-items: center;
    margin-bottom: 1rem;
}

.[page]-search-input {
    max-width: 400px;
}

.btn-add-[item] {
    margin-left: auto;
}

/* Mobile: keep on same line, search shrinks */
@media (max-width: 768px) {
    .[page]-toolbar {
        gap: 0.5rem;
    }

    .[page]-search-input {
        flex: 1;
        min-width: 0;
        max-width: none;
    }

    .btn-add-[item] {
        flex-shrink: 0;
        white-space: nowrap;
    }
}
```

## CSS Variables

All form controls should use these CSS variables for theming support:

| Variable | Purpose |
|----------|---------|
| `--text-color` | Input text color |
| `--bg-color` | Input background |
| `--border-color` | Input border |
| `--primary` | Focus border color |
| `--hover-bg` | Hover background for interactive elements |

## Examples

- `admin_sessions_list.html` - Reference implementation of search toolbar
- `admin_people.html` - People search with same pattern
- `admin_tunes.html` - Tunes search with same pattern
