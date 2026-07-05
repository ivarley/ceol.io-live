"""
Integration tests for tune-merge gaps (spec 030).

Two groups:

1. merge_tune_ids() proc tests — run entirely inside one uncommitted transaction
   (db_conn auto-rollback), so they build their own fixture rows and leave nothing
   behind. They cover the tables 016 missed (person_tune_instrument via FK cascade,
   recording_tune_segment), name/alias preservation, survivor-wins conflicts, and
   the history rows the proc now writes.

2. HTTP read/write path tests — the redirect-following read APIs (redirected_from),
   the 301 permalink routes, and the stale-write remap. These need COMMITTED rows
   (endpoints open their own connections), so the merged_pair fixture commits a
   throwaway tune pair + session and deletes them in teardown, mirroring
   test_live_logging_ops.py's isolation pattern.
"""

import pytest

from database import get_db_connection

pytestmark = pytest.mark.integration

# High, unlikely-to-collide ids for throwaway fixtures (94xx block).
OLD = 9401       # "Sonny Riordans" — merged away
NEW = 9402       # "The Blue Ribbon" — canonical survivor
SAME_OLD = 9403  # same-name pair: no alias fills expected
SAME_NEW = 9404
P_CLEAN = 9401   # person with only OLD (clean move)
P_BOTH = 9402    # person with OLD and NEW (conflict; survivor wins)
SID = 9400       # session
INST = 9490      # session_instance
REC = 9401       # recording


def _build_merge_fixture(cur):
    """Insert the full merge scenario on the given cursor (no commit)."""
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'Sonny Riordans', 'Reel'), (%s, 'The Blue Ribbon', 'Reel')", (OLD, NEW))
    cur.execute("INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'CleanMove', 'P'), (%s, 'Conflict', 'P')", (P_CLEAN, P_BOTH))
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Merge030', 'merge030-test')", (SID,))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')", (INST, SID))

    # P_CLEAN: only OLD, learned, with two instrument overrides, no name_alias.
    cur.execute("INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, 'learned')", (P_CLEAN, OLD))
    cur.execute("INSERT INTO person_tune_instrument (person_id, tune_id, instrument, status) VALUES (%s, %s, 'Fiddle', 'learned'), (%s, %s, 'Flute', 'learning')",
                (P_CLEAN, OLD, P_CLEAN, OLD))
    # P_BOTH: OLD (with an override) and NEW — conflict; survivor wins.
    cur.execute("INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, 'learning'), (%s, %s, 'learned')",
                (P_BOTH, OLD, P_BOTH, NEW))
    cur.execute("INSERT INTO person_tune_instrument (person_id, tune_id, instrument, status) VALUES (%s, %s, 'Banjo', 'learning')", (P_BOTH, OLD))

    # Session has OLD (no alias) plus an unrelated alias row for it.
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, OLD))
    cur.execute("INSERT INTO session_tune_alias (session_id, tune_id, alias) VALUES (%s, %s, 'The Squirrely Hobbit')", (SID, OLD))

    # Log rows: one displaying the canonical (old) name, one with an explicit name.
    cur.execute("INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) VALUES (%s, %s, 'a0', 'tune')", (INST, OLD))
    cur.execute("INSERT INTO session_instance_tune (session_instance_id, tune_id, name, order_position, record_type) VALUES (%s, %s, 'My Custom Name', 'a1', 'tune')", (INST, OLD))

    # A setting + a recording tune segment.
    cur.execute("INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Dmaj', 'abc')", (OLD, OLD))
    cur.execute("INSERT INTO recording (recording_id, session_instance_id, person_id, status) VALUES (%s, %s, %s, 'stopped')", (REC, INST, P_CLEAN))
    cur.execute("INSERT INTO recording_tune_segment (recording_id, tune_id, start_timestamp_ms, end_timestamp_ms) VALUES (%s, %s, 0, 1000)", (REC, OLD))


def _merge(cur, old=OLD, new=NEW):
    cur.execute("SELECT merge_tune_ids(%s, %s, NULL)", (old, new))
    return cur.fetchone()[0]


# --------------------------------------------------------------------------- #
# merge_tune_ids proc (transaction-local; db_conn rollback cleans up)
# --------------------------------------------------------------------------- #

