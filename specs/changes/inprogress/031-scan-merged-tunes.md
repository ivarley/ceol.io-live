# Spec 031: Sync Merged Tunes from thesession.org

## Overview

Because `tune.tune_id` *is* the thesession.org tune id, tunes merged upstream
on thesession.org silently go stale in our database: we keep logging against
the old id while thesession.org 301-redirects it to a new one. Spec 030 built
the machinery to merge a *known* pair (tombstone, `merge_tune_ids()`, admin
preview/confirm at `/admin/tunes/merge`). This spec finds the unknown pairs —
and applies them.

A **weekly background job** downloads thesession.org's weekly data dump,
diffs it against our tune ids, resolves where each vanished id went,
live-verifies the redirect, and **auto-applies the merge** through the spec-030
machinery. The admin merge page shows a **record** of what each run changed,
plus a **Run Now** button. The manual old-id/new-id merge form stays for
local-only merges.

## History / decisions

Rev 1 of this spec (built 2026-07-05) HEAD-scanned every local tune against the
live site (~10k requests, ~3h, resumable cursor) and presented a manual
punchlist; nothing merged automatically. The thesession.org site owner then
asked us to use the weekly data dumps instead and described the settings-diff
recipe; Ian decided to also auto-apply (an upstream merge is authoritative —
the app's premise is `tune_id` == thesession id — and spec 030 made applying
safe: name preservation, history rows, live-logger relink, no-chain guards).
Rev 1's punchlist, ignore table, and resume cursor were removed; rev 1 never
shipped, so its schema was edited in place rather than migrated.

Decisions:

1. **Detection source: the weekly data dumps**
   (github.com/adactio/TheSession-data, refreshed Sundays; suggested by the
   site owner). `csv/tunes.csv` is one row per *setting*
   (`tune_id,setting_id,name,type,...`, ~17 MB); `csv/aliases.csv` maps
   tune ids to alternate titles. One download replaces ~10k live requests.
   A dump with implausibly few tunes (`MIN_DUMP_TUNES`) aborts the run —
   a truncated file must not read as "everything merged".

