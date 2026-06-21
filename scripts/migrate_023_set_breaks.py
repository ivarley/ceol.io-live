#!/usr/bin/env python3
"""
Migration 023 (CONTRACT step): backfill set-break records, then drop continues_set.

Run AFTER schema/023_set_break_records.sql (which adds the record_type column and
swaps the CHECK constraint).

For every session instance this inserts a record_type='break' row:
  - at each INTERIOR set boundary (immediately before each tune that currently has
    continues_set = false, except the first tune of the instance), and
  - a TRAILING break after the last tune of the instance.
Net effect: exactly one break per set, positioned immediately after the set.

Break order_position values are computed with the same audited fractional-index
helpers the app uses (fractional_indexing.py), so they sort correctly between
neighbours without renumbering existing tunes.

After backfilling, it verifies that segmenting by break rows reproduces the exact
set grouping the old continues_set booleans implied, then DROPS continues_set from
session_instance_tune and session_instance_tune_history.

The whole thing runs in a single transaction (Postgres DDL is transactional), so a
failure rolls back cleanly. It is idempotent: re-running after a successful run is a
no-op (continues_set already gone -> nothing to do).

Connection: set DATABASE_URL (a single connection string) per invocation, or fall back to
the app's PGHOST/PGDATABASE/... vars. Pass it inline so prod creds never linger in the shell:
    DATABASE_URL='postgres://...' python3 scripts/migrate_023_set_breaks.py --skip-drop

Usage:
    python3 scripts/migrate_023_set_breaks.py             # backfill + verify + drop continues_set
    python3 scripts/migrate_023_set_breaks.py --skip-drop # backfill + verify, KEEP continues_set
    python3 scripts/migrate_023_set_breaks.py --dry-run   # report, no writes

Safe prod sequence (no window where running code references a missing column);
substitute your prod URL for $PROD_URL inline on each command:
    1. psql "$PROD_URL" -f schema/023_set_break_records.sql                       (add record_type, swap CHECK)
    2. DATABASE_URL="$PROD_URL" python3 scripts/migrate_023_set_breaks.py --skip-drop  (backfill, keep continues_set)
    3. deploy new code (which no longer references continues_set)
    4. DATABASE_URL="$PROD_URL" python3 scripts/migrate_023_set_breaks.py         (re-verify, then drop continues_set)
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection
from fractional_indexing import generate_position_between, generate_append_position


def _connect():
    """Connect using DATABASE_URL if provided (single connection string), else the
    app's PGHOST/PGDATABASE/... environment variables. Pass the URL per invocation, e.g.
    `DATABASE_URL='postgres://...' python3 scripts/migrate_023_set_breaks.py` -- no exports."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def column_exists(cur, table, column):
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def run(dry_run=False, skip_drop=False):
    conn = _connect()
    cur = conn.cursor()

    try:
        if not column_exists(cur, "session_instance_tune", "record_type"):
            print("ERROR: record_type column missing. Run schema/023_set_break_records.sql first.")
            return 1

        if not column_exists(cur, "session_instance_tune", "continues_set"):
            print("continues_set already dropped -- migration already applied. Nothing to do.")
            return 0

        # Idempotency: if breaks already exist, the backfill was already run (e.g. a prior
        # --skip-drop pass). Skip the insert and go straight to verify (+ optional drop).
        cur.execute("SELECT COUNT(*) FROM session_instance_tune WHERE record_type = 'break'")
        already_backfilled = cur.fetchone()[0] > 0

        if already_backfilled:
            print("Break records already present -- skipping backfill.")
        else:
            # Pull every instance's rows in order. Only real tunes exist yet (no breaks).
            cur.execute(
                """
                SELECT session_instance_id, session_instance_tune_id, order_position, continues_set
                FROM session_instance_tune
                WHERE record_type = 'tune'
                ORDER BY session_instance_id, order_position
                """
            )
            rows = cur.fetchall()

            # Group rows by instance, preserving order_position order.
            instances = {}
            for instance_id, sit_id, pos, continues in rows:
                instances.setdefault(instance_id, []).append((sit_id, pos, continues))

            breaks_to_insert = []  # (instance_id, order_position)
            for instance_id, tunes in instances.items():
                if not tunes:
                    continue
                # Interior breaks: before each tune (except the first) whose continues_set is false.
                for idx in range(1, len(tunes)):
                    _, pos, continues = tunes[idx]
                    if not continues:
                        prev_pos = tunes[idx - 1][1]
                        break_pos = generate_position_between(prev_pos, pos)
                        breaks_to_insert.append((instance_id, break_pos))
                # Trailing break after the last tune.
                last_pos = tunes[-1][1]
                breaks_to_insert.append((instance_id, generate_append_position(last_pos)))

            print(
                f"Instances: {len(instances)} | tunes: {len(rows)} | "
                f"break rows to insert: {len(breaks_to_insert)}"
            )

            if dry_run:
                print("--dry-run: no changes written.")
                conn.rollback()
                return 0

            # Insert break rows. They carry no tune/name; record_type makes them legal.
            for instance_id, break_pos in breaks_to_insert:
                cur.execute(
                    """
                    INSERT INTO session_instance_tune
                        (session_instance_id, order_position, record_type, created_date, last_modified_date)
                    VALUES (%s, %s, 'break', NOW(), NOW())
                    """,
                    (instance_id, break_pos),
                )

        if dry_run:
            print("--dry-run: no changes written.")
            conn.rollback()
            return 0

        # Verify: segmentation by break rows must reproduce the old continues_set grouping.
        _verify_equivalence(cur)

        if skip_drop:
            conn.commit()
            print("Migration 023 backfill applied (continues_set KEPT; re-run without --skip-drop to drop it).")
            return 0

        # Contract: drop the now-unused boolean from table + history.
        cur.execute("ALTER TABLE session_instance_tune DROP COLUMN continues_set")
        cur.execute("ALTER TABLE session_instance_tune_history DROP COLUMN IF EXISTS continues_set")

        conn.commit()
        print("Migration 023 applied: breaks backfilled, continues_set dropped.")
        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"Migration FAILED, rolled back: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


