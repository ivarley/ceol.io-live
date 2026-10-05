#!/usr/bin/env python3
"""
Migration 055 (data step): give every session a place, and fix the paths that do
not fit the two-part rule. Spec: specs/changes/inprogress/055-places-and-session-paths.md
("Migration"), with spec 056's festival step folded in.

Run AFTER schema/058_places.sql (the place and path_redirect tables, session.place_id).

In order, in one transaction:
  1. A town row for each distinct first segment of the regular `{city}/{name}`
     paths: name from the sessions' city text as entered (the most common spelling
     when they differ), area and country normalized (places.normalize_area /
     normalize_country). Plus the towns the strays and festivals below need.
  2. The strays: `None` -> houston/shawns-house (no redirect); logan-prodigy ->
     logan/prodigy; austin/acf -> acf/2025 as a festival year.
  3. The festivals (spec 056): place rows oflahertys, noel-hill-ics-east, acf; the
     year sessions renamed "{festival} {yyyy}"; oflahertys/2025 starts 2025-10-23;
     noel-hill-ics-east/2026 ends 2026-07-30.
  4. place_id on every session: the town of its first segment, or for a festival
     year the festival's town.
  5. No parents. Metros are curation, done on the Places page afterwards.

Anything the plan does not cover (a one-part path that is not a known stray, a
festival that is not listed, a regular session whose second part is a year) is
reported, and --apply refuses to run until it is handled.

The default is a dry run: it does all of the above, prints what it did, and rolls
back. --apply commits. Idempotent: a second run finds nothing to do.

Connection: DATABASE_URL (one connection string, passed inline so prod creds never
linger in the shell), else the app's PGHOST/PGDATABASE/... variables.

    psql "$PROD_URL" -f schema/058_places.sql
    DATABASE_URL="$PROD_URL" python3 scripts/migrate_055_places.py           # dry run
    DATABASE_URL="$PROD_URL" python3 scripts/migrate_055_places.py --apply
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

import psycopg2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import places  # noqa: E402
from database import get_db_connection, save_to_history  # noqa: E402

_YEAR = re.compile(r"^\d{4}$")

# old path -> (new path, town slug, write a redirect?)
STRAYS = {
    "None": ("houston/shawns-house", "houston", False),
    "logan-prodigy": ("logan/prodigy", "logan", True),
}

# Festival years (spec 056 "Migration"). `from_path` is where the session is today.
FESTIVALS = [
    {
        "from_path": "oflahertys/2025",
        "path": "oflahertys/2025",
        "slug": "oflahertys",
        "name": "O'Flaherty's Irish Music Retreat",
        "town": "midlothian",
        "year_name": "O'Flaherty's Irish Music Retreat 2025",
        "set": {"initiation_date": "2025-10-23"},
        "redirect": False,
    },
    {
        "from_path": "noel-hill-ics-east/2026",
        "path": "noel-hill-ics-east/2026",
        "slug": "noel-hill-ics-east",
        "name": "Noel Hill Irish Concertina School East",
        "town": "east-durham",
        "year_name": "Noel Hill Irish Concertina School East 2026",
        "set": {"termination_date": "2026-07-30"},
        "redirect": False,
    },
    {
        "from_path": "austin/acf",
        "path": "acf/2025",
        "slug": "acf",
        "name": "Austin Celtic Festival",
        "town": "austin",
        "year_name": "Austin Celtic Festival 2025",
        "set": {"session_type": "festival"},
        "redirect": True,
    },
]


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return get_db_connection()


def _table_exists(cur, table):
    cur.execute("SELECT to_regclass(%s)", (table,))
    return cur.fetchone()[0] is not None


def _sessions(cur):
    cur.execute(
        """SELECT session_id, path, name, city, state, country, session_type, place_id
           FROM session ORDER BY session_id"""
    )
    keys = (
        "session_id",
        "path",
        "name",
        "city",
        "state",
        "country",
        "session_type",
        "place_id",
    )
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def run(apply=False):
    conn = _connect()
    cur = conn.cursor()
    if not _table_exists(cur, "place") or not _table_exists(cur, "path_redirect"):
        print("place / path_redirect missing: run schema/058_places.sql first.")
        return 1

    log = []
    problems = []
    sessions = _sessions(cur)
    by_path = {s["path"]: s for s in sessions}
    festival_from = {f["from_path"] for f in FESTIVALS} | {f["path"] for f in FESTIVALS}

    # ---- What the towns are --------------------------------------------------
    # town slug -> sessions that say where it is
    town_evidence = defaultdict(list)
    for s in sessions:
        path = s["path"]
        if path in STRAYS:
            town_evidence[STRAYS[path][1]].append(s)
        elif path in festival_from:
            spec = next(f for f in FESTIVALS if path in (f["from_path"], f["path"]))
            town_evidence[spec["town"]].append(s)
        elif path.count("/") == 1:
            prefix, second = path.split("/")
            if (
                places.get_place_by_slug(cur, prefix)
                and places.get_place_by_slug(cur, prefix)["kind"] == "festival"
            ):
                continue  # a year under a festival made since the schema went in
            if s["session_type"] == "festival":
                problems.append(
                    f"session {s['session_id']} {path!r}: a festival not in the plan"
                )
            elif _YEAR.match(second):
                problems.append(
                    f"session {s['session_id']} {path!r}: a regular session whose second part is a year"
                )
            town_evidence[prefix].append(s)
        else:
            problems.append(
                f"session {s['session_id']} {path!r}: not two parts and not a known stray"
            )

    # ---- 1. Town rows ----------------------------------------------------------
    towns = {}
    for slug, evidence in sorted(town_evidence.items()):
        existing = places.get_place_by_slug(cur, slug)
        if existing:
            towns[slug] = existing
            continue
        # Prefer the sessions that actually live under the slug; the strays and
        # festivals only vouch for a town nobody else names.
        own = [s for s in evidence if s["path"].split("/")[0] == slug] or evidence
        spellings = Counter(
            (s["city"] or "").strip() for s in own if (s["city"] or "").strip()
        )
        name = (
            spellings.most_common(1)[0][0]
            if spellings
            else slug.replace("-", " ").title()
        )
        geo = Counter()
        for s in own:
            country = places.normalize_country(s["country"])
            geo[(places.normalize_area(s["state"], country), country)] += 1
        (area, country), _ = geo.most_common(1)[0]
        if len(spellings) > 1 or len(geo) > 1:
            log.append(
                f"  note: {slug}: spellings {dict(spellings)}, geography {dict(geo)}; took the most common"
            )
        if places.slugify(name) != slug:
            log.append(
                f"  note: {slug}: name {name!r} does not slug to {slug!r} (kept: the slug is the URL)"
            )
        towns[slug] = places.create_place(cur, slug, name, "place", None, area, country)
        log.append(f"place {slug}: {name}, {area or '-'}, {country or '-'}")

    # ---- 2 and 3. Strays and festivals --------------------------------------------
    def move(session, new_path, redirect, extra=None, reason=""):
        save_to_history(cur, "session", "UPDATE", session["session_id"], user_id=None)
        sets = {"path": new_path, **(extra or {})}
        cols = ", ".join(f"{k} = %s" for k in sets)
        cur.execute(
            f"UPDATE session SET {cols}, last_modified_date = CURRENT_TIMESTAMP WHERE session_id = %s",
            (*sets.values(), session["session_id"]),
        )
        if redirect and new_path != session["path"]:
            places.record_redirect(cur, session["path"], new_path)
        log.append(
            f"session {session['session_id']}: {session['path']!r} -> {new_path!r}"
            f"{' (redirect)' if redirect and new_path != session['path'] else ''}"
            f"{' ' + str(extra) if extra else ''}{reason}"
        )

    for old, (new, _town, redirect) in STRAYS.items():
        s = by_path.get(old)
        if s is None:
            continue
        if new in by_path:
            problems.append(f"stray {old!r}: {new!r} is already taken")
            continue
        move(s, new, redirect)
        s["path"] = new

    for f in FESTIVALS:
        s = by_path.get(f["from_path"]) or by_path.get(f["path"])
        if s is None:
            log.append(f"  note: festival {f['from_path']!r} not found; skipped")
            continue
        town = towns.get(f["town"])
        if town is None:
            problems.append(f"festival {f['slug']}: no town {f['town']!r}")
            continue
        festival = places.get_place_by_slug(cur, f["slug"])
        if festival is None:
            festival = places.create_place(
                cur, f["slug"], f["name"], "festival", town["place_id"]
            )
            log.append(
                f"place {f['slug']}: festival {f['name']!r} under {town['slug']}"
            )
        elif festival["kind"] != "festival":
            problems.append(f"festival {f['slug']}: the slug is already a town")
            continue
        extra = {"name": f["year_name"], "session_type": "festival", **f["set"]}
        cur.execute(
            "SELECT name, session_type, initiation_date::text, termination_date::text FROM session WHERE session_id = %s",
            (s["session_id"],),
        )
        current = dict(
            zip(
                ("name", "session_type", "initiation_date", "termination_date"),
                cur.fetchone(),
            )
        )
        extra = {k: v for k, v in extra.items() if current.get(k) != v}
        if s["path"] != f["path"] or extra:
            if f["path"] != s["path"] and f["path"] in by_path:
                problems.append(f"festival {f['slug']}: {f['path']!r} is already taken")
                continue
            move(s, f["path"], f["redirect"], extra)
            s["path"] = f["path"]
        s["town"] = town

    # ---- 4. place_id ----------------------------------------------------------------
    for s in sessions:
        if s["place_id"] is not None:
            continue
        if "town" in s:
            town = s["town"]
        elif s["path"].count("/") == 1 and s["path"].split("/")[0] in towns:
            town = towns[s["path"].split("/")[0]]
        else:
            continue  # reported above
        cur.execute(
            "UPDATE session SET place_id = %s WHERE session_id = %s",
            (town["place_id"], s["session_id"]),
        )
        log.append(
            f"session {s['session_id']} {s['path']!r}: place_id -> {town['slug']}"
        )

    # ---- Check: every session now fits the rule ------------------------------------
    for s in _sessions(cur):
        if s["place_id"] is None:
            problems.append(
                f"session {s['session_id']} {s['path']!r}: still has no place"
            )
            continue
        error = places.validate_path_for_place(
            cur, s["path"], s["session_type"], s["place_id"]
        )
        if error:
            problems.append(f"session {s['session_id']} {s['path']!r}: {error}")

    print("\n".join(log) if log else "Nothing to do.")
    if problems:
        print("\nNot handled:")
        print("\n".join(f"  {p}" for p in problems))

    if apply and not problems:
        conn.commit()
        print("\nCommitted.")
    else:
        conn.rollback()
        if apply:
            print("\nRolled back: handle the items above first.")
        else:
            print("\nDry run: rolled back. Pass --apply to commit.")
    conn.close()
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--apply", action="store_true", help="commit (default: dry run)"
    )
    sys.exit(run(apply=parser.parse_args().apply))
