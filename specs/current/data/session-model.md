# Session Model

Core data structures for tracking recurring and one-time music sessions.

## Tables

### `session` - Recurring Sessions
Represents a regular music session (e.g., "Mueller Monday Night Session").

**Key Fields**:
- `session_id` (PK) - Unique identifier
- `name` - Display name
- `path` - The session's URL: exactly `{place}/{name-or-year}` (e.g., "austin/mueller", "oflahertys/2025"); see the note below and [spec 055](../../changes/inprogress/055-places-and-session-paths.md)
- `place_id` (FK → place) - The session's **town**, whichever slug its path uses (a Conroe session filed under `houston/…` still points at Conroe). A festival year points at the festival's town. Nullable in the database until `city`/`state`/`country` are dropped; both API write paths set it.
- `location_name` - Location name
- `location_street` - Street address
- `location_website` - Venue website
- `location_phone` - Venue phone number
- `city`, `state`, `country` - Geographic location. Being replaced by the place (spec 055): both write paths still write them, copied from the town in the long form ("Texas", "United States"), until the serializers read geography through `place`; then they are dropped.
- `timezone` - IANA timezone identifier (default: UTC)
- `recurrence` - JSON pattern (see Recurrence below)
- `session_type` - "regular" or "festival" (default: "regular"); see [spec 004](../../changes/004-session-type.md).
  A festival does not recur — `recurrence` is NULL and `initiation_date`/`termination_date` are its
  first and last day. It flips the public page (Sessions tab first, grouped by day) and its instances
  may overlap. A festival year lives under its festival's place row (`{festival-slug}/{yyyy}`, spec 056).
  Seeded as session 6, `hill-country-fest/2026`, in `schema/seed_data.sql`.
- `active_buffer_minutes_before` - Minutes before session is considered active (default: 60)
- `active_buffer_minutes_after` - Minutes after session is considered active (default: 60)
- `auto_create_instances` - Whether to auto-create instances ahead of schedule (default: FALSE)
- `auto_create_hours_ahead` - Hours ahead to auto-create instances (default: 24, range: 1-168)
- `created_date`, `last_modified_date` - Audit timestamps

**Note**: Times are stored on `session_instance`, not `session`. The recurrence pattern may contain default times.

**Note on `path`**: the path *is* the session's URL — every page and API route is keyed on it
(`/sessions/<path>`, `/admin/sessions/<path>`, `/api/sessions/<path>/...`), and nothing looks a
session up by `session_id`. So a session written with an unusable path has no reachable screen
that could repair it; only a direct `UPDATE` gets it back. Every write validates structure, not
just non-emptiness, via `normalize_session_path()` in `session_path.py` (mirrored on the client in
`frontend/src/shared/sessionpath.js` — keep the two in lockstep). Slash-separated segments of
RFC 3986 unreserved characters, each containing at least one letter or number; no leading,
trailing or doubled slashes, no `.`/`..` segments, no whitespace or invisible characters.
This exists because a production session was created with a path that was non-empty (so it passed
the old `.strip()` check) but resolved to nothing in a browser, stranding it.

Since spec 055 a path is **exactly two** segments, and `places.validate_path_for_place()` adds
the clauses that need the database: the first segment is a `place` slug; under a festival the
second is a 4-digit year and the session is `session_type = 'festival'`; under a town or metro the
second is not a year and the place contains the session's town (the town itself or an ancestor).
The client mirror and the iOS port (`ios/CeolKit/Sources/CeolLogic/AddSession.swift`) check
characters and the two segments; the place clauses come back from the server as form errors. An
admin save that sends the session's current path unchanged is not re-validated, so a path from
before the rule cannot lock its session out of other edits.

### `place` - Towns, metros and festival prefixes (spec 055)
The first segment of every session path. **Location**: `schema/058_places.sql`, logic in `places.py`.

- `place_id` (PK), `slug` (UNIQUE — one namespace for towns, metros and festivals)
- `name` - "Austin", "Houston", "O'Flaherty's Irish Music Retreat". A slug need not be its name's slug (`sf` / "San Francisco").
- `kind` - `'place'` (a town or metro) or `'festival'` (spec 056)
- `parent_place_id` (FK → place) - a town's metro, or a festival's town; always a `kind = 'place'` row
- `area`, `country` - normalized long form (US states spelled out; USA/US → "United States"); NULL for festivals
- audit columns as on `session`

New towns come from the **place matcher** (`places.match_place`, `GET /api/places/match`): the
city text's slug plus normalized area and country find an existing town (also by name, for a town
whose slug is not its name's); no match creates one; the same slug somewhere else is ambiguous and
the add-session sheet asks "did you mean" (`409 place_ambiguous`, resubmitted with `place_id` or
`place_new`), a new town taking a disambiguated slug (`athens-ga`, `athens-greece`).

### `path_redirect` - Old paths (spec 055)
`from_path` (PK) → `to_path`. Written by the spec 055 migration (the legacy strays) and by a path
change on the session admin page (`places.record_redirect`, which also collapses chains and drops a
row whose `from_path` is live again). `/sessions/<path>` resolution (`places.resolve_session_path`):
exact path → bare place → town/metro alias (301) → redirect (301, up to 3 hops) → `{path}/{date-or-id}`
with the path resolved the same ways.

