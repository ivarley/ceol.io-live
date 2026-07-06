"""
Merged-tune scan against thesession.org (spec 031).

Because tune.tune_id IS the thesession.org tune id, tunes merged upstream go
stale silently. This service walks every non-tombstoned local tune id and asks
thesession.org what became of it:

    HEAD https://thesession.org/tunes/<id>   (allow_redirects=False)

    200  -> fine; not stored
    3xx  -> merged upstream; follow the Location chain (<= MAX_REDIRECT_HOPS)
            to the final target, then GET its JSON once to record the target's
            canonical name + aliases for the punchlist
    404  -> deleted upstream; stored as informational
    5xx / network error -> retried with exponential backoff, then stored as an
            error row (naturally retried by the next scan)

Nothing is ever merged automatically — results land in tune_merge_scan_result
and the admin merges pair-by-pair through the spec-030 preview/confirm flow.

Execution model: the start endpoint spawns run_scan() in a daemon thread. Every
iteration persists cursor + counters + heartbeat to the tune_merge_scan row and
re-reads status, so Cancel works from any Gunicorn worker and a deploy/restart
that kills the thread just leaves a stale heartbeat (> HEARTBEAT_STALE_SECONDS)
that the UI detects and offers to Resume. All requests are sequential, spaced
THESESSION_SCAN_DELAY_MS apart (default 1000ms; ~3h for 10k tunes).
"""

import os
import re
import json
import threading
import time
import sys

import requests

from database import get_db_connection

# Identify ourselves politely; thesession.org gets ~10k requests per scan.
USER_AGENT = "ceol.io merged-tune scan (https://ceol.io; contact: ian@ceol.io)"

TUNE_URL = "https://thesession.org/tunes/{tune_id}"
REQUEST_TIMEOUT = 10       # seconds
MAX_REDIRECT_HOPS = 3      # A->B->C->D max; longer chains stored as errors
MAX_RETRIES = 3            # same pattern as thesession_sync_service
RETRY_DELAY = 2            # seconds, doubled each retry
RETRY_BACKOFF = 2

# A 'running' scan whose heartbeat is older than this is presumed dead (its
# thread was killed by a deploy/restart) and may be resumed or replaced.
HEARTBEAT_STALE_SECONDS = 90

REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def scan_delay_seconds():
    """Inter-request delay, tunable via env without a deploy (spec 031 #3)."""
    try:
        return max(0, int(os.environ.get("THESESSION_SCAN_DELAY_MS", "1000"))) / 1000.0
    except ValueError:
        return 1.0


class _Throttle:
    """Enforces the polite inter-request spacing across ALL requests a scan
    makes (HEADs, chain hops, and alias GETs alike)."""

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
    errors and 5xx (the retryable failures). Returns a response, or raises the
    last error after MAX_RETRIES attempts."""
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


def check_tune(tune_id, throttle=None):
    """Classify one tune id against thesession.org.

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
    aliases for punchlist display. A failed alias fetch never fails the row
    (spec 031 testing #10)."""
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


def run_scan(scan_id):
    """Thread body: walk all non-tombstoned tune ids above the scan's cursor,
    persisting progress every iteration. Exits when done, cancelled, or on an
    unexpected error (leaving a stale heartbeat for the UI's Resume offer)."""
    conn = get_db_connection()
    throttle = _Throttle()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, cursor_tune_id FROM tune_merge_scan WHERE scan_id = %s", (scan_id,))
        row = cur.fetchone()
        if not row or row[0] != "running":
            return
        cursor_tune_id = row[1]

        # Snapshot the worklist once; ids added mid-scan wait for the next scan.
        cur.execute(
            """
            SELECT tune_id FROM tune
            WHERE redirect_to_tune_id IS NULL AND (%s::integer IS NULL OR tune_id > %s)
            ORDER BY tune_id
            """,
            (cursor_tune_id, cursor_tune_id),
        )
        tune_ids = [r[0] for r in cur.fetchall()]

        for tune_id in tune_ids:
            # Cancel check each iteration — Cancel flips the row's status from
            # any worker; we notice within one request cycle.
            cur.execute("SELECT status FROM tune_merge_scan WHERE scan_id = %s", (scan_id,))
            status_row = cur.fetchone()
            if not status_row or status_row[0] != "running":
                conn.commit()
                return

            result = check_tune(tune_id, throttle)

            if result is not None:
                cur.execute(
                    """
                    INSERT INTO tune_merge_scan_result
                        (scan_id, tune_id, result_type, target_tune_id, target_name, target_aliases, detail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scan_id, tune_id) DO UPDATE SET
                        result_type = EXCLUDED.result_type,
                        target_tune_id = EXCLUDED.target_tune_id,
                        target_name = EXCLUDED.target_name,
                        target_aliases = EXCLUDED.target_aliases,
                        detail = EXCLUDED.detail,
                        checked_at = (NOW() AT TIME ZONE 'UTC')
                    """,
                    (scan_id, tune_id, result["result_type"], result["target_tune_id"],
                     result["target_name"], result["target_aliases"], result["detail"]),
                )
            cur.execute(
                """
                UPDATE tune_merge_scan SET
                    cursor_tune_id = %s,
                    checked_count = checked_count + 1,
                    merged_count = merged_count + %s,
                    deleted_count = deleted_count + %s,
                    error_count = error_count + %s,
                    heartbeat_at = (NOW() AT TIME ZONE 'UTC')
                WHERE scan_id = %s
                """,
                (tune_id,
                 1 if result and result["result_type"] == "merged" else 0,
                 1 if result and result["result_type"] == "deleted" else 0,
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
        # Deliberately no status flip: the stale heartbeat is the crash signal,
        # and Resume picks up from the persisted cursor.
        print(f"[tune_merge_scan] scan {scan_id} died: {e}", file=sys.stderr)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def start_scan_thread(scan_id):
    """Fire-and-forget worker thread for a scan row already marked 'running'."""
    t = threading.Thread(target=run_scan, args=(scan_id,), daemon=True,
                         name=f"tune-merge-scan-{scan_id}")
    t.start()
    return t
