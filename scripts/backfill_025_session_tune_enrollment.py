#!/usr/bin/env python3
"""
Backfill 025: heal session_tune (session repertoire) enrollment gaps.

The new live logger historically never enrolled played tunes into session_tune the
way the old logger did (spec 025). This one-off, idempotent migration retroactively
enrolls every already-played *linked* tune into its session's repertoire, covering
gaps from any source -- not just the live logger.

What it enrolls (mirrors the old logger and the forward fix in live_logging_routes.py):
  - distinct (session_id, tune_id) for every session_instance_tune that is
      * linked            (tune_id IS NOT NULL)
      * a real tune row   (record_type = 'tune')
      * not tombstoned    (deleted = FALSE)
      * a canonical tune  (tune.redirect_to_tune_id IS NULL -- merged tunes excluded)
  - only where the pair is not already in session_tune.

Backfilled rows leave created_by_user_id / alias / setting_id NULL (created_by_user_id
is nullable). By default it also writes session_tune_history INSERT rows for
auditability, attributed to --user-id if given, else NULL (a system bulk heal). Pass
--no-history to skip.

Idempotent: uses ON CONFLICT (session_id, tune_id) DO NOTHING, so a second run adds 0.

Connection: set DATABASE_URL (a single connection string) per invocation, or fall back
to the app's PGHOST/PGDATABASE/... vars. Pass it inline so prod creds never linger:
    DATABASE_URL='postgres://...' python3 scripts/backfill_025_session_tune_enrollment.py --dry-run

Usage:
    python3 scripts/backfill_025_session_tune_enrollment.py --dry-run   # report count, no writes
    python3 scripts/backfill_025_session_tune_enrollment.py             # apply, prompt before commit
    python3 scripts/backfill_025_session_tune_enrollment.py --yes       # apply without prompting
    python3 scripts/backfill_025_session_tune_enrollment.py --no-history # skip history rows
    python3 scripts/backfill_025_session_tune_enrollment.py --user-id 1 # attribute history to a user
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, save_to_history

# Candidate (session_id, tune_id) pairs that should be in the repertoire.
_CANDIDATES = """
    SELECT DISTINCT si.session_id, sit.tune_id
    FROM session_instance_tune sit
    JOIN session_instance si USING (session_instance_id)
    JOIN tune t ON t.tune_id = sit.tune_id
    WHERE sit.tune_id IS NOT NULL
      AND sit.record_type = 'tune'
      AND sit.deleted = FALSE
      AND t.redirect_to_tune_id IS NULL
"""


def _connect():
    """Connect using DATABASE_URL if provided (single connection string), else the
    app's PGHOST/PGDATABASE/... environment variables."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def _would_add_count(cur):
    """Exact number of new session_tune rows the backfill would insert."""
    cur.execute(
        f"""
        SELECT COUNT(*) FROM ({_CANDIDATES}) cand
        WHERE NOT EXISTS (
            SELECT 1 FROM session_tune st
            WHERE st.session_id = cand.session_id AND st.tune_id = cand.tune_id
        )
        """
    )
    return cur.fetchone()[0]


def run(dry_run=False, assume_yes=False, write_history=True, user_id=None):
    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        would_add = _would_add_count(cur)
        print(f"session_tune rows that would be added: {would_add}")

        if dry_run:
            print("--dry-run: no changes written.")
            conn.rollback()
            return 0

        if would_add == 0:
            print("Nothing to backfill (repertoire already complete). Done.")
            conn.rollback()
            return 0

        # Insert and capture exactly the newly-added pairs (ON CONFLICT skips existing).
        cur.execute(
            f"""
            INSERT INTO session_tune (session_id, tune_id)
            {_CANDIDATES}
            ON CONFLICT (session_id, tune_id) DO NOTHING
            RETURNING session_id, tune_id
            """
        )
        inserted = cur.fetchall()
        print(f"Inserted {len(inserted)} session_tune rows (uncommitted).")

        if write_history:
            for session_id, tune_id in inserted:
                save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=user_id)
            print(f"Wrote {len(inserted)} session_tune_history rows"
                  f" (changed_by_user_id={user_id}).")
        else:
            print("--no-history: skipped session_tune_history rows.")

        if not assume_yes:
            reply = input("Commit these changes? [y/N] ").strip().lower()
            if reply not in ("y", "yes"):
                conn.rollback()
                print("Rolled back -- no changes committed.")
                return 0

        conn.commit()
        print(f"Committed: {len(inserted)} tunes enrolled into their session repertoires.")
        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"Backfill FAILED, rolled back: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    user_id = None
    if "--user-id" in sys.argv:
        idx = sys.argv.index("--user-id")
        user_id = int(sys.argv[idx + 1])
    sys.exit(
        run(
            dry_run="--dry-run" in sys.argv,
            assume_yes="--yes" in sys.argv,
            write_history="--no-history" not in sys.argv,
            user_id=user_id,
        )
    )
