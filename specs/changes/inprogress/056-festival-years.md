# 056: Festival years

**Date:** 2026-10-04
**Status:** OCTOBER PATH BUILT (2026-10-05): copy endpoint and form, window rule and
picker, year switcher, help — see "As built" at the end. Not built: the new-festival
mode of the add-session sheet (the server side exists, spec 055 phase 1), the
directory's one-row-per-festival, the native surface. Depends on [055 Places and session paths](055-places-and-session-paths.md):
the `place` table, the two-segment path rule, the resolution order and the `path_redirect`
table are defined there. Decided in a design interview on 2026-10-04.

## Why

`https://ceol.io/sessions/oflahertys/2025` is the O'Flaherty's Irish Music Retreat — last
year's. The 2026 retreat is weeks away and there is no way to make its session short of
re-typing every field, no URL that means "the festival" rather than one year of it, and
nothing that would send a visitor to the right year. The seed data says it outright:
"an annually-repeating festival is a separate session row per year"; spec 047 lists the
rest under "not done".

Spec 004 made `session_type = 'festival'` and it reaches exactly these places: the public
page's tab order and labels (Sessions first, grouped by day), instance labels appending
the room, the logger's naming help, the Add Instance modal's "Name" field, the home strip
allowing several same-day instances, the dropped no-overlap index, and the admin help
text. Nothing ties one year to the next.

This spec reifies a festival in the smallest form that works: a `place` row of
`kind = 'festival'` whose years are the sessions under its slug. Everything cross-year —
"which tunes have been played at every O'Flaherty's" — is then a query over those
sessions and needs no further schema. Festival-level fields (website, description) are
columns on that row when a page needs them; none yet.

## The model

```
dallas (place)                         ← created later by curation, not by the migration
└── midlothian (place, parent dallas)
    ├── oflahertys/2025  ← session, type festival, place_id = midlothian
    └── oflahertys/2026
oflahertys (place, kind festival, parent midlothian)
└── oflahertys/2025, oflahertys/2026   ← the same sessions, grouped by path prefix
```

- A **festival** is a `place` row: `kind = 'festival'`, `slug` = the path prefix, `name`
  = the festival's name without a year ("O'Flaherty's Irish Music Retreat"), `parent` =
  the town it happens in. `area` and `country` NULL.
- A **year** is a session: `session_type = 'festival'`, path `{festival-slug}/{yyyy}`,
  `place_id` = its town, `initiation_date`/`termination_date` = first and last day,
  `recurrence` NULL (which keeps `auto_create_scheduled_instances()` away), `name` =
  `"{festival name} {yyyy}"`. Venue, timezone, comments and the rest live on the year,
  because venues and dates change.
- The years of a festival are the sessions whose path begins `{slug}/` — spec 055's rule
  guarantees that is exactly the set with a 4-digit second segment under that prefix.
- "All the sessions in Dallas" finds both years through their `place_id` (Midlothian is
  under Dallas). `/sessions/oflahertys` finds them through the prefix. Two groupings,
  both data.

The year session's own `name` carries the year because flat listings (directory rows,
home cards, the tune drawer's history labels — "O'Flaherty's Irish Music Retreat 2025 -
10/25 - Lively Session at Jim Bowie") show years side by side. The session header does
not use it (below).

## Reaching the right year: `/sessions/<festival-slug>`

Spec 055 resolution step 2, `kind = 'festival'`:

- **Window rule.** Today, in the festival's timezone (the year session's `timezone`), is
  within `[initiation_date − 7 days, end + 30 days]`, where `end` is `termination_date`
  or, when NULL, `initiation_date`. A year in the window → **302** to `/sessions/{slug}/{yyyy}`.
  Two years in the window (an edition held twice within five weeks) → the nearer
  `initiation_date` wins. Fixed constants (`FESTIVAL_WINDOW_BEFORE_DAYS = 7`,
  `FESTIVAL_WINDOW_AFTER_DAYS = 30`), not per-festival columns; they become columns in a
  ten-minute change if a festival ever needs it.
- **Exactly one year** → 302 to it regardless of the window. There is nothing to pick.
- **Otherwise, the picker**: a small page under the festival's name — the next upcoming
  year first with its dates, then past years newest first, one line each showing the
  dates and how many sessions (instances) have logged tunes. No tabs, no other chrome. It
  is the festival's own page and the one place the festival row's name is the whole
  heading; when the row gains `description`, it goes here. Admins see **Add a year**
  (below). On 2026-10-04 this is what O'Flaherty's shows: 2026 is more than a week out.

