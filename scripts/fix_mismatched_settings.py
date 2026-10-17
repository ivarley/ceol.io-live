#!/usr/bin/env python3
"""
Clear every setting that belongs to a different tune than its row's.

session_tune.setting_id, session_instance_tune.setting_override and
person_tune.setting_id must name a setting of the row's own tune. Before
schema/064_setting_matches_tune.sql, a typed "1" (meaning "the first setting")
saved thesession.org's setting 1, which is Cooley's, and relinking a night's tune
kept the old tune's setting. Clearing the setting makes the row fall back to its
tune's first setting. Each change writes a history row.

Run AFTER schema/064_setting_matches_tune.sql. The default is a dry run: it prints
what it would clear and rolls back. --apply commits. A second run finds nothing.

Connection: DATABASE_URL, else the app's PGHOST/PGDATABASE/... variables.

    psql "$PROD_URL" -f schema/064_setting_matches_tune.sql
    DATABASE_URL="$PROD_URL" python3 scripts/fix_mismatched_settings.py           # dry run
    DATABASE_URL="$PROD_URL" python3 scripts/fix_mismatched_settings.py --apply
"""

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, save_to_history  # noqa: E402


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def run(apply=False):
    conn = _connect()
    cur = conn.cursor()
    log = []

    cur.execute(
        """SELECT st.session_id, st.tune_id, st.setting_id, ts.tune_id
           FROM session_tune st JOIN tune_setting ts ON ts.setting_id = st.setting_id
           WHERE ts.tune_id <> st.tune_id ORDER BY 1, 2"""
    )
    for session_id, tune_id, setting_id, belongs_to in cur.fetchall():
        save_to_history(cur, "session_tune", "UPDATE", (session_id, tune_id))
        cur.execute(
            "UPDATE session_tune SET setting_id = NULL WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id),
        )
        log.append(
            f"session {session_id}, tune {tune_id}: setting {setting_id} (tune {belongs_to})"
        )

    cur.execute(
        """SELECT sit.session_instance_tune_id, sit.session_instance_id, sit.tune_id,
                  sit.setting_override, ts.tune_id
           FROM session_instance_tune sit
           JOIN tune_setting ts ON ts.setting_id = sit.setting_override
           WHERE ts.tune_id <> sit.tune_id ORDER BY 1"""
    )
    for row_id, instance_id, tune_id, setting_id, belongs_to in cur.fetchall():
        save_to_history(cur, "session_instance_tune", "UPDATE", row_id)
        cur.execute(
            "UPDATE session_instance_tune SET setting_override = NULL WHERE session_instance_tune_id = %s",
            (row_id,),
        )
        log.append(
            f"night {instance_id}, row {row_id}, tune {tune_id}: setting {setting_id} (tune {belongs_to})"
        )

    cur.execute(
        """SELECT pt.person_tune_id, pt.person_id, pt.tune_id, pt.setting_id, ts.tune_id
           FROM person_tune pt JOIN tune_setting ts ON ts.setting_id = pt.setting_id
           WHERE ts.tune_id <> pt.tune_id ORDER BY 1"""
    )
    for pt_id, person_id, tune_id, setting_id, belongs_to in cur.fetchall():
        save_to_history(cur, "person_tune", "UPDATE", pt_id)
        cur.execute(
            "UPDATE person_tune SET setting_id = NULL WHERE person_tune_id = %s",
            (pt_id,),
        )
        log.append(
            f"person {person_id}, tune {tune_id}: setting {setting_id} (tune {belongs_to})"
        )

    print("\n".join(log) if log else "Nothing to do.")
    print(f"\n{len(log)} setting(s) cleared.")

    if apply:
        conn.commit()
        print("Committed.")
    else:
        conn.rollback()
        print("Dry run: rolled back. Pass --apply to commit.")
    conn.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    parser.add_argument(
        "--apply", action="store_true", help="commit (default: dry run)"
    )
    sys.exit(run(apply=parser.parse_args().apply))
