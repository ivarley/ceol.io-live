#!/usr/bin/env python3
"""
One-off migration: canonicalize person_instrument.instrument values.

Historically instruments were stored inconsistently -- mostly lowercase (from the
`.strip().lower()` API paths) but Title Case from the profile-setup page, plus
arbitrary free text. Per-instrument tune status now keys off instrument identity,
so this rewrites every stored instrument to the single canonical vocabulary in
instruments.py (Title Case), de-duping case-insensitively per person.

Mapping is `instruments.normalize_instrument`:
  - canonical / known-alias values  -> canonical Title Case (e.g. "tin whistle" -> "Whistle")
  - everything else                 -> kept verbatim as an "Other" free-text instrument
Note: plain "accordion" resolves to "Button Accordion" (trad default). Those rows
are printed under "REVIEW" so you can eyeball them -- a player may actually mean
piano accordion.

Per person we delete rows whose exact value is not a canonical target and insert
any missing canonical targets, writing person_instrument_history rows for both.
(Renamed rows get a fresh created_date; instrument created_date is low-value.)

Idempotent: a second run finds everything already canonical and changes 0 rows.

Connection: set DATABASE_URL inline so creds never linger, or fall back to the
app's PG* env vars.

Usage:
    DATABASE_URL='postgres://...' python3 scripts/migrate_canonicalize_instruments.py --dry-run
    python3 scripts/migrate_canonicalize_instruments.py            # apply, prompt before commit
    python3 scripts/migrate_canonicalize_instruments.py --yes      # apply without prompting
    python3 scripts/migrate_canonicalize_instruments.py --user-id 1  # attribute history to a user
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, save_to_history
from instruments import normalize_instrument

# Lowercase originals that map somewhere non-obvious and deserve a human glance.
_REVIEW_ORIGINALS = {"accordion", "box", "melodeon", "pipes"}


def build_plan(cur):
    """Return (deletes, inserts, reviews).

    deletes / inserts are lists of (person_id, instrument).
    reviews are (person_id, original, canonical) for ambiguous remaps.
    """
    cur.execute("SELECT person_id, instrument FROM person_instrument ORDER BY person_id")
    rows = cur.fetchall()

    by_person = {}
    for person_id, instrument in rows:
        by_person.setdefault(person_id, []).append(instrument)

    deletes, inserts, reviews = [], [], []
    for person_id, originals in by_person.items():
        current = set(originals)
        targets = []
        seen = set()
        for original in originals:
            canon = normalize_instrument(original)
            if canon is None:
                continue
            key = canon.lower()
            if key not in seen:
                seen.add(key)
                targets.append(canon)
            if canon != original and original.strip().lower() in _REVIEW_ORIGINALS:
                reviews.append((person_id, original, canon))
        target_set = set(targets)

        for instrument in current - target_set:
            deletes.append((person_id, instrument))
        for instrument in target_set - current:
            inserts.append((person_id, instrument))

    return deletes, inserts, reviews


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    parser.add_argument("--yes", action="store_true", help="apply without prompting")
    parser.add_argument("--user-id", type=int, default=None, help="attribute history to this user")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        deletes, inserts, reviews = build_plan(cur)

        print(f"Rows to delete (non-canonical / duplicate): {len(deletes)}")
        for person_id, instrument in sorted(deletes):
            print(f"  - person {person_id}: DELETE {instrument!r}")
        print(f"Rows to insert (canonical): {len(inserts)}")
        for person_id, instrument in sorted(inserts):
            print(f"  + person {person_id}: INSERT {instrument!r}")
        if reviews:
            print(f"\nREVIEW -- ambiguous remaps ({len(reviews)}):")
            for person_id, original, canon in sorted(reviews):
                print(f"  ? person {person_id}: {original!r} -> {canon!r}")

        if args.dry_run:
            print("\n[dry-run] no changes made.")
            return

        if not deletes and not inserts:
            print("\nNothing to change; already canonical.")
            return

        if not args.yes:
            resp = input(f"\nApply {len(deletes)} deletes + {len(inserts)} inserts? [y/N] ")
            if resp.strip().lower() not in ("y", "yes"):
                print("Aborted.")
                return

        cur.execute("BEGIN")
        for person_id, instrument in deletes:
            save_to_history(cur, "person_instrument", "DELETE",
                            (person_id, instrument), user_id=args.user_id)
            cur.execute(
                "DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s",
                (person_id, instrument),
            )
        for person_id, instrument in inserts:
            cur.execute(
                """INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                   VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                   ON CONFLICT (person_id, instrument) DO NOTHING""",
                (person_id, instrument, args.user_id),
            )
            save_to_history(cur, "person_instrument", "INSERT",
                            (person_id, instrument), user_id=args.user_id)
        conn.commit()
        print(f"\nDone: {len(deletes)} deleted, {len(inserts)} inserted.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