def _verify_equivalence(cur):
    """Assert break-segmentation == old continues_set grouping for every instance.

    Old grouping: a new set starts at the first tune and at every continues_set=false tune.
    New grouping: walk rows in order; a 'break' closes the current set.
    We compare the ordered list of set sizes per instance.
    """
    cur.execute(
        """
        SELECT session_instance_id, order_position, record_type, continues_set
        FROM session_instance_tune
        ORDER BY session_instance_id, order_position
        """
    )
    per_instance = {}
    for instance_id, _pos, record_type, continues in cur.fetchall():
        per_instance.setdefault(instance_id, []).append((record_type, continues))

    mismatches = 0
    for instance_id, recs in per_instance.items():
        # Old: sizes of runs delimited by continues_set=false on tune rows.
        old_sizes = []
        for record_type, continues in recs:
            if record_type != "tune":
                continue
            if not continues:
                old_sizes.append(1)
            else:
                old_sizes[-1] += 1
        # New: sizes of tune runs delimited by break rows.
        new_sizes = []
        current = 0
        for record_type, _continues in recs:
            if record_type == "break":
                if current:
                    new_sizes.append(current)
                    current = 0
            else:
                current += 1
        if current:
            new_sizes.append(current)

        if old_sizes != new_sizes:
            mismatches += 1
            print(f"  MISMATCH instance {instance_id}: old={old_sizes} new={new_sizes}")

    if mismatches:
        raise RuntimeError(f"Backfill verification failed for {mismatches} instance(s)")
    print(f"Verification OK: break segmentation matches continues_set for {len(per_instance)} instances.")


if __name__ == "__main__":
    sys.exit(run(dry_run="--dry-run" in sys.argv, skip_drop="--skip-drop" in sys.argv))