2. **Resolution, for each local active tune id absent from the dump:**
   - *Settings-trace* (the site owner's recipe): our cached
     `tune_setting.setting_id`s found in the dump under exactly ONE other tune
     id → merge candidate, with target name + aliases straight from the dump.
     One live request (`verify_thesession_redirect`) re-verifies before acting,
     because the dump is up to a week stale. Settings split across multiple
     targets → fall through.
   - *Live check* (`check_tune`): HEAD, no-follow, redirect chain ≤3 hops,
     404 = deleted, 5xx/network retried 3× with backoff then recorded as an
     error. Also clears tunes imported locally after the Sunday cut (200 →
     alive). Only ~11% of local tunes have cached settings (bulk imports skip
     setting caching), so this fallback matters.
   - Live requests throttled by `THESESSION_SCAN_DELAY_MS` (default 1000 ms).
     Custom User-Agent identifying ceol.io + contact email. Steady-state
     traffic: the dump download + ~2 requests per actual upstream change.

3. **Apply automatically, one transaction per tune:** target not local →
   import in-transaction (`live_logging_routes._import_tune_for_live`);
   target locally tombstoned → resolve to its canonical (the proc forbids
   merging into a redirect); then the shared apply sequence
   (`tune_merge_scan_service.apply_merge`, also used by the manual endpoint):
   capture open live-logger rows → `merge_tune_ids(old, new, NULL)` (NULL =
   system) → emit `change_tune` events. An apply failure rolls back that tune
   only and records an error row.

4. **Record, not punchlist.** Results persist across runs (an applied merge
   can't be re-detected later — the rows ARE the record): `merged` with
   `applied_at`; `deleted` upstream informational, recorded once (first run
   that noticed); `error` latest-attempt-only, retried naturally next run.
   No ignore/dismiss machinery — nothing on the record needs action.

5. **Execution.** Weekly Render cron (`jobs/sync_thesession_merges.py`,
   Mondays 06:00 UTC) runs it synchronously; the admin page's Run Now spawns
   the same run in a daemon thread. Single active run enforced in the DB
   (status + fresh heartbeat, table-locked create). A killed thread leaves
   status `running` with a stale heartbeat (> 90 s); the next run starts
   fresh — no resume cursor (a full run is ~1 minute). Cancel flips the row
   status; the loop notices per candidate.

6. **Missing target on the manual form too:** the existing merge endpoint
   (`merge_tune`) imports a target absent from the local `tune` table on
   confirm (preview announces it), sharing the same import + apply code.

## Schema (`schema/031_merge_scan.sql`, mirrored in `full_schema.sql`)

- `tune_merge_scan` — one row per run: status
  (`running|completed|cancelled`), `total_count`, `checked_count`,
  `merged_count`, `applied_count`, `deleted_count`, `error_count`,
  `started_by_user_id` (NULL = cron), `started_at`, `heartbeat_at`,
  `finished_at`.
- `tune_merge_scan_result` — PK `(scan_id, tune_id)`, no FK on `tune_id`
  (row must survive its tune being merged): `result_type`
  (`merged|deleted|error`), `target_tune_id`, `target_name`,
  `target_aliases JSONB`, `detail`, `applied_at`, `checked_at`.

## API (system-admin gated)

| Endpoint | Behavior |
|----------|----------|
| `POST /api/admin/tunes/merge-scan` | Run the sync now. 409 while a run is going (fresh heartbeat). |
| `GET /api/admin/tunes/merge-scan` | Recent runs (≤26), newest first, each with its result rows (applied/imported flags, display names joined). Page polls every ~5 s while running. |
| `DELETE /api/admin/tunes/merge-scan` | Cancel the running sync. |

## Implementation map

| Piece | Where |
|-------|-------|
| Tables | `schema/031_merge_scan.sql`, mirrored in `schema/full_schema.sql` |
| Sync pipeline (dump fetch/parse, settings-trace, live check, verify, apply, record) | `services/tune_merge_scan_service.py` |
| Weekly job | `jobs/sync_thesession_merges.py` — `run_weekly_if_due()`, called from `jobs/check_active_sessions.py`. No cron service of its own; see [Scheduling](../../current/services/thesession-merge-sync.md#scheduling) |
| Run Now / record / cancel endpoints | `api_routes.py` (`start_merge_scan`, `get_merge_scan`, `cancel_merge_scan`) |
| Shared verify + apply (manual endpoint uses the same) | `tune_merge_scan_service.verify_thesession_redirect` / `.apply_merge`; `merge_tune` auto-import via `_import_tune_for_live` |
| Record UI: Run Now, running progress, runs newest-first | `templates/admin_tune_merge.html` |
| Docs | `specs/current/services/thesession-merge-sync.md`, `specs/current/data/tune-model.md` |

## Testing (`tests/integration/test_merge_scan_031.py`)

1. `check_tune`: 200 not stored, 301 target parsed + aliases fetched, chained
   redirects ≤3 hops, chain-too-long error, 404 deleted, network error retried
   then stored, 5xx retry recovery, alias-fetch failure tolerated.
2. Dump: parse (ids, setting map, aliases), truncated dump rejected.
3. Settings-trace: single target found; ambiguous/absent → None.
4. `run_sync`: full pipeline applies traced + live-resolved merges (target
   imported when missing, usage rows moved), records deleted/error, skips
   alive + fresh-import tunes with zero live requests for in-dump ids;
   stale trace (verify disagrees) falls back to live and applies nothing;
   apply failure rolls back and records error; truncated dump aborts leaving
   `running` (stale heartbeat semantics); cancel mid-run; second run dedupes
   deleted, replaces error, retains prior rows.
5. Endpoints: Run Now + 409, record payload (order, flags, aliases), cancel,
   non-admin 403.
6. Manual merge auto-import: preview announces, confirm imports+merges
   atomically, failed import rolls back both.
