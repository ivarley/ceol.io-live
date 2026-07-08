#!/usr/bin/env python3
"""
Sync thesession.org merges - Cron Job Script (spec 031)

Runs weekly (Mondays 06:00 UTC, after thesession.org's Sunday data-dump
refresh). Downloads the weekly dump, finds local tune ids that no longer
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
from datetime import datetime, timezone
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


def main():
    logger.info("=" * 80)
    logger.info("Starting thesession.org merge sync")
    logger.info(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 80)

    try:
        scan_id = create_run(started_by_user_id=None)
        if scan_id is None:
            # Another run (cron overlap or an admin's Run Now) is active.
            logger.info("A sync run is already in progress; skipping this invocation.")
            return

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

        # A run that didn't complete, or recorded errors, should alert (Render
        # flags non-zero exits). Errors retry naturally next week either way.
        if status != "completed" or errors > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error during thesession merge sync: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
