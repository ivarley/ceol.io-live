# Spec 031: Scan for Merged Tunes

## Overview

Because `tune.tune_id` *is* the thesession.org tune id, tunes merged upstream
on thesession.org silently go stale in our database: we keep logging against
the old id while thesession.org 301-redirects it to a new one. Spec 030 built
the machinery to merge a *known* pair (tombstone, `merge_tune_ids()`, admin
preview/confirm at `/admin/tunes/merge`). This spec finds the unknown pairs.

A new **"Scan for merged tunes"** section on the existing admin merge page
checks every local tune id against thesession.org, collects the ones that
redirect (merged) or 404 (deleted), and presents a **punchlist** for manual,
one-by-one merging through the existing preview/confirm flow. Nothing is ever
merged automatically.

Scale context: production has >10,000 non-tombstoned tunes; at the polite rate
below a full scan takes ~3 hours, so the design is resumable end-to-end.

## Decisions (interview outcomes)

1. **Placement & gating.** A new section on `/admin/tunes/merge`
   (`templates/admin_tune_merge.html`), visible to system admins only (same
   gate as the page). Controls: **Start scan**, **Cancel**, **Resume**; a
   progress bar (checked / total, hits so far); the punchlist below.

2. **Detection: HEAD, no follow.** For each tune id, `HEAD
   https://thesession.org/tunes/<id>` with `allow_redirects=False`
   (verified live: HEAD returns correct status codes; avoids downloading
   ~100 KB of HTML per tune, which matters across 10k+ requests):
   - **200** → fine; not stored.
   - **3xx** → merged; parse the new id from the `Location` header. Follow
     chained redirects up to 3 hops to reach the final target.
   - **404** → deleted upstream; stored as informational.
   - **Network error / 5xx** → retry 3× with exponential backoff (same
     pattern as `thesession_sync_service.py:33-82`), then store as an error
     row. Errors retry naturally on the next scan.

   For each **merged** hit, one extra `GET
   https://thesession.org/tunes/<target>?format=json` records the target's
   canonical name and aliases (for punchlist display and for the
   target-not-local case). Same rate limit applies.

3. **Rate limit: 1 request/second, sequential.** No concurrency. Delay is an
   env var (`THESESSION_SCAN_DELAY_MS`, default `1000`) so it's tunable
   without a deploy. Requests carry a custom `User-Agent` identifying
   ceol.io plus a contact email. ~3 h for 10k tunes.

4. **Execution: background thread + persisted cursor.** The Start button
   spawns a thread in the Flask worker that walks the id list at the rate
   limit. Every iteration persists progress (cursor + heartbeat timestamp +
   counters) to the scan row, so:
   - The page polls a status endpoint (~5 s) and works from any Gunicorn
     worker; the admin can close the tab and come back.
   - If a deploy/restart kills the thread, status stays `running` but the
     heartbeat goes stale (> ~90 s); the UI then offers **Resume**, which
     starts a fresh thread from the cursor. Resume is manual, not automatic.
   - **Cancel** sets the scan row's status; the thread checks it each
     iteration and exits.
   - Single active scan enforced in the DB (status + fresh heartbeat), not
     in-process — Gunicorn runs multiple workers.

5. **Scope.** All tunes `WHERE redirect_to_tune_id IS NULL`, ordered by
   `tune_id`; cursor = last checked id. Tunes added mid-scan behind the
   cursor are picked up by the next scan.

6. **Persistence: latest scan only.** Results are fully regenerable (a tune
   still merged upstream will be found again next scan), so starting a new
   scan wipes the previous scan's rows — with a confirm dialog when
   unactioned punchlist items exist. No scan-history UI.

7. **Dismissals persist.** Each punchlist row has an **Ignore** action for
   pairs the admin decides not to merge. Ignores live in their own table
   keyed by `(tune_id, target_tune_id)` — outside the scan results, so they
   survive scan wipes. `target_tune_id` NULL covers dismissing a 404 row. A
   dismissed pair stays hidden on all future scans unless the upstream
   redirect target changes (different pair → shows again). Collapsed
   "Ignored (N)" section with un-ignore.

8. **404s are informational.** Deleted-upstream tunes appear in a collapsed
   "Deleted on thesession (N)" section; no action offered (local history
   still references them), dismissable like merge rows.

9. **Punchlist rows.** Ordered by local play count descending (high-impact
   first). Each row shows:
   - old tune name + id → target name + id
   - badge: target is local vs. **will be imported**
   - local usage: # sessions (`session_tune`) and # plays
     (`session_instance_tune`, excluding `record_type = 'break'` rows)
   - the target's alternate titles from thesession (sanity check at a
     glance — e.g. seeing "Sonny Riordan's" listed under The Blue Ribbon)
   - actions: **Merge…** and **Ignore**

   **Merge…** prefills the existing old/new form and triggers the existing
   preview; spec 030's live re-verification against thesession.org remains
   the merge-time guardrail. Rows whose tune now has `redirect_to_tune_id`
   set render as done (computed by join at read time — no result mutation).
   If thesession says A→B but local B is already tombstoned into C, the row
   resolves to canonical C with a note (the proc forbids merging into a
   redirect).

