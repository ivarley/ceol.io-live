# thesession.org Merge Sync

Weekly job that mirrors upstream tune merges automatically (spec 031).

## Overview

**Location**: `jobs/sync_thesession_merges.py` (core logic in `services/tune_merge_scan_service.py`)
**Schedule**: Weekly, Mondays 06:00 UTC (thesession.org's data dumps refresh on Sundays)
**Purpose**: Because `tune.tune_id` *is* the thesession.org tune id, tunes merged
upstream go stale silently. This job finds them and applies the merges.
**Technology**: Python, piggybacked on the `ceol-io-active-sessions` cron —
**not** a service of its own. See [Scheduling](#scheduling).

## How It Works

1. **Download the weekly data dump** — `tunes.csv` (one row per *setting*:
   `tune_id, setting_id, name, ...`) and `aliases.csv` from
   github.com/adactio/TheSession-data. One 17 MB download replaces ~10k live
   requests (approach requested by the site owner). A dump with implausibly few
   tunes (`MIN_DUMP_TUNES`) aborts the run — a truncated file must not read as
   "everything merged".
2. **Diff** — every local active tune (`redirect_to_tune_id IS NULL`) whose id
   appears in the dump is alive; nothing stored. For each id *absent* from the
   dump:
   - **Settings-trace** (the site owner's recipe): its cached
     `tune_setting.setting_id`s found in the dump under exactly one other tune
     id → merge candidate, then ONE live request re-verifies the redirect
     before acting (guards against week-old dump staleness).
   - Otherwise a **live check** (HEAD, redirect-chain follow ≤3 hops, 3×
     retry): merged / deleted / error — and 200 clears tunes imported locally
     after the Sunday cut.
3. **Apply** — each confirmed merge runs in one transaction: import the target
   from thesession.org if it isn't local
   (`live_logging_routes._import_tune_for_live`), resolve a locally-tombstoned
   target to its canonical tune, then the shared apply sequence
   (`tune_merge_scan_service.apply_merge`, also used by the manual
   `/api/admin/tunes/merge` endpoint): capture open live-logger rows →
   `merge_tune_ids()` (spec 030: moves references, preserves display names as
   aliases, writes history) → emit `change_tune` events so connected live
   screens relink.
4. **Record** — outcomes land in `tune_merge_scan` /
   `tune_merge_scan_result`, which persist across runs (an applied merge can't
   be re-detected later, so the rows ARE the durable record): `merged` with
   `applied_at`, `deleted` upstream (recorded once, first run that noticed),
   `error` (latest attempt only; retried next run).

Steady-state traffic to thesession.org: the dump download plus ~2 requests per
tune that actually changed. Live requests are throttled by
`THESESSION_SCAN_DELAY_MS` (default 1000 ms).

## Admin UI

`/admin/tunes/merge` (system admins) shows the record — runs newest-first with
each run's applied merges, deletions noticed, and errors — plus a **Run Now**
button that spawns the same run in a background thread (single active run
enforced in the DB; a dead thread leaves a stale heartbeat > 90 s and the next
run starts fresh). The manual old-id/new-id merge form on the same page remains
for local-only merges and imports a missing target on confirm.

## API

| Endpoint | Behavior |
|----------|----------|
| `POST /api/admin/tunes/merge-scan` | Run now. 409 while a run is going (fresh heartbeat). |
| `GET /api/admin/tunes/merge-scan` | Recent runs (≤26) with their result rows. |
| `DELETE /api/admin/tunes/merge-scan` | Cancel the running sync. |

## Scheduling

There is no `ceol-io-thesession-merge-sync` cron service. One was declared in
`render.yaml` when this feature shipped and never created — `render.yaml` is
dashboard-mirroring documentation, not an applied blueprint — so the sync did not
run once between 2026-07-08 and 2026-08-19.

Rather than pay for a second cron service to fire 52 times a year, it rides on
the one Ceol already has. `jobs/check_active_sessions.py` calls
`run_weekly_if_due()` at the end of every run; that cron fires at
`14,29,44,59 * * * *`, so it passes through the Monday 06:00 UTC window every
week.

`is_due()` requires **both**:

- **The window** — Monday, hour 06 UTC. This is what makes it weekly, and puts it
  after thesession.org's Sunday dump refresh.
- **≥ `SYNC_INTERVAL_DAYS` (6) since the last run started** (`MAX(started_at)` on
  `tune_merge_scan`). This stops all four of that hour's invocations from each
  starting a run, and recovers a week whose window was missed. Six days rather
  than seven so clock drift can't skip a week.

It runs **last** in that script, deliberately: it takes minutes when it fires,
and Render won't start the next run of a cron while the current one is going.
Session activation is the time-sensitive half and has already finished. The
window is ~1am Central, when no sessions are activating anyway.

The gate costs one `MAX()` per invocation and does nothing on 671 of every 672.

`create_run()` still refuses to start when a run is already active (fresh
heartbeat), so an admin's "Run Now" and this can't collide.

Failures are logged; a run that didn't complete or recorded errors makes the
active-sessions cron exit non-zero (Render alerts). Errors retry naturally the
following week.

## Local Development

```bash
python3 jobs/sync_thesession_merges.py   # runs against the .env database
```

Run standalone it syncs immediately, ignoring the schedule gate — the gate only
applies to `run_weekly_if_due()`.

Tests: `tests/integration/test_merge_scan_031.py` (HTTP fully mocked, including
the dump CSVs).

## Related Specs

- [Tune Model](../data/tune-model.md) - `redirect_to_tune_id`, scan tables
- [Tune Merge Gaps (spec 030)](../../changes/inprogress/030-tune-merge-gaps.md) - the merge machinery this applies
- [Scan spec (031)](../../changes/inprogress/031-scan-merged-tunes.md)
