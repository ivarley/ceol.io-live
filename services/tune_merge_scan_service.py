"""
thesession.org merge sync (spec 031).

Because tune.tune_id IS the thesession.org tune id, tunes merged upstream go
stale silently. Rather than polling the live site per-tune (~10k requests),
this service works from thesession's weekly data dumps
(github.com/adactio/TheSession-data, updated Sundays — approach suggested by
the site owner):

  1. Download tunes.csv (one row per SETTING: tune_id, setting_id, name, ...)
     and aliases.csv. Every local tune id present in the dump is alive.
  2. For each local id ABSENT from the dump, resolve where it went:
       a. settings-trace — its cached tune_setting.setting_ids found in the
          dump under exactly one other tune id ("a changed tune ID means a
          duplicate was merged"); then ONE live request re-verifies the
          redirect before acting, guarding against dump staleness.
       b. otherwise a live check (HEAD, redirect-chain follow, retries) —
          which also clears tunes imported locally after the Sunday cut
          (200 -> alive, nothing recorded).
  3. Confirmed merges are APPLIED automatically: import the target from
     thesession if it isn't local (in the same transaction), then
     merge_tune_ids() — the spec-030 machinery that moves references,
     preserves display names, writes history, and relinks open live-logger
     screens. Deleted-upstream and error outcomes are recorded only.

Steady-state traffic: one GitHub download + a couple of polite requests per
tune that actually changed.

Execution: jobs/sync_thesession_merges.py runs run_sync() weekly (Render
cron); the admin merge page's Run Now button spawns it in a daemon thread.
Progress/heartbeat persist to the tune_merge_scan row; a killed run leaves a
stale heartbeat (> HEARTBEAT_STALE_SECONDS) and the next run simply starts
fresh. Result rows accumulate across runs — they are the record the admin
page displays (an applied merge can't be re-detected later).
"""

import os
import re
import csv
import json
import threading
import time
import sys

import requests

from database import get_db_connection

# Identify ourselves politely on every request we make.
USER_AGENT = "ceol.io merged-tune sync (https://ceol.io; contact: ian@ceol.io)"

TUNE_URL = "https://thesession.org/tunes/{tune_id}"
DUMP_TUNES_URL = "https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/tunes.csv"
DUMP_ALIASES_URL = "https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/aliases.csv"

REQUEST_TIMEOUT = 10       # seconds (per-tune requests)
DUMP_TIMEOUT = 120         # seconds (the tunes dump is ~17 MB)
MAX_REDIRECT_HOPS = 3      # A->B->C->D max; longer chains recorded as errors
MAX_RETRIES = 3            # same pattern as thesession_sync_service
RETRY_DELAY = 2            # seconds, doubled each retry
RETRY_BACKOFF = 2

# A truncated/garbage dump must not send us checking thousands of "missing"
# tunes against the live site: thesession has ~50k tunes, so anything smaller
# than this means the download is bad and the run should abort.
MIN_DUMP_TUNES = 10000

# A 'running' scan whose heartbeat is older than this is presumed dead (its
# thread was killed by a deploy/restart); a new run may start over it.
HEARTBEAT_STALE_SECONDS = 90

REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def scan_delay_seconds():
    """Inter-request delay for live thesession.org calls, tunable via env."""
    try:
        return max(0, int(os.environ.get("THESESSION_SCAN_DELAY_MS", "1000"))) / 1000.0
    except ValueError:
        return 1.0


class _Throttle:
    """Enforces the polite inter-request spacing across ALL requests a run
    makes against thesession.org (the GitHub dump download shares it too —
    it's just one more request)."""

    def __init__(self):
        self._last = 0.0

    def wait(self):
        delay = scan_delay_seconds()
        elapsed = time.monotonic() - self._last
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last = time.monotonic()


def _request_with_retry(method, url, throttle):
    """One throttled HTTP request, retried with exponential backoff on network
    errors and 5xx. Returns a response, or raises the last error after
    MAX_RETRIES attempts."""
    delay = RETRY_DELAY
    last_error = None
    for attempt in range(MAX_RETRIES):
        throttle.wait()
        try:
            resp = requests.request(
                method, url,
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code < 500:
                return resp
            last_error = RuntimeError(f"HTTP {resp.status_code}")
        except requests.RequestException as e:
            last_error = e
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)
            delay *= RETRY_BACKOFF
    raise last_error


# ---------------------------------------------------------------------------
# Live per-tune detection (fallback path; also the final say on redirects)
# ---------------------------------------------------------------------------

