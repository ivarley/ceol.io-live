#!/usr/bin/env python3
"""
Sync thesession.org merges - Cron Job Script (spec 031)

Runs weekly (Mondays 06:00 UTC, after thesession.org's Sunday data-dump
refresh) -- but NOT as a cron service of its own. This was declared in
render.yaml and never created, so it never ran once. Rather than pay for a
second cron to fire 52 times a year, `jobs/check_active_sessions.py` calls
run_weekly_if_due() at the end of its own run; that cron already comes round
four times an hour, so it passes through the Monday 06:00 window every week.
This file still runs standalone (`python3 jobs/sync_thesession_merges.py`) for
an on-demand sync, and ignores the schedule when it does.

Downloads the weekly dump, finds local tune ids that no longer
exist upstream, resolves where they went (settings-trace through the dump,
live redirect check otherwise), and auto-applies the merges via the spec-030
merge machinery. Deleted-upstream tunes and errors are recorded only.

The run is recorded in tune_merge_scan / tune_merge_scan_result; the admin
merge page (/admin/tunes/merge) shows the same record and can trigger a run
on demand.
"""

import sys
import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
# In production on Render, env vars should be set in the dashboard
load_dotenv()

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tune_merge_scan_service import create_run, run_sync
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# How long since the last run before another is due. Six days, not seven: the
# caller only passes through the Monday 06:00 window at :14/:29/:44/:59, and a
# full seven would let clock drift skip a whole week.
SYNC_INTERVAL_DAYS = 6


def _last_run_started_at():
    """When the most recent sync run started, or None if there has never been one."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(started_at) FROM tune_merge_scan")
        return cur.fetchone()[0]
    finally:
        conn.close()


def is_due(now_utc=None):
    """True if the weekly sync should run now.

    Two conditions, both needed. The window (Monday 06:00 UTC) is what makes it
    weekly and puts it after thesession.org's Sunday dump refresh; the interval
    check is what stops all four of that hour's cron invocations from starting a
    run, and covers a week the window was missed entirely.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.weekday() != 0 or now.hour != 6:
        return False

    last = _last_run_started_at()
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) >= timedelta(days=SYNC_INTERVAL_DAYS)


def run_weekly_if_due(now_utc=None):
    """Run the sync if this is its window. Returns True if a run happened.

    The gate is cheap -- one MAX() on a table with one row per week -- so the
    active-sessions cron can call it every fifteen minutes without noticing.
    """
    if not is_due(now_utc):
        return False
    logger.info("thesession.org merge sync is due; running it")
    run_sync_job()
    return True


def run_sync_job():
    """Do the sync and log what happened. Returns True if it came out clean."""
    logger.info("=" * 80)
    logger.info("Starting thesession.org merge sync")
    logger.info(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 80)

    try:
        scan_id = create_run(started_by_user_id=None)
        if scan_id is None:
            # Another run (cron overlap or an admin's Run Now) is active.
            logger.info("A sync run is already in progress; skipping this invocation.")
            return True

        run_sync(scan_id)

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, total_count, checked_count, merged_count,
                       applied_count, deleted_count, error_count
                FROM tune_merge_scan WHERE scan_id = %s
                """,
                (scan_id,),
            )
            status, total, checked, merged, applied, deleted, errors = cur.fetchone()
            cur.execute(
                """
                SELECT tune_id, result_type, target_tune_id, target_name, detail, applied_at
                FROM tune_merge_scan_result WHERE scan_id = %s ORDER BY tune_id
                """,
                (scan_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        logger.info("-" * 80)
        logger.info(f"Run {scan_id} {status}: {checked}/{total} checked, "
                    f"{merged} merged ({applied} applied), {deleted} deleted, {errors} errors")
        for tune_id, rtype, target, name, detail, applied_at in rows:
            if rtype == "merged":
                logger.info(f"  - #{tune_id} -> #{target} \"{name}\" "
                            f"({'applied' if applied_at else 'NOT applied'}; {detail})")
            else:
                logger.info(f"  - #{tune_id} {rtype}: {detail}")
        logger.info("=" * 80)

        # A run that didn't complete, or recorded errors, should alert. Errors
        # retry naturally next week either way.
        return status == "completed" and errors == 0

    except Exception as e:
        logger.error(f"Fatal error during thesession merge sync: {e}", exc_info=True)
        return False


def main():
    """Standalone entry point: sync now, regardless of the schedule."""
    return 0 if run_sync_job() else 1


if __name__ == '__main__':
    sys.exit(main())
