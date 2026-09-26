# Tune Search and Linking Logic

Finding tunes by name and linking to thesession.org canonical database.

## Tune Matching Algorithm

**Function**: `find_matching_tune(cur, session_id, tune_name, allow_multiple_session_aliases)` | `database.py:355-435`

**Returns**: `(tune_id, final_name, error_message)`

**Search Order** (cascading, case/accent insensitive):
1. `session_tune.alias` - Session-specific primary alias
2. `session_tune_alias.alias` - Additional session aliases
3. `tune.name` - Canonical names with "The" flexibility

**"The" Flexibility**: Matches "Silver Spear" with/without "The" prefix
```sql
WHERE LOWER(unaccent(name)) = LOWER(unaccent(%s))
   OR LOWER(unaccent(name)) = LOWER(unaccent('The ' || %s))
   OR LOWER(unaccent('The ' || name)) = LOWER(unaccent(%s))
```

**String Normalization**: `normalize_apostrophes()` | `database.py:5-10` - Smart quotes → ASCII

**Accent Insensitivity**: `unaccent` extension | `schema/add_unaccent_extension.sql`

**Error on Duplicates**: Multiple matches raise error unless `allow_multiple_session_aliases=True`

## Tune Linking

**API**: `POST /api/sessions/<path>/<date_or_id>/match_tune` | `api_routes.py:5666`

**Payload**: `{"session_instance_tune_id": 123, "thesession_tune_id": 456, "setting_id": 789}`

**Process**:
1. Validate session_instance_tune exists
2. Fetch from thesession.org (if not cached)
3. Create/update `tune` record (canonical metadata)
4. Create/update `tune_setting` record(s) (ABC + images)
5. Create/update `session_tune` record (session preferences)
6. Update `session_instance_tune.tune_id` (link log entry)

**Storage**:
- `tune` - Name, type, tunebook_count_cached
- `tune_setting` - ABC notation, images (PNG), key
- `session_tune` - Session-specific alias, key, setting_id

## ABC Caching

**Incipit**: `extract_abc_incipit(abc, tune_type)` | `database.py:131-202` - First 2 bars (3 if pickup)

**Images**: Via ABC renderer service (see [ABC Renderer](../services/abc-renderer.md))

**Script**: `scripts/cache_missing_settings.py`

**Storage**: `tune_setting` - abc, incipit_abc, image, incipit_image

## Tune Search

**API**: `GET /api/tunes/search?q=<query>&mode=name|abc|mixed` | `api_person_tune_routes.py` `search_tunes`

**Strategy**:
1. Search local `tune` table by name, blending in notation matches (below)
2. If insufficient results, query thesession.org API
3. Merge, deduplicate, sort by relevance + popularity
4. Cache new results locally

A query that is a thesession.org URL or a bare tune id is a POINTER, not a query: it
resolves to that one tune (following merge redirects) and never gets notation blended in.

## Notation (ABC) Search

Searching by notes — type `fdd cAA | B`, find "My Darling Asleep". Available in **every**
box that searches tunes (feature 051), not just the deep search.

**The rules live in one place per runtime, and all three must agree:**

| Runtime | Definition |
|---|---|
| SQL | `abc_search_key(text)` — `schema/055_abc_search_index.sql`; backs the index |
| Python | `abc_query_key` / `is_abc_friendly` / `abc_search_terms` / `ABC_MATCH_SQL` — `database.py` |
| Browser | `frontend/src/shared/abcquery.js` (hand-copied into `static/js/offline_data.js`, which loads outside every Vite bundle) |

**Normalization**: drop grace notes `{…}`, chord symbols `"…"`, whitespace, and legacy `!`
line breaks; lowercase. Ornament stripping is what lets a typed `AAABc` find a setting
stored as `{g}A{d}A{e}A {g}ABc`. Lowercasing deliberately ignores ABC's octave-case
convention, so `GED` and `ged` find the same tune.

**Modes**: `mixed` (default) blends notation with name matches, ranked below them, and
flags notation-only rows `abc_only` so the UI can mark them. `name` and `abc` narrow to one
kind (the deep search's filter tabs). `mixed` requires the query to look like notes AND be
at least `ABC_MIN_QUERY_LEN` (3) characters — shorter matches nearly the whole catalog, and
pg_trgm cannot use the trigram index below 3. `mode=abc` honors whatever was typed.

The "looks like notes" test is deliberately permissive — real names like `Cabbage` and
`Bee` are all note letters. A false positive costs extra rows ranked below the name
matches, never a wrong answer.

**Filtering an already-loaded list**: `POST /api/tunes/abc-filter {q, tune_ids}` returns the
subset whose notation matches. My Tunes, the session Tunes tab and the admin tunes tab all
filter client-side over a payload that carries no ABC (far too large to ship), so they post
their visible ids and union the result into the same filter pass.
`frontend/src/shared/abcfilter.svelte.js` is the one client mechanism. `@public_api` —
session pages are publicly viewable, so their Tunes tab must filter logged out.

**Index**: `idx_tune_setting_abc_trgm`, a pg_trgm GIN index on `abc_search_key(abc)`. A
leading-wildcard LIKE cannot use a B-tree, and the query must use the identical expression
or the planner won't touch the index — same pattern as `tune_search_key` (migration 026).
Apply migration 055 **before** deploying code that calls it.

**Offline**: incipit-only — the bundle carries `incipit_abc`, never full ABC. Hits are
flagged `abc_scope: 'incipit'`. See [Offline Support](offline.md).

**Session-Specific Search** (prioritizes session aliases):
1. `session_tune` & `session_tune_alias` - Highest priority
2. Global `tune` table - Medium priority
3. thesession.org API - Lowest priority

**Ranking**: Session exact > Session partial > Canonical exact > Canonical partial > External

## Popularity Tracking

**Field**: `tune.tunebook_count_cached` - Bookmark count from thesession.org

**Refresh**: `scripts/refresh_tunebook_counts.py` - Weekly/monthly cron

**Usage**: Sort search results, identify common tunes

## Alias Management

**Primary Alias**: `session_tune.alias` - Single per (session, tune)

**Additional Aliases**: `session_tune_alias` table - Unlimited

**Create API**: `POST /api/session/<id>/tune/<tune_id>/alias` with `{"alias": "..."}`

**Search**: Both types searched with equal priority

## Error Handling

**Multiple Matches**: Error unless disambiguated with alias
**No Matches**: Options - create unlinked, refine search, search thesession.org
**API Failures**: Fall back to local cache, show warning

## Performance

**Indexes**:
- `idx_tune_name` - Name searches
- `idx_tune_tunebook_count` DESC - Popularity sorting
- Session alias indexes - Session-specific lookups

**Scripts**: `schema/optimize_session_tune_performance.sql`, `schema/popular_tunes_indices.sql`

**Caching**: Most searches satisfied by local cache without external API call