def check_tune(tune_id, throttle=None):
    """Classify one tune id against the live site.

    Returns None for a healthy 200, else a result-row dict:
      {result_type: 'merged'|'deleted'|'error',
       target_tune_id, target_name, target_aliases, detail}
    """
    throttle = throttle or _Throttle()
    current_id = tune_id
    try:
        resp = _request_with_retry("HEAD", TUNE_URL.format(tune_id=current_id), throttle)
    except Exception as e:
        return {"result_type": "error", "target_tune_id": None,
                "target_name": None, "target_aliases": None,
                "detail": f"{e} (after {MAX_RETRIES} attempts)"}

    if resp.status_code == 200:
        return None
    if resp.status_code == 404:
        return {"result_type": "deleted", "target_tune_id": None,
                "target_name": None, "target_aliases": None, "detail": "404"}
    if resp.status_code not in REDIRECT_STATUSES:
        return {"result_type": "error", "target_tune_id": None,
                "target_name": None, "target_aliases": None,
                "detail": f"HTTP {resp.status_code}"}

    # Merged: follow the Location chain to the final target.
    first_status = resp.status_code
    for _hop in range(MAX_REDIRECT_HOPS):
        m = re.search(r"/tunes/(\d+)", resp.headers.get("Location", ""))
        if not m:
            return {"result_type": "error", "target_tune_id": None,
                    "target_name": None, "target_aliases": None,
                    "detail": f"HTTP {resp.status_code} redirect to non-tune URL: "
                              f"{resp.headers.get('Location', '')!r}"}
        current_id = int(m.group(1))
        try:
            resp = _request_with_retry("HEAD", TUNE_URL.format(tune_id=current_id), throttle)
        except Exception as e:
            # Chain target unreachable: keep the id we did resolve, note the gap.
            return _merged_result(current_id, first_status, throttle,
                                  note=f"target check failed: {e}")
        if resp.status_code not in REDIRECT_STATUSES:
            break
    else:
        return {"result_type": "error", "target_tune_id": None,
                "target_name": None, "target_aliases": None,
                "detail": f"redirect chain longer than {MAX_REDIRECT_HOPS} hops"}

    if resp.status_code == 404:
        # Redirects to a tune that is itself gone — not mergeable; surface as error.
        return {"result_type": "error", "target_tune_id": current_id,
                "target_name": None, "target_aliases": None,
                "detail": f"redirect target #{current_id} is 404 on thesession.org"}

    return _merged_result(current_id, first_status, throttle)


def _merged_result(target_id, first_status, throttle, note=None):
    """Build a merged result row, fetching the target's canonical name +
    aliases for record display. A failed alias fetch never fails the row."""
    name, aliases = None, None
    try:
        resp = _request_with_retry(
            "GET", TUNE_URL.format(tune_id=target_id) + "?format=json", throttle)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name")
            aliases = data.get("aliases") or []
    except Exception:
        pass
    detail = f"HTTP {first_status}"
    if note:
        detail += f"; {note}"
    return {"result_type": "merged", "target_tune_id": target_id,
            "target_name": name,
            "target_aliases": json.dumps(aliases) if aliases is not None else None,
            "detail": detail}


def verify_thesession_redirect(old_tune_id, new_tune_id):
    """Ask thesession.org whether old_tune_id really redirects to new_tune_id
    (spec 030 #8; also the pre-apply guard for spec 031 auto-merges). Handles
    both a 30x redirect (Location: /tunes/<id>) and a 200 whose JSON id
    differs from the requested one. Never raises; returns
    {status: confirmed|no_redirect|mismatch|not_found|unreachable, message}.
    """
    url = TUNE_URL.format(tune_id=old_tune_id) + "?format=json"
    try:
        resp = requests.request("GET", url, timeout=5, allow_redirects=False,
                                headers={"User-Agent": USER_AGENT})
        if resp.status_code in REDIRECT_STATUSES:
            m = re.search(r"/tunes/(\d+)", resp.headers.get("Location", ""))
            final_id = int(m.group(1)) if m else None
        elif resp.status_code == 200:
            final_id = resp.json().get("id")
        elif resp.status_code == 404:
            return {"status": "not_found",
                    "message": f"thesession.org has no tune #{old_tune_id} - cannot verify this merge."}
        else:
            return {"status": "unreachable",
                    "message": f"thesession.org returned HTTP {resp.status_code} - could not verify this merge."}

        if final_id == new_tune_id:
            return {"status": "confirmed",
                    "message": f"Confirmed: thesession.org redirects tune #{old_tune_id} to #{new_tune_id}."}
        if final_id == old_tune_id:
            return {"status": "no_redirect",
                    "message": f"thesession.org does NOT redirect tune #{old_tune_id} - it is still a live tune there. Double-check the IDs before merging."}
        return {"status": "mismatch",
                "message": f"thesession.org redirects tune #{old_tune_id} to #{final_id}, not #{new_tune_id}. Double-check the IDs before merging."}
    except Exception:
        return {"status": "unreachable",
                "message": "Could not reach thesession.org to verify this merge."}