def test_merge_clean_move_carries_instrument_overrides(db_cursor):
    _build_merge_fixture(db_cursor)
    result = _merge(db_cursor)
    assert result["success"] is True
    assert result["tables_updated"]["person_tune_instrument"] == {"moved": 2, "dropped": 1}
    db_cursor.execute("SELECT tune_id, instrument FROM person_tune_instrument WHERE person_id = %s ORDER BY instrument", (P_CLEAN,))
    assert db_cursor.fetchall() == [(NEW, "Fiddle"), (NEW, "Flute")]


def test_merge_conflict_survivor_wins(db_cursor):
    _build_merge_fixture(db_cursor)
    _merge(db_cursor)
    # Survivor row untouched (learned, no alias inherited); old row + overrides gone.
    db_cursor.execute("SELECT tune_id, learn_status, name_alias FROM person_tune WHERE person_id = %s", (P_BOTH,))
    assert db_cursor.fetchall() == [(NEW, "learned", None)]
    db_cursor.execute("SELECT COUNT(*) FROM person_tune_instrument WHERE person_id = %s", (P_BOTH,))
    assert db_cursor.fetchone()[0] == 0


def test_merge_preserves_old_name_as_aliases(db_cursor):
    _build_merge_fixture(db_cursor)
    result = _merge(db_cursor)
    # person_tune: the clean-move row gets the old name as its personal alias.
    db_cursor.execute("SELECT name_alias FROM person_tune WHERE person_id = %s", (P_CLEAN,))
    assert db_cursor.fetchone()[0] == "Sonny Riordans"
    # session_tune: display alias filled.
    db_cursor.execute("SELECT tune_id, alias FROM session_tune WHERE session_id = %s", (SID,))
    assert db_cursor.fetchall() == [(NEW, "Sonny Riordans")]
    # session_instance_tune: NULL-name row frozen to the old name; explicit name kept.
    db_cursor.execute("SELECT name FROM session_instance_tune WHERE session_instance_id = %s ORDER BY order_position", (INST,))
    assert [r[0] for r in db_cursor.fetchall()] == ["Sonny Riordans", "My Custom Name"]
    # session_tune_alias: existing alias moved + old name added as a searchable alias.
    db_cursor.execute("SELECT alias FROM session_tune_alias WHERE session_id = %s AND tune_id = %s ORDER BY alias", (SID, NEW))
    assert [r[0] for r in db_cursor.fetchall()] == ["Sonny Riordans", "The Squirrely Hobbit"]
    assert result["tables_updated"]["session_tune_alias"]["added"] == 1


def test_merge_same_name_fills_nothing(db_cursor):
    db_cursor.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'Twin Reel', 'Reel'), (%s, 'Twin Reel', 'Reel')", (SAME_OLD, SAME_NEW))
    db_cursor.execute("INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'Twin', 'P')", (P_CLEAN,))
    db_cursor.execute("INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, 'learning')", (P_CLEAN, SAME_OLD))
    result = _merge(db_cursor, SAME_OLD, SAME_NEW)
    assert result["names_differ"] is False
    db_cursor.execute("SELECT name_alias FROM person_tune WHERE person_id = %s", (P_CLEAN,))
    assert db_cursor.fetchone()[0] is None
    assert result["tables_updated"]["session_tune_alias"]["added"] == 0


def test_merge_existing_override_never_overwritten(db_cursor):
    _build_merge_fixture(db_cursor)
    db_cursor.execute("UPDATE person_tune SET name_alias = 'My Own Name' WHERE person_id = %s AND tune_id = %s", (P_CLEAN, OLD))
    _merge(db_cursor)
    db_cursor.execute("SELECT name_alias FROM person_tune WHERE person_id = %s", (P_CLEAN,))
    assert db_cursor.fetchone()[0] == "My Own Name"


def test_merge_moves_settings_segments_and_tombstones(db_cursor):
    _build_merge_fixture(db_cursor)
    result = _merge(db_cursor)
    db_cursor.execute("SELECT tune_id FROM tune_setting WHERE setting_id = %s", (OLD,))
    assert db_cursor.fetchone()[0] == NEW
    db_cursor.execute("SELECT tune_id FROM recording_tune_segment WHERE recording_id = %s", (REC,))
    assert db_cursor.fetchone()[0] == NEW
    assert result["tables_updated"]["recording_tune_segment"]["updated"] == 1
    db_cursor.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (OLD,))
    assert db_cursor.fetchone()[0] == NEW


