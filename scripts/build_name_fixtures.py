#!/usr/bin/env python3
"""Build the calibration fixture set for the tune-name matcher (spec 037).

The matcher (frontend/src/tunesheet/namematch.js) decides whether the drawer's
`aka` subtitle is worth showing — i.e. whether two strings are the same name spelled
differently, or genuinely different names. Its thresholds have to be tuned against
real names, so this emits the candidate pairs and a human labels them.

    python3 scripts/build_name_fixtures.py --limit 200 > /tmp/pairs.json

WHAT IT DOES
    - Ranks tunes by popularity (tune.tunebook_count_cached, which IS thesession.org's
      popularity metric — no scraping needed). Tops up from the dump by alias count if
      the database doesn't have enough ranked tunes, since a tune with many aliases is
      exactly where the matcher gets exercised.
    - Pulls each tune's alias set from csv/aliases.csv in thesession.org's weekly data
      dump (github.com/adactio/TheSession-data), reusing the fetch/parse code from the
      spec-031 merge-sync service.
    - Emits every WITHIN-TUNE name pair (canonical name + aliases, deduped).

WHAT IT DOES NOT DO — AND WHY
    It does not label the pairs. The alias data CANNOT produce the labels: an alias
    group freely mixes spelling variants ("The Connaughtman's Rambles" / "Connaught
    Rambles") with genuinely different names for the same tune. Suppressing the first
    and SHOWING the second is the entire job, so a human has to read them.

    It also does not generate the negative set. Do not be tempted to build one by
    sampling pairs from *different* tunes: the same name legitimately belongs to
    several different tunes ("O'Keefe's"), so a cross-tune identical pair is not a
    matcher failure — "same name" is the right answer there. The negatives in
    namematch.fixtures.json are therefore hand-picked genuinely-different names.

REFRESHING
    Re-run against a newer dump, label only the pairs that aren't already in
    frontend/src/tunesheet/namematch.fixtures.json, and re-tune. Only add a spelling
    substitution when a real labelled pair fails without it — never speculatively.
"""
import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection  # noqa: E402
from services.tune_merge_scan_service import _fetch_dump, _Throttle  # noqa: E402


def ranked_tune_ids(cur, limit):
    """Most popular tunes we know about, best-effort."""
    cur.execute(
        """
        SELECT tune_id, name
        FROM tune
        WHERE tunebook_count_cached IS NOT NULL
        ORDER BY tunebook_count_cached DESC
        LIMIT %s
        """,
        (limit,),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200, help="how many tunes to draw pairs from")
    args = ap.parse_args()

    print("fetching thesession.org data dump...", file=sys.stderr)
    _live_ids, _settings, aliases_map = _fetch_dump(_Throttle())
    print(f"  {len(aliases_map)} tunes have aliases upstream", file=sys.stderr)

    conn = get_db_connection()
    cur = conn.cursor()
    tunes = ranked_tune_ids(cur, args.limit)
    print(f"  {len(tunes)} tunes ranked by tunebook_count_cached", file=sys.stderr)

    # Top up from the dump by alias count when the database is thin (e.g. a test DB).
    if len(tunes) < args.limit:
        have = {t[0] for t in tunes}
        by_alias_count = sorted(
            (tid for tid in aliases_map if tid not in have),
            key=lambda tid: len(aliases_map[tid]),
            reverse=True,
        )
        for tid in by_alias_count[: args.limit - len(tunes)]:
            tunes.append((tid, None))
        print(f"  topped up to {len(tunes)} from the dump by alias count", file=sys.stderr)

    out = []
    for tune_id, canonical in tunes:
        names = []
        if canonical:
            names.append(canonical)
        names.extend(aliases_map.get(tune_id, []))

        # Dedupe exactly (case-sensitively): an exactly-equal pair is trivially "same"
        # and teaches the matcher nothing.
        seen, uniq = set(), []
        for n in names:
            n = (n or "").strip()
            if n and n not in seen:
                seen.add(n)
                uniq.append(n)

        for a, b in itertools.combinations(uniq, 2):
            out.append({"tune_id": tune_id, "a": a, "b": b, "label": None})

    conn.close()
    print(f"  {len(out)} within-tune pairs to label", file=sys.stderr)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