# ---------------------------------------------------------------------------
# Dump download + settings-trace
# ---------------------------------------------------------------------------

def _open_dump(url, throttle):
    """GET a dump file (streaming, redirects allowed), retried with backoff."""
    delay = RETRY_DELAY
    last_error = None
    for attempt in range(MAX_RETRIES):
        throttle.wait()
        try:
            resp = requests.request(
                "GET", url,
                stream=True,
                allow_redirects=True,
                timeout=DUMP_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code == 200:
                return resp
            last_error = RuntimeError(f"HTTP {resp.status_code} from {url}")
        except requests.RequestException as e:
            last_error = e
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)
            delay *= RETRY_BACKOFF
    raise last_error


def _fetch_dump(throttle):
    """Download and parse the weekly dumps.

    Returns (live_tune_ids, setting_map, aliases_map):
      live_tune_ids: set of every tune id present upstream
      setting_map:   setting_id -> (tune_id, tune_name)
      aliases_map:   tune_id -> [alias, ...]

    tunes.csv is one row per setting (tune_id,setting_id,name,type,...); the
    abc column contains quoted embedded newlines, which csv.reader handles
    (we never look at that column). Raises on a failed download or a dump too
    small to be real (MIN_DUMP_TUNES) — better to abort the run than to treat
    a truncated file as "everything got merged".
    """
    live_tune_ids = set()
    setting_map = {}
    resp = _open_dump(DUMP_TUNES_URL, throttle)
    reader = csv.reader(resp.iter_lines(decode_unicode=True))
    next(reader, None)  # header
    for row in reader:
        if len(row) < 3:
            continue
        try:
            tune_id, setting_id = int(row[0]), int(row[1])
        except ValueError:
            continue
        live_tune_ids.add(tune_id)
        setting_map[setting_id] = (tune_id, row[2])

    if len(live_tune_ids) < MIN_DUMP_TUNES:
        raise RuntimeError(
            f"tunes dump looks truncated ({len(live_tune_ids)} tunes < {MIN_DUMP_TUNES}); aborting run")

    aliases_map = {}
    resp = _open_dump(DUMP_ALIASES_URL, throttle)
    reader = csv.reader(resp.iter_lines(decode_unicode=True))
    next(reader, None)  # header
    for row in reader:
        if len(row) < 2:
            continue
        try:
            tune_id = int(row[0])
        except ValueError:
            continue
        aliases_map.setdefault(tune_id, []).append(row[1])

    return live_tune_ids, setting_map, aliases_map


def _trace_via_settings(cur, tune_id, setting_map, aliases_map):
    """The site owner's recipe: our cached setting ids for a vanished tune,
    found in the dump under exactly ONE other tune id, name where it went.
    Returns a merged result-row dict, or None (no cached settings, settings
    gone from the dump too, or settings split across multiple targets)."""
    cur.execute("SELECT setting_id FROM tune_setting WHERE tune_id = %s", (tune_id,))
    targets = {}
    for (setting_id,) in cur.fetchall():
        hit = setting_map.get(setting_id)
        if hit and hit[0] != tune_id:
            targets.setdefault(hit[0], hit[1])
    if len(targets) != 1:
        return None
    target_id, target_name = next(iter(targets.items()))
    return {"result_type": "merged", "target_tune_id": target_id,
            "target_name": target_name,
            "target_aliases": json.dumps(aliases_map.get(target_id, [])),
            "detail": "settings-trace (dump)"}


# ---------------------------------------------------------------------------
# Applying a merge (shared with the manual /api/admin/tunes/merge endpoint)
# ---------------------------------------------------------------------------

