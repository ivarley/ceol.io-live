# thesession.org Merge Sync Cron Job

Weekly job that mirrors upstream tune merges automatically (spec 031).

## Overview

**Location**: `jobs/sync_thesession_merges.py` (core logic in `services/tune_merge_scan_service.py`)
**Schedule**: Weekly, Mondays 06:00 UTC (thesession.org's data dumps refresh on Sundays)
**Purpose**: Because `tune.tune_id` *is* the thesession.org tune id, tunes merged
upstream go stale silently. This job finds them and applies the merges.
**Technology**: Python cron job on Render (`ceol-io-thesession-merge-sync`)

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

## Deployment

Configured in `render.yaml`:

```yaml
- type: cron
  name: ceol-io-thesession-merge-sync
  env: python
  schedule: "0 6 * * 1"
  buildCommand: "pip install -r requirements.txt"
  startCommand: "python3 jobs/sync_thesession_merges.py"
```

Exit code 1 when the run didn't complete or recorded errors (Render alerts);
errors retry naturally the following week.

## Local Development

```bash
python3 jobs/sync_thesession_merges.py   # runs against the .env database
```

Tests: `tests/integration/test_merge_scan_031.py` (HTTP fully mocked, including
the dump CSVs).

## Related Specs

- [Tune Model](../data/tune-model.md) - `redirect_to_tune_id`, scan tables
- [Tune Merge Gaps (spec 030)](../../changes/inprogress/030-tune-merge-gaps.md) - the merge machinery this applies
- [Scan spec (031)](../../changes/inprogress/031-scan-merged-tunes.md)
