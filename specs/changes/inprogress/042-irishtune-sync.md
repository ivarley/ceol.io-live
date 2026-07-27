# 042: irishtune.info Playlist Sync — API Proposal (DRAFT)

Status: exploration / discussion draft. Nothing here is built. The "Proposed API"
section is written so it can be excerpted and sent to Alan Ng.

## Background & value proposition

irishtune.info (Alan Ng's Irish Traditional Music Tune Index) lets members keep
per-instrument **playlists** (repertoire lists) with learned/practiced tracking.
Alan has offered to build an API so ceol.io can sync with it. Our per-instrument
tune status work (person_tune + sparse person_tune_instrument overrides) removed
the main modeling mismatch.

The value proposition: whichever site is your "tune home" wins. If you already
use irishtune.info as your tune home / practice regime, syncing means ceol.io
knows what you know (better session logging, my-tunes, highlight modes). If you
center your tune list on ceol.io, syncing gives you irishtune.info's Practice
Machine and stats. Sync is **two-way from day one**.

Explicitly out of scope: practice data. Playing a tune at a session is not
"practicing" it, and ceol.io does not represent (or want to represent) practice
dates. `last_practiced` never syncs in either direction.

## irishtune.info data model (as observed 2026-07-19, logged in as ianvarley)

**Tune** (site-level, curated by Alan):
- `tune_id` (site-local integer, e.g. Sí Bheag Sí Mhór = 1768; unrelated to
  thesession.org ids)
- Canonical title + a long list of **alias titles** ("all published misspellings"),
  rhythm (Air, Reel, JigD, Hpipe, Slide, Polka, BDnce, …), mode (D Major,
  E Dorian, …), 8-bar phrase structure (AABB), first-2-bars ABC incipit,
  discography + bibliography.
- No thesession.org cross-reference anywhere on the site — the id mapping is
  entirely our problem.
- Alan merges musically-identical variants that thesession keeps separate, so
  the id mapping is not 1:1 (see Mapping below).

**Playlist** (per member; the "Instrument:" droplist):
- Free-named entities with their own ids (mine: Banjoo=6090, Concertina=5791,
  Piano Accordion=2617). Named after instruments by convention, but free text —
  not a canonical instrument enum.
- Publishing the list at /public/playlist/<username>/ is an opt-in choice.

**Playlist entry** (tune × playlist):
- `current` boolean ("I currently play this tune") — the Show filter has
  only-current / only-not-current / all
- `learned_on` date
- `last_practiced` date (drives the Practice Machine and freshness stats)

**Per tune × member** (shared across that member's playlists):
- `NotePublic` ("note shared with my friends"), `NotePrivate` ("note to myself only")
- `tags` — freeform tag list (playlist UI filters by include-any / exclude-any)

**Practice Machine / Stats**: assigns stalest N tunes per playlist, "mark practiced
now", freshness graph, per-playlist practice goal. All derived from
`last_practiced` per entry. (Not synced; listed for completeness.)

## Proposed API for irishtune.info (v1)

The full proposal lives in [`042 files/api-proposal-for-alan.md`](042%20files/api-proposal-for-alan.md) —
a standalone document addressed to Alan (human preamble explaining purpose and
usage, followed by an implementation spec he can hand to an AI coding
assistant). That file is the source of truth for the API surface; edit it, not
a copy here. Shape summary:

- Per-member Bearer token (generated/revoked on his Preferences page; pasted
  into ceol.io once). Scoped to that member's own playlist data only.
- `GET /api/v1/me` — username + playlist list (id, name, tune_count, published).
- `GET /api/v1/playlists/{id}` — full entry snapshot every time (no pagination,
  no change tracking; optional `updated_at`/`modified_since` only if his rows
  already have timestamps). Entries: tune_id, current, learned_on, and the
  per-tune×member note_public / note_private / tags denormalized in.
- `POST /api/v1/playlists/{id}/entries` — the only write: batch
  `{upsert:[…], remove:[…]}`, absolute-set per included field, idempotent,
  per-item errors. Never writes last_practiced.
- Tune index for mapping: weekly static dump (preferred) and/or
  `GET /api/v1/tunes?ids=…` batch — id, title, aliases, rhythm, mode,
  structure, incipit ABC.
- Non-requirements: no OAuth, webhooks, pagination, rate limiting, change
  feeds, or thesession.org awareness; ceol.io polls at most ~daily per
  connected member + manual "Sync now".

## ceol.io-side design sketch (our work, later spec)

### External tune mapping (multi-scheme, assertion-based)

Core principle (from discussion with Ian, echoing Alan's "friction between
conceptual tune universes"): **mappings are assertions, not identities**. Each
tune index is its own conceptual universe; a mapping row records a typed,
attributed claim of correspondence, and individual users may resolve
ambiguities differently for their own sync.

- `external_tune_map(scheme TEXT, external_id TEXT, tune_id INT FK → tune,
  relation ('same'|'variant'|'subsumes'), confidence REAL,
  asserted_by ('seed'|'admin'|'similarity'|'user'), created_at, created_by)`
  - PK (scheme, external_id, tune_id). `external_id` is TEXT because schemes
    differ (irishtune: integer id; tunearch: wiki page slug).
  - `subsumes` = the external tune covers this ceol tune and more (their
    universe merges what ours splits, or vice versa).
  - **Not 1:1 by design.** Sync rules:
    - Outbound (our tune → external id): fold. His entry is `current=true` if
      ANY mapped ceol tune is learned; `learned_on` = earliest.
    - Inbound (external id → our tune): unique mapping applies directly;
      fan-out (multiple rows) requires a per-user resolution (below) — first
      encounter parks in suspense and asks the user "which do you play — or all?".
- `person_external_tune_map(person_id, scheme, external_id, tune_id, …)` —
  sparse per-user overrides consulted before the global table (same pattern as
  person_tune_instrument). The global map is a *default*, not truth; admin fiat
  sets defaults, each user's sync operates in their own tune universe.
- **Statistical similarity ranks, never decides.** His incipits + alias lists
  vs our thesession ABC settings give melodic (pitch-interval n-gram) and title
  fuzzy scores. Used to: rank candidates in the admin mapping UI, auto-flag
  dubious mappings, and populate `confidence`. Contested cases are contested
  precisely because tunes are melodically close, so humans confirm defaults and
  users can override individually.

### Seed data

`specs/changes/inprogress/042 files/TheSession To IrishTune.info mapping -
Sheet1.csv` — 1,004 rows, all with irishtune.info id + thesession URL; 89 rows
also carry a tunearch.org URL (the **Traditional Tune Archive**, tunearch.org —
a distinct scheme from irishtune). More schemes may come later.

The raw export had 1,011 rows with 9 irishtune ids each mapped to two thesession
tunes; Ian resolved these 2026-07-19 (applied directly to the CSV):
- Removed wrong pairings: 105→ts15498, 245→ts338, 688→ts1244, 1373→ts9323,
  2052→ts9336, 4224→ts580, 5436→ts8668
- Remapped ts7514 (The King's Jig) from irishtune 801 → 2795 (Miss Monroe's
  Jig, whose aliases include "The Kings Jig"; verified on site)
- **Kept irishtune 300 → both ts2039 (Charlie Harris's, polka) and ts4620
  (John Blessings's, reel)** — genuinely both; seeds as `relation='subsumes'`.
  All other seed rows import as `relation='same'`, `asserted_by='seed'`.

### Account link & instrument mapping

- `irishtune_account(person_id PK, username, api_token, connected_at)`
- `irishtune_playlist_link(person_id, irishtune_playlist_id, instrument)` — at
  connect time the user maps each of his playlists to one of our instruments.
  Our instrument values are the canonical list from `instruments.py` **or free
  text ("Other")**, so playlist names outside our canonical list still map.

### Suspense queue

`irishtune_sync_suspense(person_id, irishtune_tune_id, irishtune_playlist_id,
payload jsonb, first_seen_at, status ('pending'|'applied'|'ignored'))` — inbound
entries whose tune has no (usable) mapping land here instead of silently
dropping. Admin mapping UI (fuzzy match on aliases/rhythm/incipit vs our tune
search) resolves the mapping; on insert into `external_tune_map`, all pending
suspense rows for that external id auto-apply for every user.

### Field / status mapping (decided)

| irishtune.info | ceol.io per-instrument status | direction |
|---|---|---|
| entry with `current=true` | `learned` | two-way |
| entry with `current=false` | `learning` | inbound; also pushed on demotion (below) |
| entry removed / absent | (no change on our side) | — |
| — | `want to learn` | never syncs |
| `learned_on` | `learned_date` | two-way |
| `last_practiced` | — | never syncs |
| `NotePrivate` | `person_tune.notes` | two-way |
| `NotePublic` | — | never syncs (no friends-facing notes on our side; must not publish private text) |
| `tags` | `person_tune.tags TEXT[]` (built, migration 044) | two-way; three-way **set merge** (apply each side's adds/removes), not ours-wins |

Notes/tags granularity matches ours: per tune × member on his side (global
across playlists) ⇔ our instrument-agnostic person_tune. No fan-out.

Tag normalization: our side normalizes (lowercase, whitespace→hyphen, dedupe —
`services/person_tune_service.normalize_tags`, mirrored in tunesheet logic.js).
His side may not. To avoid a rewrite loop, the sync must **diff on normalized
forms**: normalize his tags on ingest, and only push when the normalized sets
differ (never push solely to re-case/re-format a tag he already has).

Rationale: "want to learn" is aspirational (heard it, never tried learning);
"learning" is the middle state, so a tune slipped out of current repertoire on
his side lands there. We may eventually add "comfortable" (could start it at a
session) and "lapsed" states — UX space is tight, deferred.

Demotion (decided): when a previously-synced `learned` tune drops to
`learning` on our side, we push `current=false` — that is exactly what the flag
means on his side, and it prevents permanent drift / re-promotion loops. The
asymmetry that remains: our `learning` tunes that were never on his playlist
are NOT pushed onto it.

### Sync algorithm

Keep a per-(person, playlist) shadow of last-synced state; three-way merge
(base vs his vs ours) per field; where both sides changed, last-write-wins is
unavailable (no timestamps on his side) so ours wins + report in sync summary.
All merge complexity lives on our side. Manual "Sync now" button first;
scheduled sync later.

## Open questions

All ceol.io-side decisions are settled (recorded above). The six open questions
for Alan (timestamps, dump vs endpoint, token scheme, notes/tags storage &
exposure, remove-vs-current=false semantics, tag format rules) live in the
"Questions for you" section of
[`042 files/api-proposal-for-alan.md`](042%20files/api-proposal-for-alan.md).
