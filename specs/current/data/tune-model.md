# Tune Model

Tune metadata, session-specific aliases, ABC notation cache.

## Three-Layer Structure

1. **tune** - Canonical tune from thesession.org
2. **session_tune** - Session-specific aliases and settings
3. **session_instance_tune** - Actual plays in session logs

## Tables

### tune
Canonical tune database.
- tune_id, thesession_tune_id (unique)
- name, type (jig, reel, etc.)
- tunebook_count (popularity from thesession.org)
- redirect_to_tune_id — merge tombstone (spec 016/030): set when this tune was merged
  into another (mirroring thesession.org merges, via `/admin/tunes/merge`). The
  `merge_tune_ids()` proc moves all references (incl. `person_tune_instrument` via FK
  cascade and `recording_tune_segment`), preserves the old display name as per-context
  aliases where none existed, and writes history rows. Reads follow the redirect
  (permalinks 301, APIs return `redirected_from`); stale writes remap transparently
  (`remapped_from`). No chains (DB trigger). Searches exclude tombstoned tunes.

### tune_merge_scan / tune_merge_scan_result
thesession.org merge sync (spec 031): a weekly cron job diffs local tune ids
against thesession's weekly data dump, resolves where merged-away ids went
(settings-trace through the dump, live redirect check otherwise), live-verifies,
and AUTO-APPLIES the merges via `merge_tune_ids()` — importing a missing target
from thesession.org in the same transaction. One `tune_merge_scan` row per run
(heartbeat detects a dead thread; stale > 90s means the next run starts fresh).
Result rows persist ACROSS runs — they are the record the admin page shows
(`merged` with `applied_at`, `deleted` upstream recorded once, `error` latest
attempt only, retried next run). Full pipeline:
[thesession.org Merge Sync](../services/thesession-merge-sync.md). Endpoints
(system-admin): `/api/admin/tunes/merge-scan` (POST run-now / GET record /
DELETE cancel).

### session_tune
Session-specific tune information — the session's **repertoire**. A `(session_id, tune_id)`
row means "this tune belongs to this session's list"; it feeds the fast-match vocabulary,
"in session" flags, and tune-list views. Enrolled as a side effect of logging any linked
tune, by **both** loggers: the old save path (`api_routes.py`) and the live logger's
`_enroll_session_tune` (spec 025). Merged/redirect tunes are never enrolled. The live
logger also **un-enrolls** when the last live play is deleted (spec 045), unless the row
is protected by `manually_added` or carries curation.
- session_tune_id, session_id, tune_id (nullable)
- tune_name, thesession_tune_id
- key (VARCHAR(20) - expanded to support "Amixolydian")
- alias (single alternative name)
- manually_added (BOOLEAN) — someone put this entry here on purpose (add-tune pane, admin
  copy, or curating its alias/key/setting), so the play-delete auto-cleanup skips it

### session_tune_alias
Multiple alternative names per tune at session.
- (session_id, session_tune_id, alias) composite PK

### tune_setting
ABC notation cache from thesession.org.
- setting_id, tune_id, key
- abc (text notation), image (PNG bytea)
- incipit_abc (first 2 bars), incipit_image (PNG bytea)
- cache_updated timestamp

### session_instance_tune
Logged tune plays (the actual session log).
- session_instance_tune_id, session_instance_id, tune_id (nullable), name
- order_position (VARCHAR(32) - base-62 fractional index for CRDT-compatible ordering)
- continues_set (boolean - true if continues previous tune in a set)
- started_by_person_id (FK to person, nullable) - Who started the set
- played_timestamp, inserted_timestamp
- key_override (VARCHAR(20)), setting_override

**Constraint**: tune_id IS NOT NULL OR name IS NOT NULL

## Set Management

**Set** = consecutive tunes played without pause
- continues_set = TRUE means tune continues previous tune
- Sets are implicit (no set_id, derived from continues_set sequence)
- started_by_person_id tracks who started the set (shown via clickable label)
- Clicking set label shows popout with set details and "Started By" selector

## ABC Integration

- Full ABC in tune_setting.abc
- Incipit (first 2 bars) in tune_setting.incipit_abc
- Rendered by ABC renderer service → stored as PNG bytea
- See [ABC Renderer](../services/abc-renderer.md)

**PNGs are rendered lazily, ABC is not.** A tune imported from thesession.org (the live
logger's add op and the My Tunes add pane both go through
`live_logging_routes._import_tune_for_live`) gets its `tune` row and default
`tune_setting` — ABC and incipit ABC — inside the add's transaction, but no images: a
render is an HTTP call to the abc-renderer service with a 15s timeout, twice, and no add
should block on that. The PNGs are drawn and cached on the first VIEW instead, by
whichever surface shows the notation:

- deep-search preview → `…/setting-image/<setting_id>?kind=incipit|full` (`_ensure_setting_image`)
- live logger → `…/incipit/<tune_id>` (`_ensure_incipit`, the tune's default setting)
- tune-detail drawer → the setting-image endpoint for the setting its payload resolved
  (`session_tune.setting_id`), fired automatically when the payload has ABC but no image

Each renders once and writes the PNG back to `tune_setting`, so it happens once per
setting for all viewers, ever. Anything still imageless (offline, renderer down, a
logged-out viewer) falls back to the ABC text, with **Generate Notation** as the manual
path. `api_routes.cache_default_tune_setting` is the eager sibling — it renders both
sizes synchronously and is still used where a tune row is created outside an add's
transaction.

## Key Operations

**Search**: GET /api/tunes/search?q=<query> - searches local (by name AND notation) + thesession.org.
Notation search normalizes through `abc_search_key` and is index-backed; see
[Tune Search](../logic/tune-logic.md#notation-abc-search).
**Link**: POST /api/sessions/<path>/<date_or_id>/match_tune - link to thesession.org
**Save Log**: POST /api/sessions/<path>/<date_or_id>/save_tunes - bulk save

**Scripts**:
- scripts/cache_missing_settings.py - Cache ABC notation
- scripts/refresh_tunebook_counts.py - Update popularity

## Related

- [Session Model](session-model.md) - session_instance_tune details
- [External APIs](../logic/external-apis.md) - thesession.org integration
- [ABC Renderer](../services/abc-renderer.md) - ABC to PNG conversion
