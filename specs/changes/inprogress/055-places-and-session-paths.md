# 055: Places and session paths

**Date:** 2026-10-04
**Status:** BUILT (2026-10-06): phase 1 (schema, migration, validators, matcher,
write paths, resolution), phase 2 (place pages, directory scoping, the Places admin
page, the sheet's town-or-metro choice) and phase 3 (the `place` object and the native
surface) — see the "as built" sections at the end. Not yet run against production;
the `city`/`state`/`country` column drop (step two) is still to come.
Decided in a design interview on
2026-10-04; the decisions below are the product owner's. Spec [056 Festival years](056-festival-years.md)
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

## Implementation notes (from the first code read, 2026-10-04)

Decisions made while reading the code, so a fresh session does not re-derive them:

- **`session.place_id` is nullable in the database until the step-two cleanup.** Dozens
  of tests insert sessions with raw SQL and one-segment paths (`conftest.py`
  `sample_session_data`, `test_tune_merge_030`, `test_live_logging_public`, …); a
  NOT NULL column breaks them all at once. The two API write paths enforce it instead,
  and the migration backfills every production row. SET NOT NULL lands with the column
  drop.
- **`city`, `state`, `country` keep being written** by both write paths, derived from the
  matched place (normalized long form), until the serializers switch to the `place`
  object. Otherwise a session created in the gap shows blank geography.
- **Schema delta file is `schema/058_places.sql`** — `055_*` and `056_*` filenames are
  already taken by unrelated features (abc search, pending registration). It adds
  `place`, `path_redirect`, `session.place_id` (nullable, FK, indexed) and
  `session_history.place_id`; `database.save_to_history` gains the column for `session`.
  `full_schema.sql` gets the same with `place` created before `session`.
- **Seed**: place rows 1–5 (austin, boston, chicago, sf, hill-country-fest); every seeded
  session gets `place_id`; session 6 becomes `hill-country-fest/2026` with a festival
  place row under Austin. No test references the old festival path; four reference the
  regular seed paths, which do not change. `sf` keeps its slug with name "San Francisco"
  (a slug need not equal the slug of its name).
- **Validators**: `session_path.py` and `frontend/src/shared/sessionpath.js` go from
  "at most 4 segments" to "exactly 2", same wording in both; the fixture file
  `sessionpath.fixtures.json` changes ("one part" becomes an error, add 3-segment cases);
  **`ios/CeolKit/Sources/CeolLogic/AddSession.swift` ports the same validator**
  (`maxSegments = 4`, line ~335) and reads the same fixtures, so it changes too or
  `make ios-test` fails. The kind/containment clauses live only on the server, in
  `places.py`.
- **Tests that post one-segment or non-place paths to `POST /api/add-session`** and need
  new payloads: `test_people_tracking_039.py` (`test/flags-*`, city Austin →
  `austin/flags-*`), `test_session_admin_fields.py` `TestCreate._payload` (one segment,
  city Testville), `test_api_endpoints.py` (`new-api-session-*`, city Houston),
  `test_session_path_validation.py` `_create_payload` (`probe/trimmed`, city Testville —
  first segment must become the town slug), `test_user_journeys.py` (mocked cursor; its
  `fetchone` side-effect sequence changes because the matcher adds queries),
  `test_page_payload_add_session_admin_people.py` (`x/x`, city `X` — passes as is since
  the town `x` gets created), `test_native_surface.py` (`memphis/contract-crossing`,
  city Memphis — passes as is).
- **New module `places.py`**: slugify (byte-for-byte the client's `generatePath` clean
  step: lowercase, drop anything outside `[a-z0-9\s-]`, spaces to hyphens, collapse,
  trim), US state table both directions, country aliases, `match_place`,
  `disambiguated_slug`, `validate_path_for_place`, `resolve_session_path` (exact → bare
  place → alias → redirect), `record_redirect` (upsert; delete rows whose `from_path` is
  the new live path; repoint rows whose `to_path` was the old path so chains collapse).
