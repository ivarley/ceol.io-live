#!/usr/bin/env python3
"""
Find -- and, per instance, repack -- overgrown session_instance_tune.order_position keys.

Why: order_position is a fractional index (fractional_indexing.py) in a VARCHAR(32)
column. Until September 2026 the midpoint between two ADJACENT keys was made by
appending a character, so inserting repeatedly in the same gap -- the segmenter's
pattern: every tune after the last one, before the same follower -- grew the key by
one character per insert, and the 32nd tune of a session hit the column limit
(a 500 on POST /api/recordings/<id>/segments). The generator now bisects the
suffix instead, about five inserts per character, so new inserts are fine even
after a long key. Existing long keys are VALID and harmless: nothing needs to
change unless an instance is close enough to the limit that a few more inserts
in its longest gap would overflow. This script finds those, and can repack one
instance's keys into short, evenly spaced ones, preserving order exactly.

Repacking rewrites order_position for every row of the instance (tombstoned rows
included: they still occupy positions), with session_instance_tune_history rows
for auditability. Ops anchor on record ids, not keys, so nothing else refers to
the old values -- but a live-logging screen open on that instance holds the old
keys until it reloads, so repack when nobody is logging it.

Connection: set DATABASE_URL (a single connection string) per invocation, or fall
back to the app's PGHOST/PGDATABASE/... vars. Pass it inline so prod creds never linger:
    DATABASE_URL='postgres://...' python3 scripts/renumber_order_positions.py

Usage:
    python3 scripts/renumber_order_positions.py                      # report: instances by longest key
    python3 scripts/renumber_order_positions.py --min-length 12      # report threshold (default 16)
    python3 scripts/renumber_order_positions.py --renumber 499       # show the repack, no writes
    python3 scripts/renumber_order_positions.py --renumber 499 --yes # apply it
    python3 scripts/renumber_order_positions.py --renumber 499 --yes --user-id 1  # attribute history
"""

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, save_to_history  # noqa: E402
from fractional_indexing import ALPHABET, BASE, validate_position  # noqa: E402

COLUMN_LIMIT = 32


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def _encode(value, length):
    """Base-62 encode `value`, zero-padded on the left to `length` characters."""
    out = []
    for _ in range(length):
        out.append(ALPHABET[value % BASE])
        value //= BASE
    return "".join(reversed(out))


def evenly_spaced_keys(n):
    """`n` keys in ascending order, all the same (minimal) length, with the same
    gap between neighbours and at least as much room before the first and after
    the last -- so later inserts anywhere have equal headroom.

    Length is the smallest L with 62**L >= 8 * (n + 1): every gap is at least 8
    slots wide, so nudging a key off a trailing '0' (which validate_position
    forbids: nothing could ever go directly before it) can't collide with a
    neighbour."""
    length = 1
    while BASE**length < 8 * (n + 1):
        length += 1
    step = BASE**length // (n + 1)
    keys = []
    for i in range(1, n + 1):
        value = i * step
        if value % BASE == 0:
            value += 1
        keys.append(_encode(value, length))
    assert keys == sorted(keys) and len(set(keys)) == n
    assert all(validate_position(k) for k in keys)
    return keys


def report(cur, min_length):
    cur.execute(
        """
        SELECT sit.session_instance_id, s.name, si.date,
               COUNT(*) AS rows, MAX(LENGTH(sit.order_position)) AS longest
        FROM session_instance_tune sit
        JOIN session_instance si USING (session_instance_id)
        JOIN session s USING (session_id)
        WHERE sit.order_position IS NOT NULL
        GROUP BY sit.session_instance_id, s.name, si.date
        ORDER BY longest DESC, sit.session_instance_id
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("No session_instance_tune rows with an order_position.")
        return
    longest_overall = rows[0][4]
    histogram = {}
    for _iid, _name, _date, _n, longest in rows:
        histogram[longest] = histogram.get(longest, 0) + 1
    print(f"{len(rows)} instances; longest key anywhere is {longest_overall} of {COLUMN_LIMIT} characters.")
    print("Instances by longest key: " + ", ".join(f"{k}:{histogram[k]}" for k in sorted(histogram, reverse=True)))
    flagged = [r for r in rows if r[4] >= min_length]
    print()
    if not flagged:
        print(f"None at or above {min_length} characters. Nothing to repack.")
        return
    print(f"At or above {min_length} characters ({len(flagged)}):")
    print(f"  {'instance':>8}  {'longest':>7}  {'rows':>5}  {'date':<10}  session")
    for iid, name, date, n, longest in flagged:
        print(f"  {iid:>8}  {longest:>7}  {n:>5}  {str(date):<10}  {name}")
    print()
    print("Repack one with:  --renumber <instance>  (add --yes to write).")


def renumber(conn, cur, instance_id, apply, user_id):
    cur.execute(
        """
        SELECT session_instance_tune_id, order_position, record_type, deleted, COALESCE(name, '')
        FROM session_instance_tune
        WHERE session_instance_id = %s AND order_position IS NOT NULL
        ORDER BY order_position COLLATE "C", session_instance_tune_id
        """,
        (instance_id,),
    )
    rows = cur.fetchall()
    if not rows:
        print(f"Instance {instance_id}: no rows with an order_position.")
        return 1
    olds = [r[1] for r in rows]
    if olds != sorted(olds) or len(set(olds)) != len(olds):
        print(f"Instance {instance_id}: existing keys are not strictly ordered; refusing to touch it.")
        return 1

    news = evenly_spaced_keys(len(rows))
    longest = max(len(o) for o in olds)
    print(f"Instance {instance_id}: {len(rows)} rows, longest key {longest} -> {len(news[0])} characters.")
    print(f"  {'id':>8}  {'type':<5}  {'old':<34}  {'new':<6}  name")
    for (rid, old, rtype, deleted, name), new in zip(rows, news):
        flag = " (deleted)" if deleted else ""
        print(f"  {rid:>8}  {rtype:<5}  {old:<34}  {new:<6}  {name}{flag}")

    if not apply:
        print("\nDry run: nothing written. Add --yes to apply.")
        return 0

    for (rid, old, _rtype, _deleted, _name), new in zip(rows, news):
        if old == new:
            continue
        save_to_history(cur, "session_instance_tune", "UPDATE", rid, user_id=user_id)
        cur.execute(
            "UPDATE session_instance_tune SET order_position = %s, last_modified_date = NOW(), "
            "last_modified_user_id = COALESCE(%s, last_modified_user_id) "
            "WHERE session_instance_tune_id = %s",
            (new, user_id, rid),
        )
    conn.commit()
    print(f"\nRepacked {len(rows)} rows of instance {instance_id}.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--min-length", type=int, default=16, help="report instances whose longest key is at least this (default 16)"
    )
    parser.add_argument(
        "--renumber", type=int, metavar="INSTANCE_ID", help="repack this instance's keys (dry run unless --yes)"
    )
    parser.add_argument("--yes", action="store_true", help="with --renumber: write the new keys")
    parser.add_argument("--user-id", type=int, default=None, help="with --yes: attribute the history rows to this user")
    args = parser.parse_args()

    conn = _connect()
    try:
        cur = conn.cursor()
        if args.renumber is None:
            report(cur, args.min_length)
            return 0
        return renumber(conn, cur, args.renumber, args.yes, args.user_id)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