**Location**: `schema/create_session_table.sql`

### `session_instance` - Specific Occurrences
Individual dated occurrences of sessions.

**Key Fields**:
- `session_instance_id` (PK)
- `session_id` (FK → session)
- `date` - Specific date of occurrence
- `start_time`, `end_time` - Start and end times
- `location_override` - Location override
- `is_cancelled` - Cancellation flag
- `is_active` - Currently active (managed by cron job)
- `comments` - Instance-specific notes
- `log_complete_date` - When log was marked complete
- `created_date`, `last_modified_date` - Audit timestamps

**Location**: `schema/create_session_instance_table.sql`

### `session_instance_tune` - Tune Logs
Individual tunes played during a session instance.

**Key Fields**:
- `session_instance_tune_id` (PK)
- `session_instance_id` (FK → session_instance)
- `tune_id` (FK → tune, nullable)
- `name` - Name as played
- `order_position` - Fractional index for ordering (VARCHAR(32), base-62 CRDT string)
- `continues_set` - True if continues previous tune in a set
- `played_timestamp` - When tune was played
- `inserted_timestamp` - When log entry was created
- `key_override` - Musical key override (VARCHAR(20))
- `setting_override` - Specific thesession.org setting ID
- `created_date`, `last_modified_date` - Audit timestamps

**Live-logging columns** (Feature 024, `schema/024_live_logging_delta.sql`):
- `source` - 'human' (default) or 'audio'
- `confidence` - SMALLINT 0..100; NULL = definite human entry
- `deleted` - Soft tombstone (live `remove_tune` op never hard-deletes)
- `logged_timestamp` - Client-asserted log time
- `client_device_id` - Originating device
- `played_start` / `played_end` - Audio-only timing (nullable; human ops never write these)

**Constraint**: `tune_id IS NOT NULL OR name IS NOT NULL` (must have one)

**Location**: `schema/create_session_instance_tune_table.sql`

### `session_event` - Live Logging Change Feed
Append-only, per-instance delivery/replay log for the real-time logger (Feature 024).
`session_instance_tune` stays canonical state; `session_event` is the ordered feed that
drives SSE fan-out (`event_id` doubles as the `Last-Event-ID` cursor). Not an audit table —
see [Live Logging](../logic/live-logging.md) and [History](history.md).

**Location**: `schema/024_session_event.sql`

## Relationships

```
session (1) ──< session_instance (N)
session_instance (1) ──< session_instance_tune (N)
session_instance_tune (N) ──> tune (1, optional)
```

## Recurrence Patterns

Stored as JSON in `session.recurrence` field. Schema in `schema/recurrence_schema.json`.

**Examples**:
```json
// Every Monday
{"type": "weekly", "interval": 1, "daysOfWeek": [1]}

// First and third Tuesday
{"type": "monthly", "interval": 1, "daysOfWeek": [2], "setPositions": [1, 3]}

// One-time event
{"type": "one_time", "date": "2025-12-25"}
```

**Logic**: `session_instance_auto_create.py` generates instances from patterns

## Key Operations

### Create Session Instance
- Manual: `api_routes.py:/api/session_instance` POST
- Auto: `session_instance_auto_create.py:auto_create_session_instances()`

### Log Tunes
- Standard UI: `web_routes.py:session_instance_detail()` + `api_routes.py:/api/session_instance/<id>/tunes`
- Beta UI: `web_routes.py:session_instance_detail_beta()`
- Live (real-time, multi-user): `live_logging_routes.py` ops at `POST /api/live/instances/<id>/ops` — see [Live Logging](../logic/live-logging.md) (Feature 024)
- Logging a **linked** tune (any UI) enrolls it into the session's repertoire (`session_tune`)
  as a side effect; see [Tune Model → session_tune](tune-model.md) and spec 025. Deleting the
  last live play in the live logger un-enrolls it again unless the entry is protected
  (`manually_added` / curated) — spec 045.

### Set Management
- Group tunes: Set `continues_set = TRUE` to continue previous tune
- Break set: Set `continues_set = FALSE`
- Reorder: Update `order_position` via API (fractional indexing allows insertion without reordering)

## Access Patterns

### Get Session with Future Instances
```sql
SELECT s.*, si.date, si.session_instance_id
FROM session s
LEFT JOIN session_instance si ON s.session_id = si.session_id
WHERE s.session_id = ? AND si.date >= CURRENT_DATE
ORDER BY si.date
```

### Get Session Log
```sql
SELECT sit.*, t.name as canonical_name, t.type, t.thesession_tune_id
FROM session_instance_tune sit
LEFT JOIN tune t ON sit.tune_id = t.tune_id
WHERE sit.session_instance_id = ?
ORDER BY sit.order_position
```

## Related Specs

- [Tune Model](tune-model.md) - Linked tune metadata
- [People & Attendance](people-model.md) - Who attends sessions
- [Session Management Logic](../logic/session-logic.md) - Business rules
- [Session Logging UI](../ui/session-logging.md) - User interface
- [Live Logging](../logic/live-logging.md) - Real-time multi-user logging (Feature 024)
