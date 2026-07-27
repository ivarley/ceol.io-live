# 047 — Festival instance names: shown everywhere, editable anywhere

## Problem

Spec 004 gave festivals overlapping same-day instances and spec 006 said how to name
them — `{Session Name} - {Date} - {location_override}` — but only the session's Logs tab
ever rendered the place. Everywhere else a festival instance was labelled by date alone,
which at a festival identifies nothing: "Hill Country Trad Fest - 2026-06-06" is the name
of *four* different sessions in four different rooms.

And `location_override` — the column carrying that name — was barely writable:

| Surface | Before |
|---|---|
| Add-instance sheet (`/sessions/<path>`) | A field labelled **Location**, placeholder "The usual: <venue>" — the right input, framed as an exception to the venue rather than as the log's name |
| Live logger header | Nothing. The header could re-date a log (spec 046) but not name it |
| Admin instance sheet (`/admin/sessions/<path>`) | View and delete only — no editing at all |
| Legacy pill editor's modal | The one real editor, and spec 035 Step 6 deletes it |

So the name that a festival depends on could, in practice, only be set at the moment the
instance was created — and only if you understood that "Location" meant "name".

## What was built

### 1. `instance_labels()` (`serializers.py`)

One helper returning both forms a list needs:

- `full_name` — with the session on the front, for cross-session lists
- `instance_label` — without it, for a list already scoped to one session

A **regular** session's label is the bare date, exactly as before. A **festival** appends
the place, falling back to the session's own `location_name` when the instance doesn't
override it — the same `location_override or location_name` the Logs tab has always
rendered, so an unnamed festival instance still gets a place rather than nothing.

Deviation from spec 006, deliberately: it wrote the festival date as `mm/dd`. These
labels appear in "All Sessions" lists spanning years, where a bare `mm/dd` is worse than
ambiguous, so the date is spelled in full in both forms.

`GET /api/tunes/<id>/history` now selects `session_type`, `location_override` and
`location_name` and returns both fields; the drawer's History tab renders
`instance_label` when scoped to one session and `full_name` otherwise (it previously
rendered the raw `instance.date` in the scoped case).

### 2. `set_name` op (`live_logging_routes.py`)

A metadata op beside `set_date`, with the same contract: anyone who can log may use it,
online-only, never queued for offline replay, SSE echo renames every other open screen,
prior value preserved by `save_to_history`.

- Blank clears the name. That's an edit, not an error — it means "back to the usual".
- Over 255 characters is `rejected: {reason: 'invalid'}`, rather than letting the column
  constraint raise mid-transaction.
- Setting the name to what it already is short-circuits before the write.
- Returns `{instance_name, previous_name}`.

`live_bootstrap` and the `/live/instances/<id>` shell both return `instance_name`, so the
header can paint the name before bootstrap lands (the same treatment `instance_date` got
in spec 046).

### 3. The header (`App.svelte`)

- Collapsed row: the name on its own line between the session name and the date, clipped
  to one line. **Absent when unset**, so a weekly session's header is unchanged.
- Expanded panel: a **Name** row directly under Date, reading the name or — when unset —
  "The usual" / "Unnamed" depending on the session type, with a `Rename` / `Name it`
  action. Not festival-gated — it's the same field a regular session uses for a night at
  a different venue.
- The sheet reuses the date sheet's `.dt-*` chrome, because it's the same kind of
  decision. Save is explicit; clearing a set name keeps the commit live and relabels it
  "Clear name".

`instanceName` applies from a snapshot on key *presence*, not truthiness — `null` is a
real value (an unnamed log), but a snapshot cached before this spec has no key at all and
must not blank the name the shell already painted.

The sheet's help text **reads the session type**. `session_type` is plumbed into the
logger (bootstrap + shell config + offline snapshot) for this one purpose. At a festival
naming is the norm and the reason is concrete — "Several sessions share a day here, so the
date on its own won't tell them apart" — while everywhere else it's the exception, and
telling someone at a weekly pub session about "a festival day with several sessions" is
noise about a case they will never be in. The placeholder and the unnamed-state wording
follow the same split ("Unnamed" at a festival, where there is no *usual*; "The usual"
otherwise).

Nothing is **gated** on session type — the same fields are editable either way. Only the
words change. And "Clear name" appears only when there is a name to clear; on an
already-unnamed log an empty box is the status quo, not a deletion.

### 4. The add-instance sheet (`AddInstanceModal.svelte`)

Takes `isFestival`. At a festival the field is labelled **Name**, placeholder "e.g.
Advanced Session @ Jim Bowie", with a caption saying why. Regular sessions keep
**Location** and "The usual: <venue>" verbatim.

## Test data

`schema/seed_data.sql` grew session 6, `austin/hill-country-fest` — three days, eight
instances, overlapping pairs, an open-ended end time, two instances sharing both a date
and a name (the only shape that exercises `historyScopeOptions`' start_time tiebreak),
and one with a NULL `location_override` exercising the venue fallback.

## Tests

- `tests/integration/test_tune_history.py` — `TestFestivalInstanceLabels`: same-day
  instances get distinct labels, the unnamed instance falls back to the venue,
  `instance_label` drops the session name, and regular sessions are byte-identical.
- `tests/integration/test_live_logging_ops.py` — `set_name` sets (trimmed, with history),
  clears, rejects an overlong name, no-ops on an unchanged name, and reaches bootstrap;
  plus bootstrap carrying `session_type` both ways.
- `frontend/tests/App.sessionname.test.js` — the header offers to name an unnamed log,
  one `set_name` op reaches the collapsed header, blanking clears, an SSE echo renames
  with attribution, and the help/placeholder/unnamed wording differs by session type
  (the regular copy never mentions festivals).

## Not done

An annually-recurring festival still can't be one session row: `initiation_date` /
`termination_date` model a single run, so each year's edition needs its own session and
its own path.
