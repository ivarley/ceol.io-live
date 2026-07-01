"""
Integration tests for the "likely next tune" suggestion (Feature: likely-next).

compute_session_vocabulary() attaches a `next` field to each Tier-A vocabulary entry:
the single successor that follows the anchor tune WITHIN A SET more than 50% of the time
and at least 3 times, across all instances of the session. These tests exercise the
thresholds and the set-boundary (break) exclusion against the real test database, inside
a transaction that the db_cursor fixture rolls back.
"""

import pytest

from live_logging_routes import compute_session_vocabulary

SID = 9100  # session
# tunes
SILVER = 9101   # Silver Spear  -> qualifies (Earl's Chair follows 3/4 within-set)
EARLS = 9102    # Earl's Chair  -> always set-closer / cross-break only: no successor
MAID = 9103     # Maid Behind the Bar -> top successor only twice (< 3): no qualify
CLOSER = 9104   # The Closer
LEAD = 9105     # Lead Tune     -> single within-set successor (< 3): no qualify


def _seed(cur):
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
        (SID, "Next Tune Test", "nexttune-test"),
    )
    for tid, name in [
        (SILVER, "Silver Spear"),
        (EARLS, "Earl's Chair"),
        (MAID, "Maid Behind the Bar"),
        (CLOSER, "The Closer"),
        (LEAD, "Lead Tune"),
    ]:
        cur.execute(
            "INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel')",
            (tid, name),
        )
        cur.execute(
            "INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)",
            (SID, tid),
        )

    # rows = list of (tune_id_or_None, record_type) in play order, one list per instance
    instances = {
        9201: [(SILVER, "tune"), (EARLS, "tune")],                       # Silver -> Earl's
        9202: [(SILVER, "tune"), (EARLS, "tune")],                       # Silver -> Earl's
        9203: [(SILVER, "tune"), (EARLS, "tune")],                       # Silver -> Earl's
        9204: [(SILVER, "tune"), (MAID, "tune")],                        # Silver -> Maid
        # Silver is the LAST tune of its set (break after it); Closer starts a NEW set.
        # Silver->Closer is cross-break and must NOT count.
        9205: [(LEAD, "tune"), (SILVER, "tune"), (None, "break"), (CLOSER, "tune")],
        9206: [(MAID, "tune"), (CLOSER, "tune")],                        # Maid -> Closer (1)
        9207: [(MAID, "tune"), (CLOSER, "tune")],                        # Maid -> Closer (2, still < 3)
    }
    positions = "abcdefgh"
    for inst_id, rows in instances.items():
        cur.execute(
            "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, %s)",
            (inst_id, SID, f"2026-0{inst_id % 7 + 1}-01"),
        )
        for i, (tid, rtype) in enumerate(rows):
            name = "Break" if rtype == "break" else None
            cur.execute(
                """
                INSERT INTO session_instance_tune
                    (session_instance_id, tune_id, name, order_position, record_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (inst_id, tid, name, positions[i], rtype),
            )


def _by_id(known):
    return {t["tune_id"]: t for t in known}


def test_qualifying_successor_attached(db_cursor):
    _seed(db_cursor)
    known, _ = compute_session_vocabulary(db_cursor, SID, n=200, m=0)
    entries = _by_id(known)

    nxt = entries[SILVER].get("next")
    assert nxt is not None, "Silver Spear should carry a likely-next successor"
    assert nxt["tune_id"] == EARLS
    assert nxt["name"] == "Earl's Chair"
    assert nxt["tune_type"] == "Reel"


def test_set_closer_and_cross_break_excluded(db_cursor):
    _seed(db_cursor)
    known, _ = compute_session_vocabulary(db_cursor, SID, n=200, m=0)
    entries = _by_id(known)

    # Earl's Chair only ever ends a set (or is followed across a break) -> no within-set successor.
    assert "next" not in entries[EARLS]


def test_below_three_floor_no_suggestion(db_cursor):
    _seed(db_cursor)
    known, _ = compute_session_vocabulary(db_cursor, SID, n=200, m=0)
    entries = _by_id(known)

    # Maid -> Closer happens 100% of the time but only twice (< 3) -> no suggestion.
    assert "next" not in entries[MAID]
    # Lead -> Silver happens once -> no suggestion.
    assert "next" not in entries[LEAD]


def test_searchable_abc_attached(db_cursor):
    """Each vocabulary entry carries a whitespace-stripped `abc` string (all settings
    joined) for the client's instant ABC substring match; tunes with no notation get None."""
    _seed(db_cursor)
    # Two settings for one tune -> aggregated; whitespace is stripped (meaningless in ABC).
    db_cursor.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, abc) VALUES (%s, %s, %s), (%s, %s, %s)",
        (99001, SILVER, "fdd cAA | B2A", 99002, SILVER, "AB cd ef"),
    )
    known, _ = compute_session_vocabulary(db_cursor, SID, n=200, m=0)
    entries = _by_id(known)

    silver_abc = entries[SILVER]["abc"]
    assert silver_abc is not None
    assert " " not in silver_abc  # whitespace stripped
    assert "fddcAA|B2A" in silver_abc
    assert "ABcdef" in silver_abc
    # A tune with no tune_setting rows carries an explicit None (not a missing key).
    assert entries[EARLS]["abc"] is None
