# 039 — Per-session people-tracking flags

**Status:** BUILT (2026-07-15). Design agreed by interview; implemented, tested, and
verified end-to-end in Chrome. 877 backend + 434 frontend tests green. Uncommitted.

## Why

A session should be able to turn off people-tracking without losing membership or
administrability. Not every session wants a public roster, attendance records, or
set-starter attribution — but some of that data is load-bearing elsewhere, so "hide
people" has to be carved precisely.

## Three flags, one dependency

Three booleans on `session`, all `NOT NULL DEFAULT TRUE` — this is **opt-out**, so
existing behaviour is preserved and new sessions start fully on unless the creator
unchecks something.

| flag | what it governs |
|---|---|
| `show_people_list` | the session-page **People tab** (the members roster) |
| `track_attendance` | check-ins — recorded AND displayed |
| `track_set_starters` | the "▸ Sean O" set-starter pill |

**Dependency:** recording who *started* a set is meaningless without recording who was
*there*, so `track_set_starters` requires `track_attendance`. A DB CHECK
(`ck_session_starters_need_attendance`: `track_attendance OR NOT track_set_starters`)
makes the nonsensical state unrepresentable; the UI disables + clears the starters box
when attendance is off; and both write paths (create, admin-update) normalize
`track_set_starters := track_set_starters AND track_attendance` server-side so no client
can land a violating pair.

Migration `schema/038_session_people_tracking.sql`.

## What each flag does — and, crucially, what it does NOT touch

### `show_people_list` off
The session-page People tab disappears for **everyone, admins included**. It folds into
the existing single gate: `can_view_people = (is_admin OR confirmed) AND show_people_list`
(`serializers.py`). An admin who wants the roster manages membership on the **session
admin page**, which is unaffected. When the list IS shown but attendance is off, the tab
renders members with the attendance badges and the "Sessions Attended" table stripped.

### `track_attendance` off
- No check-in UI in the live logger; the `attendance_*` ops are **refused server-side**
  (`_people_ops_blocked` in `live_logging_routes.py`), not merely UI-hidden — a stale
  client, a queued offline op, or a direct POST can't slip a check-in through.
- This session's attendance rows are excluded from **every** display, historic included:
  the person `/me` **Attended** tab (`api_routes.py`), the `/admin/people` **Checked In**
  count and Latest Session (`serializers.py`), and the spec-033 **R4 "while I was there"**
  lens. The rows stay in the DB, just unqueried — flip the flag back and they return.
- The tune drawer's **"while I was there" checkbox** hides when the drawer is scoped to
  this session (the filter is meaningless there); the wide lenses keep it, and their
  counts exclude this session app-wide.

### `track_set_starters` off (or forced off by attendance)
Starter pills hidden **past and present**, the "Started by" tray row / picker /
bulk-Assign gone, and `attribute_set_starter` refused server-side.

### Never touched by any flag
`session_person.is_admin` and membership itself (a people-hidden session stays
administrable and stays in *your* "my sessions"); the viewer's own `relationship`
(the R3 "member" lens reads your own row, not other people's); and — in the live logger
— **presence, "currently logging / away", typing, and the per-row "logged by" name and
color**. That last carve-out is deliberate: a collaborative logger inherently shows who's
actively logging right now, and you accepted that when you turned the logger on. So
`show_people_list` off is specifically "no persistent members tab", not "no names ever".

## The R4 exclusion lives in THREE places

`services/person_scope.py` holds R4 attendance logic in three spots, and all three needed
the `JOIN session ... AND track_attendance` filter — missing any one leaks. A test flushed
out the one I first missed:
- `attended_instance_predicate` (the tune-history `?attended=1` filter)
- `person_tune_play_counts_sql`'s `mine` CTE (the drawer's attended count)
- `plays_sort_expr('attended')` (the my-tunes sort)

R3/member logic in the same file is **not** filtered — it reads the viewer's own
`session_person` row.

## Where it lives

| | |
|---|---|
| Migration | `schema/038_session_people_tracking.sql`; `schema/full_schema.sql` |
| Payload + gate | `serializers.py` (session-detail `can_view_people` + flags; admin payload; `/admin/people` count; session_scope `track_attendance`) |
| Attendance exclusion | `services/person_scope.py` (R4 ×3); `api_routes.py` (person Attended tab) |
| Op refusal | `live_logging_routes.py` (`_people_ops_blocked`) |
| Write paths | `api_routes.py` (`add_session_ajax`, `admin-update` field map + normalize) |
| Logger config | `web_routes.py` (`live_logging_screen`), `templates/live_logging.html` |
| Logger UI | `frontend/src/App.svelte` (`trackAttendance`/`trackStarters` derived) |
| Session page | `frontend/src/sessionpage/{App,PeopleTab}.svelte` |
| Admin UI | `frontend/src/sessionadminpage/{DetailsTab,PeopleAdminTab}.svelte` |
| Create form | `frontend/src/addsessionpage/SessionSheet.svelte` |
| Drawer filter gate | `frontend/src/tunesheet/TuneSheet.svelte` (`showAttendedFilter`) |
| Tests | `tests/integration/test_people_tracking_039.py`, additions to `test_live_logging_ops.py` |

## Deploy note

Render does NOT run `schema/*.sql` on deploy — migration 038 must be applied to prod by
hand (`psql`) or the app 500s on the new columns.