10. **Missing target: auto-import on confirm.** The existing merge endpoint
    (`merge_tune`, `api_routes.py:10210`) gains one case: when `new_tune_id`
    isn't in the local `tune` table, preview reports "target will be imported
    from thesession.org as *<name>*", and confirm imports it (reusing
    `_import_tune_from_thesession`, `api_routes.py:3513`) then merges, in one
    transaction. One click from punchlist to done.

## Schema (`schema/031_merge_scan.sql`, mirrored in `full_schema.sql`)

```sql
-- One row per scan; "latest scan only" means at most one live row.
CREATE TABLE tune_merge_scan (
    scan_id             SERIAL PRIMARY KEY,
    status              TEXT NOT NULL CHECK (status IN ('running','completed','cancelled')),
    cursor_tune_id      INTEGER,            -- last checked id; resume point
    total_count         INTEGER NOT NULL,   -- snapshot at start
    checked_count       INTEGER NOT NULL DEFAULT 0,
    merged_count        INTEGER NOT NULL DEFAULT 0,
    deleted_count       INTEGER NOT NULL DEFAULT 0,
    error_count         INTEGER NOT NULL DEFAULT 0,
    started_by_user_id  INTEGER REFERENCES users(user_id),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ
);

-- Only interesting hits; 200s are not stored.
CREATE TABLE tune_merge_scan_result (
    scan_id         INTEGER NOT NULL REFERENCES tune_merge_scan(scan_id) ON DELETE CASCADE,
    tune_id         INTEGER NOT NULL,       -- no FK: row must survive the tune being merged
    result_type     TEXT NOT NULL CHECK (result_type IN ('merged','deleted','error')),
    target_tune_id  INTEGER,                -- final id after following chains (merged only)
    target_name     TEXT,
    target_aliases  JSONB,
    detail          TEXT,                   -- http status / error message
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (scan_id, tune_id)
);

-- Persistent dismissals; survives scan wipes.
CREATE TABLE tune_merge_ignore (
    tune_id             INTEGER NOT NULL,
    target_tune_id      INTEGER,            -- NULL = dismissed 404 row
    created_by_user_id  INTEGER REFERENCES users(user_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tune_id, target_tune_id)
);
```

(Exact column names/constraints may be adjusted at build time to match house
style; NULL-target uniqueness needs either the `UNIQUE` + a partial unique
index for the NULL case or `UNIQUE NULLS NOT DISTINCT` — decide at build.)

## API (all system-admin gated)

| Endpoint | Behavior |
|----------|----------|
| `POST /api/admin/tunes/merge-scan` | Start a scan. 409 if one is `running` with a fresh heartbeat. Wipes prior scan rows. `{"resume": true}` resumes the existing `running`-but-stale scan from its cursor instead. |
| `GET /api/admin/tunes/merge-scan` | Scan status + progress + full punchlist payload (results joined against `tune` for done-detection, usage counts, ignore table). |
| `DELETE /api/admin/tunes/merge-scan` | Cancel the running scan. |
| `POST /api/admin/tunes/merge-scan/ignore` | Body `{tune_id, target_tune_id?}` — dismiss a pair. |
| `DELETE /api/admin/tunes/merge-scan/ignore` | Un-dismiss a pair. |

The page polls the GET every ~5 s while status is `running`.

## Implementation map

| Piece | Where |
|-------|-------|
| Tables | `schema/031_merge_scan.sql`, mirrored in `schema/full_schema.sql` |
| Scan loop (thread body: HEAD loop, rate limit, retries, alias fetch, cursor/heartbeat writes, cancel check) | new `services/tune_merge_scan_service.py` |
| Scan endpoints + punchlist query | `api_routes.py` |
| Merge auto-import of missing target | `api_routes.py` `merge_tune` (~:10210), reusing `_import_tune_from_thesession` (~:3513) |
| Scan section UI: controls, progress polling, punchlist, prefill hook into existing preview JS | `templates/admin_tune_merge.html` |
| Rate/UA config | env `THESESSION_SCAN_DELAY_MS` (default 1000), User-Agent constant in the service |

## Testing

1. Detection: 200 (not stored), 301 → target parsed, chained 301s followed
   (≤3 hops), 404 stored as deleted, network error retried then stored.
2. Rate limit honored (delay between requests; env override works).
3. Resume: kill mid-scan → heartbeat goes stale → resume continues from
   cursor without re-fetching checked ids.
4. Cancel: thread exits promptly; status `cancelled`.
5. Double-start blocked (409) while heartbeat fresh; allowed after stale +
   resume path chosen instead.
6. New scan wipes old results; confirm dialog when unactioned items exist.
7. Ignore: hides row this scan and next scan; NULL-target ignore hides a 404
   row; un-ignore restores; a *changed* upstream target reappears despite an
   ignore on the old pair.
8. Punchlist: ordered by plays desc; break rows excluded from play counts;
   completed merges (redirect set) render done via join; locally-tombstoned
   target resolves to canonical with note.
9. Auto-import merge: target absent locally → preview announces import,
   confirm imports + merges atomically; failure mid-import rolls back both.
10. Alias fetch recorded for merged hits; missing/failed alias fetch doesn't
    fail the scan row.
