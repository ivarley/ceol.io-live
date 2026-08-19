# 051: Notation (ABC) Search Everywhere You Can Search by Name

## Purpose

Ceol could already find a tune by its notes — type `fdd cAA | B`, get "My Darling Asleep" —
but only in one place: the **deep search** (`_deep_search_core`), reached from the live
logger and the two add panes, all through `TuneSearch.svelte`.

Every other tune-search box was name-only. So whether Ceol could help when you had a tune
in your fingers but not its name depended on which box you happened to be standing in
front of. This closes that: a note-shaped query searches notation in **every** box that
searches tunes.

## Surfaces closed

| Surface | Was | Now |
|---|---|---|
| Hamburger **"Find a tune"** (`FindTune.svelte` → `GET /api/tunes/search`) | name only | name + notation, blended server-side |
| **My Tunes** filter (`mytunespage`) | name / notes / tune-id, client-side | + notation |
| **Session page → Tunes tab** (`sessionpage`) | name / tune-id, client-side | + notation |
| **Admin session-tunes tab** (`sessionadminpage`) | name / alias / type / key, client-side | + notation |
| **Offline** (`CeolOffline.searchTunes`) | name only | + notation, **incipit only** |
| Deep search (`TuneSearch.svelte`) | name + notation | unchanged behavior, now on the shared rules |

## How it works

### One definition of the rules, mirrored three times

"Is this query notation, and what does it match?" is decided in exactly one place per
runtime, and the three must agree or notation search silently stops matching:

- **SQL** — `abc_search_key(text)`, `schema/055_abc_search_index.sql`. Backs the index.
- **Python** — `abc_query_key` / `is_abc_friendly` / `abc_search_terms` / `ABC_MATCH_SQL`
  in `database.py`. Used by `_deep_search_core`, `search_tunes`, and `abc_filter_tunes`.
- **Browser** — `frontend/src/shared/abcquery.js`. Used by the live logger's local
  vocabulary index and by the three client-side filters. `static/js/offline_data.js`
  hand-copies it (it loads outside every Vite bundle and cannot import).

The normalization drops **grace notes `{…}`, chord symbols `"…"`, whitespace, and legacy
`!` line breaks**, then lowercases. The ornament stripping is new and matters: without it
`{g}A{d}A{e}A {g}ABc` could never be found by typing `AAABc`, which is what a player
actually types (~9% of settings carry such ornaments). Lowercasing means ABC's octave-case
convention is deliberately ignored — `GED` and `ged` find the same tune.

### Auto-blend, no new chrome

Notation is blended in the deep search's default `mixed` mode: a note-shaped query gets
notation matches alongside name matches, ranked **below** them, and rows that matched the
notation but not the name are flagged `abc_only` so the UI can mark them with a ♪. No
"By name / By ABC" tabs were added to these boxes — only the deep search has those, and it
keeps them.

The "is this notation?" test is deliberately permissive: plenty of real names (`Cabbage`,
`Bee`, `Face`) are made only of note letters. That is fine — a false positive costs a few
extra rows ranked below the name matches, never a wrong answer.

### The three client-side filters: server lookup for ids

My Tunes, the session Tunes tab and the admin tunes tab all filter a list the page has
**already loaded**. Names match in the browser; notation cannot, because the full ABC is
far too large to ship with a page (a 300-tune list would gain 150–250KB). So:

`POST /api/tunes/abc-filter  {q, tune_ids} -> {tune_ids}`

The client posts the ids it is showing and unions the matching subset into the same filter
pass. One endpoint for all three — the caller already knows its own list, so there is no
scope to model and no per-surface auth story. `shared/abcfilter.svelte.js` is the single
client mechanism (debounce, stale-response guard, no request at all for a non-notation
query, empty result on any failure so the filter silently degrades to name-only).

The endpoint is **`@public_api`** by necessity, not oversight: session pages are publicly
viewable, so their Tunes tab must filter for logged-out visitors. It reveals only which
*public* catalog tunes match *public* catalog notation, and only among ids the caller
already supplied.

## Behavior changes worth knowing

- **Minimum length 3 for blended notation search** (`ABC_MIN_QUERY_LEN`). Previously
  `mixed` mode had no floor, so a 1–2 character note-ish query notation-matched nearly the
  whole catalog. Three is also pg_trgm's floor for using the trigram index, and the number
  the live logger's client-side match has always used. Explicit `mode=abc` still honors
  whatever was typed.
- **Ornaments are now stripped**, so notation search finds strictly more than before.
- `/api/tunes/search` now returns `abc_only` on every row and accepts `mode=name|abc|mixed`
  (default `mixed`), matching the deep search's vocabulary. A pasted thesession.org link
  is a pointer, not a query — it never gets notation blended into it.
- `/api/tunes/search`'s result rows are now read **by column name**, not position. The old
  positional mapping (`session_idx = 6 if person_id else 4`) would have mis-mapped the
  moment another optional column appeared.

## Performance: the index is a prerequisite, not a follow-up

The old predicate was `REGEXP_REPLACE(abc,'\s','','g') ILIKE '%…%'` — a sequential scan of
`tune_setting` recomputing a regex per row. That was tolerable when only a deliberate deep
search reached it. It is not tolerable behind a public, every-page, debounced "Find a tune"
box, especially since ordinary *name* typing (`cabbage`, `bee`, `face`) trips the
notation test too.

`schema/055_abc_search_index.sql` mirrors what migration 026 did for names: one IMMUTABLE
normalization function used by **both** the index expression and the query, so the planner
matches them, plus a `pg_trgm` GIN index. **Apply the migration before deploying the code**
— `abc_search_key()` is a hard runtime dependency of every notation query.

## Offline is incipit-only

The offline bundle carries `incipit_abc`, never the full setting ABC, to bound the payload
(see `specs/current/logic/offline.md`). So offline a query matching bar 20 of a tune finds
nothing while online it does. Hits are flagged `abc_scope: 'incipit'` and the Find-a-tune
row says "opening bars" — under-answering visibly rather than quietly. No new bundle field
was added: the incipit keys are normalized on demand and memoized per tune, cleared on sync.

## Not done

- The three client-side filters do **not** match notation offline. `createAbcMatcher`
  no-ops when the browser is offline and those filters fall back to name-only. Matching My
  Tunes' cached incipits locally would be a *second* mechanism; deliberately out of scope.
- `static/js/components/TuneSearchComponent.js` (the quarantined pill logger's search) was
  left alone. It picks up the server blend for free through `/api/tunes/search`.
