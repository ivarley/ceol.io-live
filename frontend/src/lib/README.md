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

### Chip — small pill/badge
THE badge — status badges, type pills, filter pills, count badges, role and
instrument markers all run on it. Clickable (whole chip is a real `<button>`,
padding included), dismissible (the ONE sanctioned × glyph, U+00D7), or plain.

| Prop | Default | |
|---|---|---|
| `label` / `children` | — | text or richer content |
| `active` | `false` | |
| `dismissible` | `false` | renders the × (`onDismiss`) |
| `onclick` | — | whole-chip button (with `dismissible`, the body and × are separate buttons) |
| `variant` | `'default'` | `'primary' | 'success' | 'warning' | 'danger'` (styled mode) |
| `styled` | `true` | `false` = structure only; skin comes from the page via `chipClass` |
| `chipClass` / `xClass` | — | legacy skin + e2e/CSS hook passthrough |
| `...rest` | — | `title`, `style`, `data-*` … pass to the chip |


### Tabs — responsive tabs (bits-ui `Tabs`)
Desktop: horizontal tab buttons. Under 768px: the same panes behind a
`<select>`. Both controls always render; CSS picks one. THE tab engine —
every tabbed surface (person page, session page, session admin, the tune
sheet) uses it.

| Prop | Default | |
|---|---|---|
| `tabs` | `[]` | `[{ id, label, href?, domId? }]` — `href` per tab in navigate mode; `domId` = trigger DOM id (for `aria-labelledby` panes) |
| `value` | first tab id | bindable active id |
| `onValueChange` | noop | host hook: URL sync, lazy loads |
| `navigate` | `false` | tabs are routes: real `<a href>` on desktop, the select navigates |
| `onNavigate` | `location.href` | navigate-mode seam (tests) |
| `styled` | `true` | `false` = structural responsive rule only; skin comes from the page via the class props |
| `listId`/`listClass`/`tabClass`/`selectId`/`selectClass`/`paneClass` | — | legacy skin + e2e/CSS hook passthrough; triggers always carry `data-tab` and an `active` class |
| `selectLabel` | `'Section'` | aria-label for the mobile select |
| `children` | — | snippet receiving the active id — branch on it, or keep pane components mounted with an `active` flag when their state must survive switching |

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

### SearchField — debounced search input
THE search input — every page filter box runs on it. Debounced
`onSearch(query)`, clear-× when there's text, **Escape clears** (and stops
there; an empty box lets Escape propagate to a host Sheet/overlay), **Enter
flushes immediately**. No tune/thesession logic — hosts own min-chars rules,
casing, and what "search" means.

| Prop | Default | |
|---|---|---|
| `value` | `''` | bindable raw text |
| `placeholder` | `'Search…'` | |
| `debounce` | `300` | ms of idle before `onSearch` fires |
| `onSearch` | noop | settled-text callback (also fired by Enter/clear) |
| `styled` | `true` | `false` = behavior only; skin comes from the page's legacy input class |
| `inputClass`/`wrapperClass` | — | legacy skin + e2e/CSS hook passthrough |
| `...rest` | — | `id`, `title`, `autocomplete`… pass to the `<input>` |

`bind:this` exposes `focus()`. For instant client-side filters, just
`bind:value` and derive — the debounce only gates `onSearch`.


### Seg — segmented control
THE seg — the status 3-ways (tune sheet + add pane), the sort/status filter
groups, and the history-scope toggles. CONTROLLED: the host owns `value`; Seg
paints the active option and reports clicks. `onSelect` fires on EVERY option
click — including the active one — because some hosts toggle-off on that
(per-instrument status).

| Prop | Default | |
|---|---|---|
| `options` | `[]` | `[{ id, label }]` |
| `value` | — | active option id (host-owned; not self-mutating) |
| `onSelect` | noop | fires on every option click |
| `idAttr` | `'data-seg'` | attribute name the option id is stamped under (`data-status`, `data-sort`…) |
| `secondary` | `null` | option id marked `active-secondary` (two-level sort) |
| `styled` | `true` | `false` = structure only; skin via `segClass`/`optClass` |
| `segClass`/`optClass` | — | legacy skin + e2e/CSS hook passthrough; options always carry an `active` class |
| `...rest` | — | `role`, `aria-label`… pass to the container |
