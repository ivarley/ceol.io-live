# 055: Places and session paths

**Date:** 2026-10-04
**Status:** SPECIFIED — not started. Decided in a design interview on 2026-10-04; the
decisions below are the product owner's. Spec [056 Festival years](056-festival-years.md)
depends on this one.

## Why

A session's path IS its URL, and today it is whatever the adder typed. Production holds
30 sessions: 27 shaped `{city}/{name}`, 2 festivals shaped `{festival}/{year}`
(`oflahertys/2025`, `noel-hill-ics-east/2026`), and 3 strays — `logan-prodigy` (one
segment), the literal string `None` (Shawn's house, stranded), and `austin/acf` (the
Austin Celtic Festival, typed regular because it predates the festival type). The
geography columns have drifted the way free text does: `state` holds both "TX" and
"Texas", `country` both "USA" and "United States".

Two things want the same fix. Browsing by place ("all the sessions around Houston",
including the one in Conroe) needs a curated place vocabulary, not a city string. And a
festival needs a prefix that owns its years (`/sessions/oflahertys` is a 404 today) —
which is the same thing as a place that owns its sessions. So: the first path segment
becomes a row in a `place` table, the path shape becomes a hard rule, and the strays get
fixed with redirects.

Deliberately NOT a country level (`us/austin/mueller`): the URL only has to be unique and
readable; geography is data on the place row. City slugs collide rarely (a second Athens)
and get a disambiguated slug when they do.

## The rule

A session path is exactly two segments, `{place}/{second}`:

- The first segment is the slug of an existing `place` row.
- If that place is `kind = 'festival'`, the second segment is a 4-digit year.
- If that place is a town or metro, the second segment is a name slug that is NOT a
  4-digit year, and the place must contain the session's own town — the town itself or
  one of its ancestors. (A Conroe session may live at `conroe/…` or `houston/…`, never
  `dallas/…`.)
- Character rules are unchanged from `session_path.py` today (RFC 3986 unreserved, each
  segment with at least one letter or digit).

Enforced in `normalize_session_path()` for the character and shape checks and in a new
server-side check for the place-dependent clauses, at BOTH write paths
(`POST /api/add-session`, `PUT /api/sessions/<path>/admin-update`). The client mirror
`frontend/src/shared/sessionpath.js` keeps the character and two-segment checks; the
place clauses need the database and surface as ordinary form errors.

A side effect worth having: with every session path exactly two segments, the old
"is `oflahertys/2025` a session or an instance" ambiguity disappears — three segments is
always `{path}/{date-or-instance-id}`. The eager full-path lookups in
`web_routes.session_handler`, `api_routes` (tune detail) and `api_app_routes.resolve_path`
can go once the migration has run.

## Schema

### `place`

| Column | Notes |
|---|---|
| `place_id` SERIAL PK | |
| `slug` VARCHAR(100) NOT NULL UNIQUE | The first URL segment. Same character rules as a path segment. One namespace for towns, metros and festivals. |
| `name` VARCHAR(255) NOT NULL | Display name: "Austin", "Houston", "O'Flaherty's Irish Music Retreat". |
| `kind` VARCHAR(16) NOT NULL CHECK IN ('place','festival') | A town or metro, or a festival prefix (spec 056). |
| `parent_place_id` INTEGER NULL REFERENCES place | The containing place. For a town: its metro (Conroe → Houston), or NULL. For a festival: the town it happens in (O'Flaherty's → Midlothian). A parent is always `kind = 'place'`. |
| `area` VARCHAR(255) NULL | thesession.org's word: a US state, an Irish county, a region. Stored in the normalized long form ("Texas"). NULL for festivals. |
| `country` VARCHAR(255) NULL | Normalized long form ("United States"). NULL for festivals. |
| audit columns | `created_date`, `last_modified_date`, `created_by_user_id`, `last_modified_user_id`, as on `session`. |

`name`, `area`, `country` rather than `town`, `state`, `country`: `name` because the row may
be a metro or a festival; `area` because it is a state in Texas and a county in Clare.
No festival-specific columns yet (website, description) — add `description` when the
festival picker needs a sentence of context, not before.