## The year switcher

On a festival year's page, public and admin (`frontend/src/sessionpage/`,
`frontend/src/sessionadminpage/`), the session header shows:

- The **festival's name from the place row**, linked to `/sessions/{slug}` (the picker).
  Not the year session's `name`.
- A **year `<select>`** beside it listing the sibling years, navigating on change. Shown
  only when the festival has two or more years.

Both pages get `festival: { place, years }` in their payload (below) to render this.

## Spawning a year: "Copy to a new year"

### Entry points

- The admin page of a year, Details tab: **Copy to a new year**. Source = that year.
- The festival picker: **Add a year**. Source = the most recent year.

One form, two entry points. Permission: **can edit the source year** — site admins and
that year's session admins (`session_person.is_admin`), the check that already exists.

### The form

- **Year**: defaults to the latest existing year + 1; editable to any year the festival
  does not already have, forward or back (backfilling 2024 from 2025 is expected). The
  path follows: `{slug}/{year}`, shown read-only — spec 055's rule leaves nothing else it
  could be.
- **Dates**: prefilled from the source, moved to the target year as **the same calendar
  dates nudged to the same weekday**: Oct 23–26 2025 (Thu–Sun) → Oct 22–25 2026 and
  Oct 24–27 2024. One pure function, tested; correct in both directions at any distance,
  where "shift 52 weeks" drifts a day or two a year. Editable. Both required.
- **Name**: prefilled `"{festival name} {year}"`. Editable.
- Everything else is copied silently and editable afterwards on the admin page.

### What copies

| Copied from the source year | Not copied |
|---|---|
| `session_type` (festival), `place_id` (town), `location_name`, `location_street`, `location_website`, `location_phone`, `timezone`, `comments`, `active_buffer_minutes_before/after`, `live_cache_session_limit`, `live_cache_global_limit`, `show_people_list`, `track_attendance`, `track_set_starters`, `unlisted_address` | `path`, dates (from the form); `thesession_id` (a year has none, and the app refuses two sessions on one upstream id); `recurrence` (NULL); `session_id`, audit columns (Postgres and the trigger set them; `created_by_user_id` = the copier) |
| **People**: the copier as a confirmed admin member (as `POST /api/add-session` does), plus the source year's admins (`session_person.is_admin`) as confirmed admin members | The rest of the roster; `session_tune` and `session_tune_alias` (built as tunes get logged); **instances** — last year's leaders and rooms are not this year's, and 36 wrong rows are worse than none. The new year opens with an empty Sessions tab and the Add Instance modal, which already knows the festival wording. A faster schedule-entry helper is a separate feature. |

### Endpoint

`POST /api/sessions/<path>/copy-year {year, initiation_date, termination_date, name}` →
`201 {success, path}`, one transaction. Refusals: 403 when the caller cannot edit the
source; 400 `year_exists` when `{slug}/{year}` is taken; 400 on a missing or inverted date
range; 400 when the source is not a festival year.

## Creating a new festival

The add-session sheet (`frontend/src/addsession/`), when the type is **festival**, asks
for the **festival's name** and the **year** in place of a session name, and on submit
creates the festival place row (slug from the name, `kind = 'festival'`, parent = the
matched town) and the first year `{slug}/{year}` in one transaction. The path preview
shows `/oflahertys/2025` before saving. Any logged-in user may do this, as they may
create a town; the slug shares the one namespace, so a taken slug gets spec 055's "did
you mean" treatment, and site admins fix slug or name on the Places page afterward.

## Directory and home

- The sessions directory lists **one row per festival**, linking to `/sessions/{slug}` so
  the window rule applies. Name and town from the place row; "On Now" when any year has
  an active instance. Years never appear as rows; past years are reached from the picker.
  A festival counts as active for the active/inactive filter when any year has no
  `termination_date` or a future one.
- The home page needs nothing: it is keyed by instance and by per-session membership, so
  two years coexist. (Being a member of 2025 says nothing about 2026 — which is why the
  copy carries the admins.)

## API

Changed outright, not additively (spec 055 takes the same exception; regenerate the Swift
client once when both are final).