- **Sheet needs a pre-submit lookup**: `GET /api/places/match?city=&state=&country=`
  returning match / new / ambiguous plus the matched place with its parent, so the
  town-or-metro droplist and the "did you mean" prompt render before the save, not as a
  failed save. On an ambiguous create the server answers 409 `place_ambiguous` with the
  existing place and the suggested slug; the client resubmits with `place_id` or
  `place_new: true`.
- **Festival creation API** (`session_type = 'festival'` with `festival_name` and `year`,
  spec 056) is wired on the server in phase 1, because the new rule rejects the old
  `city/name` shape for festivals; the sheet side follows with spec 056.
- **Resolution in `web_routes.session_handler`** applies to the tab routes too
  (`/sessions/<path>/tunes|logs|people` call it with `active_tab`), so a 301 preserves
  the tab suffix. The admin routes do not redirect.

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

## Phase 1 as built (2026-10-05)

Files: `schema/058_places.sql` (and `full_schema.sql`), `scripts/migrate_055_places.py`,
`places.py`, `session_path.py` + `frontend/src/shared/sessionpath.js` + the iOS port,
`api_routes.py` (`add_session_ajax`, `update_session_ajax`, `match_place_ajax`),
`web_routes.session_handler`, `api_app_routes.resolve_path`, the add-session sheet's
"did you mean". Tests: `tests/unit/test_places_normalize.py`,
`tests/integration/test_place_matcher.py`, `tests/integration/test_path_resolution.py`,
`frontend/tests/addsession.sheet.test.js` ("the place the session is in").

Choices made while building, beyond the notes above:

- **The matcher also matches by name.** After the slug candidates (the bare slug and the
  two slugs disambiguation would have produced, so the second Athens is found again at
  `athens-greece`), a town whose name equals the city text with the same area and country
  is a match. Without it "San Francisco" would create a second town beside `sf`, and so
  would any production town whose slug is not its city's slug.
- **A festival holding the slug is not a town to have meant**: the city then gets a new
  town at the disambiguated slug, no question asked.
- **The generated prefix follows the town.** When the posted path's first segment is the
  slug of the typed city but the chosen town has another slug (`sf`, `athens-ga`) and no
  place of that name contains the town, the server puts the town's slug in front. The
  response's `session_path` is what was saved; the sheet now navigates there.
- **Creating a festival through `POST /api/add-session`**: `session_type = 'festival'`
  with `festival_name` and `year` (and optional `festival_slug`, `name`). A festival
  already at that slug whose parent is the matched town is the same festival and the year
  joins it; a slug held by anything else is `409 slug_taken` with `suggested_slug`. The old
  `city/name` shape for a festival is refused by the rule.
- **Admin update**: the form sends city/state/country on every save, so the matcher runs
  only when they differ from the session's (after normalization) or the session has no
  town. The rule is checked when the path, the type or the town changes — not when a
  pre-055 session merely gets its first town. A path sent unchanged is not re-validated
  (server and `DetailsTab.svelte`), so a pre-migration path cannot block other edits. A
  path change writes a `path_redirect` row (built here rather than with the Places page).
  An ambiguous city answers 409 `place_ambiguous`; the admin page shows the message only.
- **A bare place is still a 404 page** (`kind: "place"` from `/api/resolve`, without
  `years`/`current`) until place pages and spec 056's picker exist. One-segment session
  paths still resolve by exact match until the migration has run.
- **The town-or-metro droplist is not built**: no town has a parent until the Places page
  exists, so it would only ever offer one choice. `GET /api/places/match` already returns
  `path_prefixes` for it.
- The eager full-path lookup in `api_routes.get_session_instance_tune_detail` and in the
  legacy `session_instance_players` route are left in place; they are harmless.

### Running it in production

1. `psql "$PROD_URL" -f schema/058_places.sql` (idempotent; the old code ignores the new
   column and tables).
2. `DATABASE_URL="$PROD_URL" python3 scripts/migrate_055_places.py` — a dry run that does
   everything, prints it, and rolls back. Anything it cannot place is listed under "Not
   handled" and blocks `--apply`.
3. `... --apply`, then deploy. Rerunning is a no-op, so it can be run again after the
   deploy to catch a session created by the old code in between.

## Phase 2 as built (2026-10-06)