### `session`

- `place_id` INTEGER NOT NULL REFERENCES place — the session's **town**, always
  `kind = 'place'`, regardless of whether the path uses the town or the metro slug. A
  festival year points at its town too.
- `city`, `state`, `country` become derived from the place in two steps: (1) this spec
  backfills `place_id`, switches every serializer and filter to read geography through
  the place, and stops writing the three columns; (2) a later cleanup drops them once
  nothing reads them. The API shape changes in step 1 (below), so step 2 is invisible.

### `path_redirect`

| Column | Notes |
|---|---|
| `from_path` VARCHAR(255) PK | A path that used to be, or might be guessed as, a session's. |
| `to_path` VARCHAR(255) NOT NULL | The session's path at the time the row was written. |
| `created_date` | |

Written by: the migration (legacy strays), a slug rename on the Places admin page (one row
per session under that slug), and a path change on the session admin page. Renaming back
to an old path deletes the stale row. A runtime table, not a list in code, because the
renames happen from the admin UI.

## Resolution: `/sessions/<anything>`

In order:

1. **Exact `session.path` match** → the session page (as today).
2. **Bare prefix** (one segment) → look up `place.slug`. `kind = 'place'`: the scoped
   directory (below). `kind = 'festival'`: spec 056's window rule (redirect to a year, or
   the picker). No match → 404.
3. **Two segments, no exact match** → the town/metro alias: first segment is a place `P`,
   and exactly one session has a path whose second segment matches and whose town is `P`
   or lies under `P` → **301** to that session's path. (A Conroe session filed as
   `houston/the-pub` is reachable as `conroe/the-pub`, and vice versa.)
4. **`path_redirect`** → 301 to `to_path`, following up to 3 hops (a redirect whose
   target is itself redirected).
5. **Three segments** → `{path}/{date-or-id}` instance resolution, as today, with the
   path itself resolved through steps 1, 3 and 4 so an aliased or redirected path still
   reaches its instances.
6. 404.

`/api/resolve` applies the same order and returns the session or instance it lands on; a
bare prefix returns `kind: "place"` (shape in spec 056, since the festival fields are
what make it interesting).

## Adding a session

The sheet (`frontend/src/addsession/`) keeps its one path to the server, and the city
text becomes the input to a **place matcher** rather than a column:

1. **Normalize** area and country before comparing: US state abbreviations ↔ names (the
   table `guessTimezone` already has, both directions) and a short country alias list
   (USA / US / United States; UK / United Kingdom; Ireland / Éire). Store the normalized
   long form on new place rows. Outside the US `area` is free text (a county, a region);
   there is no vocabulary to validate against.
2. **Match** by slug of the city text. Same slug, same normalized area and country →
   that place. No such slug → create a town, no parent, area and country from the form.
3. **Same slug, different area or country** (Athens GA vs Athens, Greece; or just a
   mismatch nobody normalized) → the sheet asks: "Did you mean Athens, Georgia?" with
   the existing place or "a new place". On "new", the slug is disambiguated
   automatically — `athens-ga` from the area if present, `athens-greece` from the country
   otherwise. The first Athens keeps `athens`.
4. **Primary path**: when the matched town has a parent, the path field is a droplist
   of `/{town}/{name}` and `/{metro}/{name}`; the adder picks which is primary. A
   brand-new town has no parent, so there is one option; the metro alternative appears
   after a site admin assigns the parent (and works as an alias from then on, step 3 of
   resolution). The name half of the path stays editable as today.

thesession.org imports feed the same three fields (`town` → city, `area` → area,
`country` → country; `api_routes.py` `_thesession_field`) and go through the same matcher.
The adder may create a **town** this way; they may not edit one (next section). Creating
a **festival** is spec 056.

## Who may change a place

Site admins only, after creation. A place is a shared fact: renaming "Austin" relabels
every Austin session. The adder's typo is fixed by an admin in ten seconds, which is how a
bad path is fixed today, except there is now a screen for it.

### Places admin page (`/admin/places`)