def test_merge_writes_history_rows(db_cursor):
    _build_merge_fixture(db_cursor)
    _merge(db_cursor)
    counts = {}
    for table, where in [
        ("person_tune_history", "tune_id = %s"),
        ("person_tune_instrument_history", "tune_id = %s"),
        ("session_tune_history", "tune_id = %s"),
        ("session_instance_tune_history", "tune_id = %s"),
        ("tune_history", "tune_id = %s"),
    ]:
        db_cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", (OLD,))
        counts[table] = db_cursor.fetchone()[0]
    # Pre-images of everything the merge touched: 2 person_tune rows (1 UPDATE + 1
    # DELETE), 3 override rows (2 moved + 1 dropped), 1 session_tune, 2 log rows,
    # and the tombstoned tune itself.
    assert counts == {
        "person_tune_history": 2,
        "person_tune_instrument_history": 3,
        "session_tune_history": 1,
        "session_instance_tune_history": 2,
        "tune_history": 1,
    }


def test_merge_rejects_chain_and_self(db_cursor):
    _build_merge_fixture(db_cursor)
    _merge(db_cursor)
    # OLD is now a redirect: merging it again, or into it, must fail.
    with pytest.raises(Exception):
        _merge(db_cursor, OLD, NEW)


# --------------------------------------------------------------------------- #
# HTTP paths (need committed fixtures — endpoints open their own connections)
# --------------------------------------------------------------------------- #

@pytest.fixture
def merged_pair():
    """Commit OLD (redirecting to NEW) + NEW + a session enrolling NEW; delete after."""
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'The Blue Ribbon', 'Reel')", (NEW,))
    cur.execute("INSERT INTO tune (tune_id, name, tune_type, redirect_to_tune_id) VALUES (%s, 'Sonny Riordans', 'Reel', %s)", (OLD, NEW))
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Merge030 HTTP', 'merge030-test')", (SID,))
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, NEW))
    conn.commit()

    yield {"old": OLD, "new": NEW, "session_id": SID, "path": "merge030-test"}

    cur.execute("DELETE FROM person_tune_history WHERE tune_id = ANY(%s)", ([OLD, NEW],))
    cur.execute("DELETE FROM person_tune WHERE tune_id = ANY(%s)", ([OLD, NEW],))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([OLD, NEW],))
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (OLD,))  # redirect first
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (NEW,))
    conn.commit()
    cur.close()
    conn.close()


def test_session_tune_permalink_301(client, merged_pair):
    resp = client.get(f"/sessions/{merged_pair['path']}/tunes/{merged_pair['old']}")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith(f"/sessions/{merged_pair['path']}/tunes/{merged_pair['new']}")


def test_session_tune_detail_follows_redirect(client, authenticated_user, merged_pair):
    with authenticated_user:
        resp = client.get(f"/api/sessions/{merged_pair['path']}/tunes/{merged_pair['old']}")
    body = resp.get_json()
    assert body["success"] is True
    assert body["redirected_from"] == merged_pair["old"]
    assert body["session_tune"]["tune_id"] == merged_pair["new"]
    assert body["session_tune"]["tune_name"] == "The Blue Ribbon"


def test_session_tune_detail_canonical_id_no_redirect_flag(client, authenticated_user, merged_pair):
    with authenticated_user:
        resp = client.get(f"/api/sessions/{merged_pair['path']}/tunes/{merged_pair['new']}")
    body = resp.get_json()
    assert body["success"] is True
    assert body["redirected_from"] is None


def test_add_session_tune_remaps_stale_write(client, authenticated_user, merged_pair, db_cursor):
    # NEW is already enrolled, so a remapped add of OLD hits the duplicate guard —
    # proof the write proceeded against the canonical id instead of rejecting with
    # a tune_redirected error.
    with authenticated_user:
        resp = client.post(f"/api/sessions/{merged_pair['path']}/tunes", json={"tune_id": merged_pair["old"]})
    body = resp.get_json()
    assert body["error"] == "Tune already exists in this session"


def test_my_tunes_op_add_remaps(client, authenticated_user, merged_pair):
    with authenticated_user:
        resp = client.post("/api/my-tunes/ops", json={"op_id": "test-030-remap", "type": "add", "tune_id": merged_pair["old"]})
    body = resp.get_json()
    assert body["success"] is True
    assert body["tune_id"] == merged_pair["new"]
    assert body["remapped_from"] == merged_pair["old"]
    # The row landed on the canonical tune, never the tombstoned one.
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM person_tune WHERE tune_id = %s", (merged_pair["old"],))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM person_tune WHERE tune_id = %s", (merged_pair["new"],))
    assert cur.fetchone()[0] == 1
    cur.close()
    conn.close()