Place pages, directory scoping, the Places admin page, the sheet's town-or-metro choice.
Files: `serializers.build_sessions_directory_payload` (`place=`),
`web_routes._place_page`, `frontend/src/sessionsdir/` (heading, row place links,
festival rows), `places.py` (admin operations), `place_routes.py`,
`serializers.build_admin_places_payload`, `templates/admin_places.html` +
`frontend/src/placesadminpage/`, `frontend/src/addsession/DetailsSheet.svelte`. Tests:
`tests/integration/test_place_pages.py`, `tests/integration/test_places_admin.py`,
`frontend/tests/sessionsdir.app.test.js`, `frontend/tests/placesadminpage.test.js`, the
sheet tests.

- **Directory rows read geography from the town** (`city`/`state`/`country` are the
  place's name, area and country), so "TX" and "Texas" no longer sit side by side. The
  row shape is unchanged apart from the added `kind`, `place` and (festival rows)
  `years`; the `place` object proper is still the native-surface step.
- **A place page opens on "All Active"**, not "My Sessions".
- **The row's place is a link by script** (`role="link"`), because the row itself is
  an `<a>` and links cannot nest.
- **Places admin**: one `PUT` carries edits and a slug change; a changed slug is the
  rename (paths move, a `path_redirect` row per path and one for the bare prefix, which
  resolution follows to the renamed place with a 301). A slug an admin types is
  lowercase letters, digits and single hyphens, and not a year. Editing a town also
  rewrites its sessions' `city`/`state`/`country`. A festival's parent (its town) can be
  changed but not cleared.
- **The sheet's place lookup** (`GET /api/places/match`, debounced) supplies the path's
  first segment; a town with a parent shows "Address under" with `/{town}/…` and
  `/{metro}/…`. With no answer the path falls back to the city text, as before.

## Phase 3 as built (2026-10-06): the `place` object and the native surface

- **Session payloads** (`build_sessions_directory_payload` rows,
  `build_session_detail_payload`, `build_session_admin_payload`) carry `place` —
  `{place_id, slug, name, kind, area, country, parent}` — and no longer `city`, `state`,
  `country`. Consumers moved: `templates/session_detail.html`, `sessionsdir/logic.js`
  (`locationLabel` reads the place), the admin Details form (prefills city/state/country
  from the place; still posts them as inputs to the matcher), and the iOS sessions list
  and session screen (`SessionsViews.swift`). Inputs are unchanged: the add-session POST,
  the admin update and the thesession.org search/import still speak city/state/country.
  Not touched, web-internal and unused by a client: `/api/person/<id>/available-sessions`,
  `/api/person/<id>/search-sessions`, the bulk-import `session_info`, the person page's
  flattened `location` string.
- **`native-surface.yaml`**: `Place`, `FestivalYear`, `FestivalBlock` schemas; directory
  rows gain `kind`, `place`, `years`; `SessionDetail.session.place` and
  `SessionDetail.festival`; `ActiveInstanceSummary.path`; `Resolve.kind` gains `place`
  with `place`/`years`/`current`/`latest`/`permissions`, and `session`/`instance` are no
  longer required. The header records the one-time exception to the additive rule.
- **Optional, not nullable**: swift-openapi-generator drops a property declared as
  `oneOf: [$ref, {type: null}]`, so `place` and `festival` are plain `$ref`s left out of
  `required` (the Swift type is optional). The server therefore omits `festival` on a
  session that is not a festival year rather than sending null; `place` is always present
  after the migration.
- **Contract**: `VARIANT_GETS` in `tests/contract/test_native_surface.py` also validates a
  festival's resolve, a town's resolve, a festival year's detail and a scoped directory
  (kept out of `CHECKED_GETS`, which the fixture capture reads).
- **iOS**: the client regenerates at build time from the symlinked yaml (touch the
  symlink, `touch -h ios/CeolKit/Sources/CeolAPI/openapi.yaml`, if SwiftPM does not notice
  the target changed). `SessionsDirectory.json` and `SessionDetail.json` fixtures
  re-captured (the other fixtures' date drift was left out). CeolKit tests, the app build
  and the app's unit tests pass. Production samples (`make prod-parity`) will not decode
  until the new server is deployed.