Day one:
- List every place with kind, parent, area, country and session count; search.
- Edit name, area, country.
- Set or clear the parent. Creating a metro that has no sessions of its own (Waco, Dallas)
  is "add a place" with no sessions; parents must be `kind = 'place'`, and the chain must
  not cycle.
- Rename the slug: rewrites the path of every session under the slug (primary paths
  only), writes one `path_redirect` row per rewritten path, and writes a row for the bare
  prefix too.
- Delete a place with no sessions and no children.

Not day one: **merge** ("Austn" into "Austin"). With ~25 towns a duplicate is rare and is
two edits by hand; build merge when it stops being rare.

The **session admin page's path field** stays editable, validated by the full rule above,
and a change writes a `path_redirect` row (today a rename silently breaks every shared
link).

## Place pages and the directory

- **`/sessions/<town-or-metro>`** is the sessions directory
  (`frontend/src/sessionsdir/`, `build_sessions_directory_payload`) scoped to the place:
  sessions whose town is the place or lies under it, with the same filters and search,
  a heading naming the place, and its child places as links. Festival years in the area
  appear through their town link, labeled as festivals. Grouping by town under a metro
  waits for a metro that needs it.
- The **unscoped directory** links each session's place name to its place page — how
  people discover the pages exist.
- `GET /api/sessions/with-today-status` takes `?place=<slug>` for the scoped view.
- One row per **festival**, not per year (detail in spec 056).

## API: the `place` object

Nobody but the owner has the native app yet, so the surface changes outright rather than
additively (a deliberate exception to spec 052's additive rule, taken once, now).

Every session payload replaces the flat `city`, `state`, `country` fields with:

```json
"place": {
  "slug": "conroe",
  "name": "Conroe",
  "kind": "place",
  "area": "Texas",
  "country": "United States",
  "parent": { "slug": "houston", "name": "Houston" }
}
```

`parent` is `null` for a top-level town. Touches: every serializer that emits a session
(`serializers.py`), the directory payload, `specs/api/native-surface.yaml`,
`tests/contract/test_native_surface.py`, the generated Swift client in `ios/CeolKit`, and
the iOS screens that show a city. Regenerate the client once, after spec 056's additions
to the same payloads are also final.

## Migration

One script, run once against production, in this order:

1. Create a town row for each distinct first segment of the 27 `{city}/{name}` paths,
   `name` from the session's `city` text (title case as entered), `area` and `country`
   normalized. The three towns of the festivals and strays below as well (Midlothian,
   East Durham, Houston already exists, Logan already exists).
2. Fix the strays:
   - `None` → `houston/shawns-house`. No redirect (one tune ever logged).
   - `logan-prodigy` → `logan/prodigy`, with a redirect.
   - `austin/acf` → festival: place row `acf` (kind festival, name "Austin Celtic
     Festival", parent Austin), path `acf/2025`, `session_type = 'festival'`, with a
     redirect from `austin/acf`.
3. The two existing festivals' place rows and year renames — spec 056 lists them.
4. Set `place_id` on every session from its first segment (for festivals, from the town).
5. Assign **no parents**. Lorena under Waco, Midlothian under Dallas, Sandy Springs under
   Atlanta are curation and are done on the Places page afterward, where the metro rows
   get created.

Seed data (`schema/seed_data.sql`) gains place rows for its sessions; the seeded festival
`austin/hill-country-fest` becomes `hill-country-fest/2026` with a festival place row.

## Build order

055 schema, migration and validator first; then spec 056's copy and routing (the
October-critical path); then the rest of this spec (place pages, directory scoping,
Places admin, redirect-writing on rename); the native surface last.

## Tests

- `tests/unit/test_session_path.py`: two-segment rule, year-vs-name by kind, containment.
- `tests/integration/test_place_matcher.py`: normalization, match / create / disambiguate.
- `tests/integration/test_path_resolution.py`: the six resolution steps, alias 301,
  redirect chain limit, instance under an aliased path.
- `tests/integration/test_places_admin.py`: rename writes redirects; delete refuses with
  sessions or children; parent cycle refused.
- Contract tests updated for the `place` object; Vitest for the sheet's droplist and the
  "did you mean" step.