def apply_merge(cur, old_tune_id, new_tune_id, user_id=None):
    """Run the spec-030 apply sequence on the caller's cursor: capture the log
    rows live-logger clients may have open, merge_tune_ids(), then emit
    change_tune events so connected screens relink in place. The caller owns
    the transaction. Returns (proc_result_json, events_emitted)."""
    # Rows of the old tune in instances with feed activity in the last 24h —
    # anything older has no plausible SSE listeners (spec 030 #6).
    cur.execute("""
        SELECT sit.session_instance_id, sit.session_instance_tune_id
        FROM session_instance_tune sit
        WHERE sit.tune_id = %s AND sit.deleted = FALSE
          AND sit.session_instance_id IN (
            SELECT DISTINCT session_instance_id FROM session_event
            WHERE server_ts > (NOW() AT TIME ZONE 'UTC') - INTERVAL '24 hours'
          )
    """, (old_tune_id,))
    live_rows = cur.fetchall()

    cur.execute("SELECT merge_tune_ids(%s, %s, %s)", (old_tune_id, new_tune_id, user_id))
    result = cur.fetchone()[0]

    from live_logging_routes import emit_change_tune
    events_emitted = 0
    for instance_id, record_id in live_rows:
        if emit_change_tune(cur, instance_id, record_id, user_id):
            events_emitted += 1

    return result, events_emitted


def _apply_candidate(cur, tune_id, result):
    """Import-if-missing + merge for one confirmed candidate, on the caller's
    cursor/transaction. Mutates result's target fields if the local target was
    tombstoned (merge goes to its canonical). Returns detail-note string.
    Raises on failure (caller rolls back and records an error row)."""
    target = result["target_tune_id"]
    note = ""
    cur.execute("SELECT name, redirect_to_tune_id FROM tune WHERE tune_id = %s", (target,))
    row = cur.fetchone()
    if row is None:
        # Target not local: import it in THIS transaction (atomic with the merge).
        from live_logging_routes import _import_tune_for_live
        imported_name, _tune_type = _import_tune_for_live(cur, target, None)
        result["target_name"] = result["target_name"] or imported_name
        note = "; target imported"
    elif row[1] is not None:
        # thesession says A->B but local B is already tombstoned into C: merge
        # into canonical C (the proc forbids merging into a redirect).
        canonical = row[1]
        cur.execute("SELECT name FROM tune WHERE tune_id = %s", (canonical,))
        canon_row = cur.fetchone()
        note = f"; local #{target} already redirects to #{canonical}, merged there"
        result["target_tune_id"] = canonical
        result["target_name"] = canon_row[0] if canon_row else result["target_name"]
        target = canonical

    apply_merge(cur, tune_id, target, None)
    return note


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

def create_run(started_by_user_id=None):
    """Insert a 'running' tune_merge_scan row, unless one is already running
    with a fresh heartbeat. Returns scan_id, or None if a run is active.
    Serialized via a table lock — Gunicorn runs multiple workers."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("LOCK TABLE tune_merge_scan IN ACCESS EXCLUSIVE MODE")
        cur.execute(
            """
            SELECT 1 FROM tune_merge_scan
            WHERE status = 'running'
              AND heartbeat_at >= (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s)
            LIMIT 1
            """,
            (HEARTBEAT_STALE_SECONDS,),
        )
        if cur.fetchone():
            conn.rollback()
            return None
        cur.execute("SELECT COUNT(*) FROM tune WHERE redirect_to_tune_id IS NULL")
        total = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO tune_merge_scan (status, total_count, started_by_user_id)
            VALUES ('running', %s, %s)
            RETURNING scan_id
            """,
            (total, started_by_user_id),
        )
        scan_id = cur.fetchone()[0]
        conn.commit()
        return scan_id
    finally:
        conn.close()


def _heartbeat(conn, cur, scan_id):
    cur.execute(
        "UPDATE tune_merge_scan SET heartbeat_at = (NOW() AT TIME ZONE 'UTC') WHERE scan_id = %s",
        (scan_id,),
    )
    conn.commit()


def _record_result(cur, scan_id, tune_id, result, applied):
    """Insert this run's result row, maintaining the cross-run record rules:
    errors show only the latest attempt; a deleted tune is recorded once."""
    # Whatever happened now supersedes any previous error row for this tune.
    cur.execute(
        "DELETE FROM tune_merge_scan_result WHERE tune_id = %s AND result_type = 'error'",
        (tune_id,),
    )
    if result["result_type"] == "deleted":
        cur.execute(
            "SELECT 1 FROM tune_merge_scan_result WHERE tune_id = %s AND result_type = 'deleted' LIMIT 1",
            (tune_id,),
        )
        if cur.fetchone():
            return False
    cur.execute(
        """
        INSERT INTO tune_merge_scan_result
            (scan_id, tune_id, result_type, target_tune_id, target_name,
             target_aliases, detail, applied_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s THEN (NOW() AT TIME ZONE 'UTC') END)
        ON CONFLICT (scan_id, tune_id) DO UPDATE SET
            result_type = EXCLUDED.result_type,
            target_tune_id = EXCLUDED.target_tune_id,
            target_name = EXCLUDED.target_name,
            target_aliases = EXCLUDED.target_aliases,
            detail = EXCLUDED.detail,
            applied_at = EXCLUDED.applied_at,
            checked_at = (NOW() AT TIME ZONE 'UTC')
        """,
        (scan_id, tune_id, result["result_type"], result["target_tune_id"],
         result["target_name"], result["target_aliases"], result["detail"],
         applied),
    )
    return True


