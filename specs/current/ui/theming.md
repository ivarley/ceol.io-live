# Theming (Dark-Only)

The app is dark-only. There is no light mode, no theme toggle, no `data-theme`
attribute, and no `localStorage['theme']` — all of that was removed when light
mode was ripped out. Theming is a single set of CSS custom properties.

## CSS Variables

Defined in `static/css/theme.css` (the `:root` block at the top of the file —
NOT in `templates/base.html`, which only loads the stylesheet). This is the
single token source: colors, plus the radius (`--r-sm/--r/--r-lg/--r-pill`),
shadow (`--shadow-sm/-md/-lg`), scrim (`--scrim`), spacing (`--sp-1`…`--sp-8`),
motion (`--dur-quick/--dur/--ease`), and z-index (`--z-*`) scales, and the one
global `@keyframes spin`.

**Palette** (excerpt). The `:root` block is GENERATED from `design/tokens.json` by
`scripts/build_tokens.py` (spec 052 §B6) — edit the JSON, not the CSS:
```css
:root {
  --bg-color: #1a1a1a;
  --text-color: #e0e0e0;
  --primary: #65b464;            /* accent TEXT, links, icons */
  --primary-fill: #4a8049;       /* accent surfaces behind white text */
  --primary-fill-hover: #437342;
  --secondary-text: #888;
  --text-muted: #888;
  --border-color: #444;
  --input-bg: #2d2d2d;
  --hover-bg: #3d3d3d;
  --link-color: #65b464;
  --link-hover-color: #92ca91;
  --table-header-bg: #3d3d3d;
  --header-bg: #2d2d2d;
  --dropdown-bg: #2d2d2d;
  --dropdown-border: #444;
  --dropdown-shadow: rgba(0,0,0,0.3);
}
```

### The accent is two colours, not one (spec 052 §B10)

`--primary` is the accent as TEXT. `--primary-fill` is the accent as a SURFACE —
a selected filter, a tune-type chip, a primary button, a checked box's
`accent-color`. They are not interchangeable, and the reason is contrast: a green
light enough to read as text on the dark page (6.85:1) is too light to sit behind
white text (2.54:1, under AA), and the logo green that carries white text properly
(4.69:1) is too dark to read as text (3.71:1).

The rule: **`color:` takes `--primary`; `background`, `accent-color`, and a border
that outlines one of those backgrounds take `--primary-fill`.** It is enforced by
`tests/unit/test_design_tokens_052.py`, which greps the stylesheets for an accent
background on the text token.

`--primary-fill` is the logo green exactly — `static/images/logo3-1.png` is one
flat `#4a8049`. `--primary-dark` is NOT the fill's hover: it is lighter than the
fill, so it would brighten on hover. Use `--primary-fill-hover`.

Note: `--primary-color` was removed in spec 035 — `--primary` is the one name.

## The `:root <selector>` pattern

`theme.css` (and a few page CSS files) contain component overrides written as
`:root .card { … }`. The `:root` prefix is deliberate: these rules were
previously `[data-theme="dark"] .card { … }` and the prefix preserves their
specificity (0,1,1+), so they still beat single-class component rules. Don't
"simplify" them to bare selectors — that changes the cascade.

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

The live-logging shell (`templates/live_logging.html` + `frontend/src/app.css`)
deliberately does not load `theme.css`; it carries its own copy of the dark
palette variables so the bundle is self-contained.

## Mobile/Responsive Standards

**Breakpoints** (Bootstrap 4.5):
- `max-width: 767.98px` - Mobile devices
- `max-width: 1199.98px` - Tablets and small desktops

**Padding Standards**:
- Desktop: `2rem` (32px) for content areas like `.docs-article`
- Mobile (≤767.98px): `1rem` (16px) for content areas

**Form Inputs**:
All form inputs must use CSS variables:
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
