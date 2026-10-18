#!/usr/bin/env python3
"""
Fix every setting that belongs to a different tune than its row's.

session_tune.setting_id, session_instance_tune.setting_override and
person_tune.setting_id must name a setting of the row's own tune. Before
schema/064_setting_matches_tune.sql, any number was accepted, so production had
42 rows pointing at another tune's setting. Three causes, three fixes, in order:

  1. A row on the wrong tune. Session 1 logged Allistrum's March as tune 2136
     with setting 36627, which is a setting of 6188, a separate tune of the same
     name; the session plays 6188. RETARGET moves the session's row and its
     nights' rows to 6188, keeping the setting (now its own).
  2. A position typed as an id. In the session-level setting box, "1", "2",
     "24" meant the 1st, 2nd, 24th setting on thesession.org, not setting #1
     (which is Cooley's). Every such number fits within its tune's list, and
     every session key set alongside matches the Nth setting's key. So a
     session's setting that fits within the tune's list becomes the Nth setting
     (imported if we don't hold it); one that doesn't is cleared.
  3. Anything else (a night relinked to another tune that kept the old tune's
     setting, a person's list): the setting is cleared, and the row falls back
     to its tune's first setting.

Each change writes a history row. Run AFTER schema/064 and 065. The default is
a dry run: it prints what it would do and rolls back. --apply commits. A second
run finds nothing to do.

Connection: DATABASE_URL, else the app's PGHOST/PGDATABASE/... variables.

    DATABASE_URL="$PROD_URL" ./venv/bin/python scripts/fix_mismatched_settings.py
    DATABASE_URL="$PROD_URL" ./venv/bin/python scripts/fix_mismatched_settings.py --apply
"""

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection, save_to_history  # noqa: E402

# (session_id, from tune, to tune): rows logged on the wrong tune.
RETARGET = [(1, 2136, 6188)]


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def _retarget(cur, log, problems):
    for session_id, old, new in RETARGET:
        cur.execute(
            "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id IN (%s, %s)",
            (session_id, old, new),
        )
        has = {r[0] for r in cur.fetchall()}
        if has == {old, new}:
            problems.append(
                f"session {session_id} already has tune {new}: not moving {old}"
            )
            continue
        if old in has:
            save_to_history(cur, "session_tune", "UPDATE", (session_id, old))
            cur.execute(
                "UPDATE session_tune SET tune_id = %s WHERE session_id = %s AND tune_id = %s",
                (new, session_id, old),
            )
            log.append(f"session {session_id}: tune {old} -> {new}")
        cur.execute(
            """SELECT sit.session_instance_tune_id, sit.session_instance_id
               FROM session_instance_tune sit
               JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
               WHERE si.session_id = %s AND sit.tune_id = %s
               ORDER BY 1""",
            (session_id, old),
        )
        for row_id, instance_id in cur.fetchall():
            save_to_history(cur, "session_instance_tune", "UPDATE", row_id)
            cur.execute(
                "UPDATE session_instance_tune SET tune_id = %s WHERE session_instance_tune_id = %s",
                (new, row_id),
            )
            log.append(f"night {instance_id}, row {row_id}: tune {old} -> {new}")


def _session_positions(cur, log, problems):
    from live_logging_routes import _ensure_setting_local, _fetch_thesession_tune
    from api_routes import TuneImportError

    cur.execute(
        """SELECT st.session_id, st.tune_id, st.setting_id, ts.tune_id
           FROM session_tune st JOIN tune_setting ts ON ts.setting_id = st.setting_id
           WHERE ts.tune_id <> st.tune_id ORDER BY 1, 2"""
    )
    for session_id, tune_id, n, belongs_to in cur.fetchall():
        try:
            settings = _fetch_thesession_tune(tune_id).get("settings") or []
        except TuneImportError as e:
            problems.append(
                f"session {session_id}, tune {tune_id}: thesession.org: {e.message}"
            )
            continue
        nth = settings[n - 1]["id"] if 1 <= n <= len(settings) else None
        if nth is not None:
            try:
                _ensure_setting_local(cur, tune_id, nth, None)
            except TuneImportError as e:
                problems.append(
                    f"session {session_id}, tune {tune_id}: setting {nth}: {e.message}"
                )
                continue
        save_to_history(cur, "session_tune", "UPDATE", (session_id, tune_id))
        cur.execute(
            "UPDATE session_tune SET setting_id = %s WHERE session_id = %s AND tune_id = %s",
            (nth, session_id, tune_id),
        )
        what = (
            f"setting {n} of {len(settings)} = #{nth}"
            if nth is not None
            else f"setting {n} (tune {belongs_to}) cleared: the tune has {len(settings)}"
        )
        log.append(f"session {session_id}, tune {tune_id}: {what}")


def _clear_the_rest(cur, log):
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
            f"night {instance_id}, row {row_id}, tune {tune_id}: setting {setting_id} (tune {belongs_to}) cleared"
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
            f"person {person_id}, tune {tune_id}: setting {setting_id} (tune {belongs_to}) cleared"
        )


def run(apply=False):
    conn = _connect()
    cur = conn.cursor()
    log, problems = [], []

    _retarget(cur, log, problems)
    _session_positions(cur, log, problems)
    _clear_the_rest(cur, log)

    print("\n".join(log) if log else "Nothing to do.")
    print(f"\n{len(log)} change(s).")
    if problems:
        print("\nNot handled:")
        print("\n".join(f"  {p}" for p in problems))

    if apply and not problems:
        conn.commit()
        print("Committed.")
    else:
        conn.rollback()
        if apply:
            print("Rolled back: handle the items above first.")
        else:
            print("Dry run: rolled back. Pass --apply to commit.")
    conn.close()
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    parser.add_argument(
        "--apply", action="store_true", help="commit (default: dry run)"
    )
    sys.exit(run(apply=parser.parse_args().apply))