def run_sync(scan_id):
    """The sync run: dump diff -> resolve -> verify -> apply -> record.

    Exits when done or cancelled. On an unexpected error the scan row is left
    'running' with a stale heartbeat — the next run (cron or Run Now) starts
    fresh; nothing here is resumable state, results already recorded stay.
    """
    conn = get_db_connection()
    throttle = _Throttle()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM tune_merge_scan WHERE scan_id = %s", (scan_id,))
        row = cur.fetchone()
        if not row or row[0] != "running":
            return

        cur.execute(
            "SELECT tune_id FROM tune WHERE redirect_to_tune_id IS NULL ORDER BY tune_id")
        local_ids = [r[0] for r in cur.fetchall()]

        _heartbeat(conn, cur, scan_id)
        live_tune_ids, setting_map, aliases_map = _fetch_dump(throttle)

        candidates = [tid for tid in local_ids if tid not in live_tune_ids]
        cur.execute(
            """
            UPDATE tune_merge_scan
            SET checked_count = checked_count + %s, heartbeat_at = (NOW() AT TIME ZONE 'UTC')
            WHERE scan_id = %s
            """,
            (len(local_ids) - len(candidates), scan_id),
        )
        conn.commit()

        for tune_id in candidates:
            # Cancel check each candidate — Cancel flips the row's status from
            # any worker.
            cur.execute("SELECT status FROM tune_merge_scan WHERE scan_id = %s", (scan_id,))
            status_row = cur.fetchone()
            if not status_row or status_row[0] != "running":
                conn.commit()
                return

            # Resolve: settings-trace first (needs one live confirmation),
            # else the live check (the redirect it follows IS the confirmation).
            result = _trace_via_settings(cur, tune_id, setting_map, aliases_map)
            if result is not None:
                verdict = verify_thesession_redirect(tune_id, result["target_tune_id"])
                if verdict["status"] != "confirmed":
                    # Dump may be stale (target merged again, un-merged, ...):
                    # fall back to the live check for the current truth.
                    result = check_tune(tune_id, throttle)
            else:
                result = check_tune(tune_id, throttle)

            applied = False
            if result is not None and result["result_type"] == "merged":
                try:
                    note = _apply_candidate(cur, tune_id, result)
                    result["detail"] = (result["detail"] or "") + note + "; applied"
                    applied = True
                except Exception as e:
                    conn.rollback()
                    result = {"result_type": "error", "target_tune_id": result["target_tune_id"],
                              "target_name": result["target_name"],
                              "target_aliases": result["target_aliases"],
                              "detail": f"merge apply failed: {e}"}

            recorded = False
            if result is not None:
                recorded = _record_result(cur, scan_id, tune_id, result, applied)
            cur.execute(
                """
                UPDATE tune_merge_scan SET
                    checked_count = checked_count + 1,
                    merged_count = merged_count + %s,
                    applied_count = applied_count + %s,
                    deleted_count = deleted_count + %s,
                    error_count = error_count + %s,
                    heartbeat_at = (NOW() AT TIME ZONE 'UTC')
                WHERE scan_id = %s
                """,
                (1 if result and result["result_type"] == "merged" else 0,
                 1 if applied else 0,
                 # A tune already recorded as deleted by an earlier run is old
                 # news — it shouldn't reappear in every weekly summary.
                 1 if recorded and result["result_type"] == "deleted" else 0,
                 1 if result and result["result_type"] == "error" else 0,
                 scan_id),
            )
            conn.commit()

        cur.execute(
            """
            UPDATE tune_merge_scan
            SET status = 'completed', finished_at = (NOW() AT TIME ZONE 'UTC'),
                heartbeat_at = (NOW() AT TIME ZONE 'UTC')
            WHERE scan_id = %s AND status = 'running'
            """,
            (scan_id,),
        )
        conn.commit()
    except Exception as e:
        # Deliberately no status flip: the stale heartbeat is the crash signal.
        print(f"[tune_merge_sync] run {scan_id} died: {e}", file=sys.stderr)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def start_scan_thread(scan_id):
    """Fire-and-forget worker thread for a run row already marked 'running'
    (the admin page's Run Now)."""
    t = threading.Thread(target=run_sync, args=(scan_id,), daemon=True,
                         name=f"tune-merge-sync-{scan_id}")
    t.start()
    return t