- `GET /api/resolve?path=oflahertys` → `kind: "place"`:
  ```json
  { "success": true, "kind": "place",
    "place": { "slug": "oflahertys", "name": "O'Flaherty's Irish Music Retreat", "kind": "festival",
               "parent": { "slug": "midlothian", "name": "Midlothian" } },
    "years": [ { "session_id": 31, "path": "oflahertys/2026", "year": 2026,
                 "initiation_date": "2026-10-22", "termination_date": "2026-10-25", "logged_instances": 0 }, … ],
    "current": { "path": "oflahertys/2026" } }
  ```
  `current` is the window rule's pick or `null` when the picker applies. For a town,
  `years` and `current` are absent and the app shows the scoped directory
  (`/api/sessions/with-today-status?place=…`, spec 055).
- Session detail payloads (`/api/sessions/<path>/detail`, the admin payload) carry
  `festival: { place, years }` for a festival year, `null` otherwise. `years` is the list
  above, so the switcher and the app render from one shape.

## Migration (runs inside spec 055's script, step 3)

- Festival rows: `oflahertys` — "O'Flaherty's Irish Music Retreat", parent Midlothian;
  `noel-hill-ics-east` — "Noel Hill Irish Concertina School East", parent East Durham;
  `acf` — "Austin Celtic Festival", parent Austin (spec 055 converts the session).
- Rename the years: "O'Flaherty's Irish Music Retreat 2025"; "Noel Hill Irish Concertina
  School East 2026" (the row already ends in 2026); "Austin Celtic Festival 2025".
- `oflahertys/2025`: `initiation_date` 2025-10-24 → **2025-10-23**, its first instances'
  date, so the weekday nudge and the window compute from the real span.
- `noel-hill-ics-east/2026`: `termination_date` NULL → **2026-07-30**, its last instance,
  so the directory's active filter stops showing it as live forever.

## Help

`/help` (`templates/help.html`) gets a short section: a festival has one address, it
takes you to this year's when the festival is near, otherwise you pick; a new year is
copied from an old one by its admins. Keep in step with this spec (CLAUDE.md).

## Build order

After spec 055's schema, migration and validator: the copy endpoint and form, then the
window rule and picker, then the year switcher — that is what October needs. Then the
new-festival path in the sheet, the directory row, resolve and the native surface.

## Tests

- `tests/unit/test_festival_dates.py`: the weekday nudge, forward and back, across a
  year boundary and a leap day; the window rule at both edges in a non-UTC zone, NULL
  end, two-in-window tie.
- `tests/integration/test_festival_routing.py`: prefix → 302 in window, → picker outside,
  → 302 with one year; picker ordering and counts.
- `tests/integration/test_festival_copy.py`: fields copied and not, admins carried,
  roster and instances not, `year_exists`, 403 for a non-admin, backfill of an earlier year.
- Vitest: the switcher renders only with siblings and navigates; the sheet's festival
  mode previews `{slug}/{year}`; the picker's Add a year is admin-only.
- Contract tests for `kind: "place"` and `festival` on session detail.

## As built (2026-10-05)

Files: `festivals.py` (years, window rule, picker order, the `festival` block),
`api_routes.copy_festival_year`, `serializers.build_festival_payload` (the picker page
and `/api/resolve`'s festival answer, one builder), `web_routes._festival_landing`,
`templates/festival.html` + `frontend/src/festivalpage/` (new bundle),
`frontend/src/festival/` (`CopyYearSheet.svelte`, `YearSwitcher.svelte`, `dates.js`),
the switcher in `templates/session_detail.html` and the admin page, `/help`. Tests:
`tests/unit/test_festival_window.py`, `tests/integration/test_festival_routing.py`,
`tests/integration/test_festival_copy.py`, `frontend/tests/festival.test.js`,
`frontend/tests/festivaldates.test.js`.

Choices made while building:

- **The weekday nudge is client code** (`frontend/src/festival/dates.js`, Vitest), not
  Python: the form recomputes it as the year is edited and the server only receives
  dates. The window rule is Python (`tests/unit/test_festival_window.py`).
- **After a copy** the form goes to the new year's admin page, where the venue and the
  rest are edited.
- **`/sessions/<festival>/<tab>`** with a year in the window 302s to that year's tab; the
  picker ignores the tab.
- **"Add a year"** shows to system admins and admins of the most recent year (the copy
  source), as `permissions.can_add_year` in the picker payload, which also carries
  `latest` (the source).
- **The picker payload** is `/api/resolve`'s festival answer plus `latest` and
  `permissions`; `years` there is in the picker's order (upcoming first, then newest
  first). The `festival.years` block on session payloads is oldest first.
- **Upcoming years** show "Coming up" in place of a logged count.
- `PUT .../admin-update` had no session-admin check at all (commit 63847eb fixed it
  before this work); the copy endpoint uses the same `is_session_admin_for` gate.

