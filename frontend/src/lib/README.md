# Component kit (spec 035, step 1b)

Shared Svelte 5 components for every migrated page. Import from `src/lib`:

```js
import { Sheet, Dialog, Popover, Card, Chip, Tabs, List, Pager, SearchField, toast } from '../lib/index.js'
```

## Conventions

- **Decisions are Dialogs; everything else is a Sheet.** A Sheet holds a task or
  scrollable detail (header/tabs/footer allowed); a Dialog holds one decision and
  never scrolls.
- **Dismiss:** commit a Sheet = "Done" (top-right, appears when `onDone` is
  passed). Abandon = "Cancel" (top-left), scrim tap, or Escape — all report
  through `onCancel`. Back within a Sheet = `‹ Label` via the `back` prop.
  Destructive Dialog confirms use an explicit verb ("Delete session"), never "OK".
  The one close glyph is `×` (U+00D7), class `kit-x`.
- **Nav:** browse as a **List** (↑/↓ + Enter, no "N of M"); inspect as a
  **Pager** (`‹ ›`, "N of M").
- **Responsive:** the device breakpoint is 768px, handled inside each component —
  no props switch layouts except Sheet's `desktop`.
- **CSS:** theme-aware via `static/css/theme.css` vars (with fallbacks), scoped
  styles, `kit-` class prefix. No global `body`/`html` rules; Sheet locks body
  scroll only while open (stacked sheets restore on the last close).
- Focus trap, Escape, click-outside, and aria wiring come from Bits UI.

## Components

### Sheet — task/detail container (bits-ui `Dialog`)
Full-screen under 768px; on desktop `desktop="center"` (default, centered
dialog) or `desktop="dock"` (right-docked pane).

| Prop | Default | |
|---|---|---|
| `open` | `false` | bindable |
| `title` | `''` | centered header title |
| `desktop` | `'center'` | `'center' \| 'dock'` |
| `back` | `null` | label → renders `‹ Label` instead of Cancel |
| `cancelLabel` | `'Cancel'` | |
| `onCancel` | noop | Cancel/back/scrim/Escape |
| `onDone` | `null` | commit; Done button renders only when passed |
| `doneLabel` | `'Done'` | |
| `children` | — | body snippet (scrolls) |
| `footer` | `null` | optional footer snippet |

### Dialog — one decision (bits-ui `AlertDialog`)
Never scrolls; outside clicks are ignored, Escape = Cancel.

| Prop | Default | |
|---|---|---|
| `open` | `false` | bindable |
| `title` | `''` | |
| `description` | `''` | plain-text body; or pass `children` for markup |
| `confirmLabel` | `'Confirm'` | pass an explicit verb, never "OK" |
| `cancelLabel` | `'Cancel'` | |
| `destructive` | `false` | red confirm button |
| `onConfirm` / `onCancel` | noop | |

### Popover — anchored panel (bits-ui `Popover`)
| Prop | Default | |
|---|---|---|
| `open` | `false` | bindable |
| `side` / `align` | `'bottom'` / `'start'` | placement |
| `triggerClass` | `''` | extra class on the trigger button |
| `trigger` | — | snippet: trigger button content |
| `children` | — | snippet: panel content |

### toast(message, type) — `toast.js`
`type: 'success' | 'error' | 'info'`. Delegates to the site-wide
`window.showMessage` when present (base.html pages); otherwise renders its own
top-center stack (`--z-toast`), auto-dismissing after 3s.

### Card
Surface with border + `--r` radius. Props: `hover` (shadow on hover),
`children`; extra attributes (`class`, `onclick`, …) pass through.

### Chip
Pill for statuses/filters/instruments. Props: `label` (or `children`),
`active`, `dismissible` (× button → `onDismiss`), `onclick` (makes the body a
button), `variant`: `'default' | 'primary' | 'success' | 'warning' | 'danger'`.

### Tabs — responsive tabs (bits-ui `Tabs`)
Desktop: horizontal tab buttons. Under 768px: the same panes behind a
`<select>`. Both controls always render; CSS picks one.

| Prop | Default | |
|---|---|---|
| `tabs` | `[]` | `[{ id, label }]` |
| `value` | first tab id | bindable active id |
| `onValueChange` | noop | |
| `children` | — | snippet receiving the active id — branch on it for panes |

```svelte
<Tabs {tabs} bind:value>
  {#snippet children(active)}
    {#if active === 'tunes'}…{:else if active === 'stats'}…{/if}
  {/snippet}
</Tabs>
```

### List — browse mode
Vertical results; ↑/↓ move the active row, Enter/click selects. No "N of M".

| Prop | Default | |
|---|---|---|
| `items` | `[]` | |
| `active` | `-1` | bindable active index |
| `onSelect` | noop | `(item)` |
| `row` | — | snippet `(item, isActive)`; wrapper `li` carries active styling |

### Pager — inspect mode
`‹ ›` + "N of M"; buttons disable at the bounds.

| Prop | Default | |
|---|---|---|
| `index` | `0` | bindable, 0-based |
| `count` | `0` | |
| `onPrev` / `onNext` | `null` | omit to let the pager step `bind:index` itself |
| `label` | `'result'` | aria context ("Previous result") |

### SearchField
Debounced input with clear-×; Escape clears. Generic — no tune-search logic.

| Prop | Default | |
|---|---|---|
| `value` | `''` | bindable |
| `placeholder` | `'Search…'` | |
| `debounce` | `300` | ms idle before `onSearch` |
| `onSearch` | noop | `(query)`; fires immediately with `''` on clear |
