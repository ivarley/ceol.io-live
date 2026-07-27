"""
Integration tests for the live-logging op endpoint (Feature 024, spec §C).

These drive the real HTTP surface — POST /api/live/instances/<id>/ops — against the
test database, covering every op handler plus idempotency, corroboration, positioning,
and rejection. This is the shared contract between ANY client (mobile today, desktop
later) and the server; before this file it had no coverage.

Isolation note (important): the op endpoint opens its OWN db connection via
get_db_connection() and COMMITs. So the db_conn fixture's auto-rollback does NOT undo
op rows, and seed rows must be committed for the endpoint's connection to see them.
The `live_instance` fixture therefore commits a throwaway session/instance/tunes on its
own connection and explicitly cascade-deletes them in teardown. Verification reads use
the db_cursor fixture (READ COMMITTED — it sees the endpoint's committed writes).
"""

import uuid

import pytest

from database import get_db_connection
from live_logging_routes import _position_for
from fractional_indexing import generate_append_position, generate_position_between

pytestmark = pytest.mark.integration

# High, unlikely-to-collide ids for the throwaway fixtures.
SID = 9300          # session
INST = 9390         # session_instance
REEL = 9301         # "The Test Reel"        (linked add / matching)
MAID = 9302         # "The Maid Behind the Bar"
COOLEY = 9303       # "Cooleys"
NEWT = 9304         # "The Unenrolled Jig"   (canonical, NOT pre-enrolled in session_tune)
MERGED = 9305       # "The Merged Reel"      (redirects to REEL; must never enroll)
IMPORT_ID = 9399001     # a tune NOT in the DB, "imported" from thesession.org (mocked fetch)
IMPORT_SETTING = 9399501  # its default setting id
SET_LOCAL = 9301501     # REEL's already-imported DEFAULT setting (fixture row, lowest id)
SET_LOCAL2 = 9301502    # REEL's second local setting (fixture row, non-default)
SET_REMOTE = 9301503    # REEL setting that exists only on thesession.org (mocked fetch)
SET_NEWT = 9304501      # NEWT's only setting (fixture row) — enrollment defaults to it

# Canned thesession.org tune JSON for the mocked importer (spec 026).
FAKE_TS_TUNE = {
    "name": "The Imported Reel",
    "type": "reel",
    "tunebooks": 42,
    "settings": [{"id": IMPORT_SETTING, "key": "Dmaj", "abc": "D2FA d2FA|BAFA B2A2"}],
}

# Canned JSON for REEL itself — the chosen-setting import (spec 032) looks a specific
# setting up in the tune's full settings list.
FAKE_TS_REEL = {
    "name": "The Test Reel",
    "type": "reel",
    "tunebooks": 10,
    "settings": [
        {"id": SET_LOCAL, "key": "Dmaj", "abc": "ABCd efga|"},
        {"id": SET_LOCAL2, "key": "Gmaj", "abc": "GABc defg|"},
        {"id": SET_REMOTE, "key": "Amaj", "abc": "cdef!gabc|"},
    ],
}


@pytest.fixture
def live_instance():
    """Commit a throwaway session + instance + catalog tunes; cascade-delete after.

    Yields a dict of ids and a pre-existing person_id usable as a set starter.
    """
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                (SID, "Live Ops Test", "liveops-test"))
    for tid, name in [(REEL, "The Test Reel"), (MAID, "The Maid Behind the Bar"), (COOLEY, "Cooleys")]:
        cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel')", (tid, name))
        # manually_added: these three model the session's CURATED repertoire (someone
        # put them there on purpose), so the play-delete auto-cleanup (spec 045) must
        # leave them alone. NEWT below is the auto-enrollment subject.
        cur.execute("INSERT INTO session_tune (session_id, tune_id, manually_added) VALUES (%s, %s, TRUE)",
                    (SID, tid))
    # COOLEY gets a session alias (the override-only name tests exercise the alias arm
    # of normalize_override_name; display coalesces sit.name -> st.alias -> t.name).
    cur.execute("UPDATE session_tune SET alias = 'The Tumbling Cooley' WHERE session_id = %s AND tune_id = %s",
                (SID, COOLEY))
    # REEL's locally-cached settings (the chosen-setting tests, spec 032): SET_LOCAL is
    # the default (lowest id), SET_LOCAL2 a non-default alternative.
    cur.execute("INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Dmaj', 'ABCd efga|')",
                (SET_LOCAL, REEL))
    cur.execute("INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Gmaj', 'GABc defg|')",
                (SET_LOCAL2, REEL))
    # NEWT: a canonical tune deliberately NOT enrolled, so enrollment on add is observable.
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Jig')", (NEWT, "The Unenrolled Jig"))
    cur.execute("INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Edor', 'E2B BAB|')",
                (SET_NEWT, NEWT))
    # MERGED: a redirect/merged tune -- must never be enrolled (mirrors the old logger).
    cur.execute("INSERT INTO tune (tune_id, name, tune_type, redirect_to_tune_id) VALUES (%s, %s, 'Reel', %s)",
                (MERGED, "The Merged Reel", REEL))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, %s)",
                (INST, SID, "2026-02-01"))
    # A real person for started_by (FK -> person); reuse a seeded one, don't create/delete.
    cur.execute("SELECT person_id FROM person ORDER BY person_id LIMIT 1")
    person_id = cur.fetchone()[0]
    conn.commit()

    yield {"session_id": SID, "instance_id": INST, "reel": REEL, "maid": MAID,
           "cooley": COOLEY, "newt": NEWT, "merged": MERGED, "person_id": person_id}

    # Teardown: children before the instance (session_instance_tune has no ON DELETE
    # CASCADE from session_instance; session_event/corroboration do). History tables
    # have no FKs — clear them too so runs don't accumulate audit rows.
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_event WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_instance_tune_history WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_instance_history WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    # Chosen-setting imports write tune_setting_history (the settings themselves cascade
    # with the tune deletes below).
    cur.execute("DELETE FROM tune_setting_history WHERE tune_id = ANY(%s)", ([REEL, MAID, COOLEY, NEWT, MERGED],))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([REEL, MAID, COOLEY, NEWT, MERGED],))
    # MERGED references REEL via redirect_to_tune_id, so drop it before the tune it points to.
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (MERGED,))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", ([REEL, MAID, COOLEY, NEWT],))
    # A tune imported from thesession.org during a test (spec 026); tune_setting cascades.
    cur.execute("DELETE FROM tune_setting_history WHERE tune_id = %s", (IMPORT_ID,))
    cur.execute("DELETE FROM tune_history WHERE tune_id = %s", (IMPORT_ID,))
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (IMPORT_ID,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    conn.commit()
    cur.close()
    conn.close()


def _op(client, inst, **payload):
    """POST one op (auto-filling a fresh op_id) and return the parsed JSON body."""
    payload.setdefault("op_id", str(uuid.uuid4()))
    resp = client.post(f"/api/live/instances/{inst}/ops", json=payload)
    return resp, resp.get_json()


def _records(cur, inst, *, include_deleted=False):
    """Live records for an instance, in order_position order."""
    q = ("SELECT session_instance_tune_id, tune_id, name, record_type, deleted, "
         "confidence, started_by_person_id, order_position "
         "FROM session_instance_tune WHERE session_instance_id = %s")
    if not include_deleted:
        q += " AND deleted = FALSE"
    q += " ORDER BY order_position"
    cur.execute(q, (inst,))
    return cur.fetchall()


def _repertoire_count(cur, session_id, tune_id):
    """How many session_tune rows enroll this tune in this session (0 or 1)."""
    cur.execute("SELECT COUNT(*) FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (session_id, tune_id))
    return cur.fetchone()[0]


# --------------------------------------------------------------------------- #
# add_tune
# --------------------------------------------------------------------------- #

def test_add_tune_by_id(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
    assert resp.status_code == 200
    assert body["success"] is True
    assert body["record"]["tune_id"] == live_instance["reel"]
    assert body["record"]["record_type"] == "tune"
    assert body["event_id"] > 0

    rows = _records(db_cursor, inst)
    assert len(rows) == 1
    assert rows[0][1] == live_instance["reel"]
    # feed row appended
    db_cursor.execute("SELECT COUNT(*) FROM session_event WHERE session_instance_id = %s", (inst,))
    assert db_cursor.fetchone()[0] == 1


def test_add_tune_by_name_matches_catalog(client, authenticated_user, live_instance, db_cursor):
    """A raw name that matches a session tune links to it (tune_id set, not unlinked)."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", name="The Maid Behind the Bar")
    assert body["success"] is True
    assert body["record"]["tune_id"] == live_instance["maid"]


def test_add_tune_linked_stores_null_name(client, authenticated_user, live_instance, db_cursor):
    """name is override-only: a typeahead-style add ships the display name alongside
    tune_id, but the redundant copy is not persisted — the row falls back to the
    catalog name (so it follows later alias/name changes). The response still carries
    the display name via the server-side coalesce."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="add_tune",
                      tune_id=live_instance["reel"], name="The Test Reel")
    assert body["success"] is True
    assert body["record"]["name"] == "The Test Reel"
    rows = _records(db_cursor, inst)
    assert rows[0][1] == live_instance["reel"]
    assert rows[0][2] is None


def test_add_tune_by_name_match_stores_null_name(client, authenticated_user, live_instance, db_cursor):
    """A typed name that links (even as a case variant of the catalog name) stores
    NULL — normalization is case/accent/quote-insensitive."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="add_tune", name="the maid behind the bar")
    assert body["record"]["tune_id"] == live_instance["maid"]
    rows = _records(db_cursor, inst)
    assert rows[0][2] is None


def test_add_tune_alias_variant_stores_null_name(client, authenticated_user, live_instance, db_cursor):
    """A display name matching the session alias is just as redundant as the catalog
    name — the coalesce falls back to session_tune.alias."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="add_tune",
                      tune_id=live_instance["cooley"], name="The Tumbling Cooley")
    assert body["record"]["name"] == "The Tumbling Cooley"
    rows = _records(db_cursor, inst)
    assert rows[0][1] == live_instance["cooley"]
    assert rows[0][2] is None


def test_add_tune_divergent_name_kept_as_override(client, authenticated_user, live_instance, db_cursor):
    """A name that genuinely differs from both fallbacks is a real per-row override."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="add_tune",
                      tune_id=live_instance["reel"], name="Sonny's Version")
    assert body["record"]["name"] == "Sonny's Version"
    rows = _records(db_cursor, inst)
    assert rows[0][2] == "Sonny's Version"


def test_add_merged_tune_keeps_logged_name_as_override(client, authenticated_user, live_instance, db_cursor):
    """A remapped add (merged-away tune_id) keeps the name the logger saw — it differs
    from the canonical tune's name, so it survives normalization (spec 030)."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="add_tune",
                      tune_id=live_instance["merged"], name="The Merged Reel")
    assert body["record"]["tune_id"] == live_instance["reel"]
    rows = _records(db_cursor, inst)
    assert rows[0][2] == "The Merged Reel"


def test_add_tune_by_name_unlinked_when_unknown(client, authenticated_user, live_instance, db_cursor):
    """An unmatchable name stays unlinked: raw name kept, tune_id NULL."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", name="Zzqx Not A Real Tune 4711")
    assert body["success"] is True
    assert body["record"]["tune_id"] is None
    assert body["record"]["name"] == "Zzqx Not A Real Tune 4711"


def test_add_tune_requires_id_or_name(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune")
    assert body["success"] is False
    assert body["rejected"] is True
    assert body["reason"] == "invalid"


def test_add_tune_positioning_with_anchors(client, authenticated_user, live_instance, db_cursor):
    """after/before anchors produce a correct authoritative order (§C)."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])       # append
        _, b = _op(client, inst, op_type="add_tune", tune_id=live_instance["maid"])       # append after A
        # insert C between A and B via after_record_id = A
        _, c = _op(client, inst, op_type="add_tune", tune_id=live_instance["cooley"],
                   after_record_id=a["record"]["session_instance_tune_id"])
    ids_in_order = [r[0] for r in _records(db_cursor, inst)]
    assert ids_in_order == [a["record"]["session_instance_tune_id"],
                            c["record"]["session_instance_tune_id"],
                            b["record"]["session_instance_tune_id"]]


# --------------------------------------------------------------------------- #
# corroboration (duplicate-in-open-set collapse, §H30)
# --------------------------------------------------------------------------- #

def test_duplicate_append_collapses_to_corroborate(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, first = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, second = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
    # The second append does not create a row — it corroborates the first.
    assert second["op_type"] == "corroborate"
    assert second["record"]["session_instance_tune_id"] == first["record"]["session_instance_tune_id"]
    assert second["record"]["confidence"] == 100
    assert len(_records(db_cursor, inst)) == 1


def test_no_merge_keeps_both(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, second = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"], no_merge=True)
    assert second["op_type"] == "add_tune"
    assert len(_records(db_cursor, inst)) == 2


# --------------------------------------------------------------------------- #
# set_break
# --------------------------------------------------------------------------- #

def test_set_break_insert_splits_sets(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, b = _op(client, inst, op_type="add_tune", tune_id=live_instance["maid"])
        _, brk = _op(client, inst, op_type="set_break", action="insert",
                     after_record_id=a["record"]["session_instance_tune_id"])
    rows = _records(db_cursor, inst)
    types = [r[3] for r in rows]
    assert types == ["tune", "break", "tune"]  # A | break | B


def test_set_break_remove(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, brk = _op(client, inst, op_type="set_break", action="insert",
                     after_record_id=a["record"]["session_instance_tune_id"])
        _, rem = _op(client, inst, op_type="set_break", action="remove",
                     record_id=brk["record"]["session_instance_tune_id"])
    assert rem["removed"] is True
    assert all(r[3] != "break" for r in _records(db_cursor, inst, include_deleted=True))


def test_set_break_remove_rejects_non_break(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, rem = _op(client, inst, op_type="set_break", action="remove",
                     record_id=a["record"]["session_instance_tune_id"])
    assert rem["success"] is False
    assert rem["reason"] == "wrong_record_type"


# --------------------------------------------------------------------------- #
# remove_tune (soft tombstone)
# --------------------------------------------------------------------------- #

def test_remove_tune_soft_deletes(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        rid = a["record"]["session_instance_tune_id"]
        _, rem = _op(client, inst, op_type="remove_tune", record_id=rid)
    assert rem["record"]["deleted"] is True
    assert _records(db_cursor, inst) == []  # gone from live view
    rows = _records(db_cursor, inst, include_deleted=True)
    assert len(rows) == 1 and rows[0][4] is True  # but the row (tombstone) remains


def test_remove_tune_idempotent(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        rid = a["record"]["session_instance_tune_id"]
        _op(client, inst, op_type="remove_tune", record_id=rid)
        _, second = _op(client, inst, op_type="remove_tune", record_id=rid)
    assert second.get("already_removed") is True


# --------------------------------------------------------------------------- #
# change_tune
# --------------------------------------------------------------------------- #

def test_change_tune_rename_and_unlink(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        rid = a["record"]["session_instance_tune_id"]
        _, ren = _op(client, inst, op_type="change_tune", record_id=rid, name="Renamed Tune")
        assert ren["record"]["name"] == "Renamed Tune"
        _, unl = _op(client, inst, op_type="change_tune", record_id=rid, unlink=True)
    assert unl["record"]["tune_id"] is None


def test_change_tune_relink_clears_redundant_name(client, authenticated_user, live_instance, db_cursor):
    """Relink ships the new tune's display name alongside tune_id (the client always
    does); the redundant copy stores as NULL — which also clears any stale override
    the row carried while unlinked."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", name="mystery reel xyz")
        rid = a["record"]["session_instance_tune_id"]
        _, rel = _op(client, inst, op_type="change_tune", record_id=rid,
                     tune_id=live_instance["reel"], name="The Test Reel")
    assert rel["record"]["tune_id"] == live_instance["reel"]
    assert rel["record"]["name"] == "The Test Reel"
    db_cursor.execute("SELECT name FROM session_instance_tune WHERE session_instance_tune_id = %s", (rid,))
    assert db_cursor.fetchone()[0] is None


def test_change_tune_rename_stores_override(client, authenticated_user, live_instance, db_cursor):
    """A rename that differs from the fallbacks persists as a genuine per-row override."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        rid = a["record"]["session_instance_tune_id"]
        _, ren = _op(client, inst, op_type="change_tune", record_id=rid, name="Renamed Tune")
    assert ren["record"]["name"] == "Renamed Tune"
    db_cursor.execute("SELECT name, tune_id FROM session_instance_tune WHERE session_instance_tune_id = %s", (rid,))
    assert db_cursor.fetchone() == ("Renamed Tune", live_instance["reel"])


def test_change_tune_no_fields_rejected(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, resp = _op(client, inst, op_type="change_tune",
                      record_id=a["record"]["session_instance_tune_id"])
    assert resp["success"] is False
    assert resp["reason"] == "invalid"


# --------------------------------------------------------------------------- #
# session_tune (repertoire) enrollment (spec 025)
# --------------------------------------------------------------------------- #

def test_add_linked_tune_enrolls_in_repertoire(client, authenticated_user, live_instance, db_cursor):
    """Adding a linked tune that isn't yet in the session's repertoire enrolls it."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    assert _repertoire_count(db_cursor, sid, newt) == 0
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=newt)
    assert _repertoire_count(db_cursor, sid, newt) == 1
    # And a history row was recorded for the enrollment.
    db_cursor.execute(
        "SELECT COUNT(*) FROM session_tune_history WHERE session_id = %s AND tune_id = %s AND operation = 'INSERT'",
        (sid, newt))
    assert db_cursor.fetchone()[0] == 1


def test_add_tune_enrollment_idempotent(client, authenticated_user, live_instance, db_cursor):
    """A second add of the same tune doesn't create a duplicate repertoire row or error."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=newt)
        # Second add lands in a different set so it isn't collapsed into a corroboration.
        _op(client, inst, op_type="set_break", action="insert")
        resp, body = _op(client, inst, op_type="add_tune", tune_id=newt)
    assert body["success"] is True
    assert _repertoire_count(db_cursor, sid, newt) == 1


def test_add_unlinked_tune_does_not_enroll(client, authenticated_user, live_instance, db_cursor):
    """An unmatchable (unlinked) add creates no session_tune row."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", name="Zzqx Not A Real Tune 4711")
    db_cursor.execute("SELECT COUNT(*) FROM session_tune WHERE session_id = %s", (sid,))
    # Only the three pre-enrolled catalog tunes remain; nothing new was added.
    assert db_cursor.fetchone()[0] == 3


def test_change_tune_relink_enrolls_new_tune(client, authenticated_user, live_instance, db_cursor):
    """Relinking a record to a new tune_id enrolls that tune in the repertoire."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        # Start from an unlinked row so the relink is the first thing to introduce newt.
        _, a = _op(client, inst, op_type="add_tune", name="Zzqx Not A Real Tune 4711")
        rid = a["record"]["session_instance_tune_id"]
        assert _repertoire_count(db_cursor, sid, newt) == 0
        _op(client, inst, op_type="change_tune", record_id=rid, tune_id=newt)
    assert _repertoire_count(db_cursor, sid, newt) == 1


# --------------------------------------------------------------------------- #
# session_tune (repertoire) un-enrollment on delete (spec 045)
#
# Logging a tune enrolls it; deleting the last play un-enrolls it again, so a
# search-add-then-delete doesn't leave an orphan in the session's tune list.
# --------------------------------------------------------------------------- #

def test_remove_tune_unenrolls_auto_enrolled_tune(client, authenticated_user, live_instance, db_cursor):
    """The reported bug: add a tune from search, delete it, repertoire is clean again."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        assert _repertoire_count(db_cursor, sid, newt) == 1
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, newt) == 0
    # The un-enrollment is audited like the enrollment was.
    db_cursor.execute(
        "SELECT COUNT(*) FROM session_tune_history WHERE session_id = %s AND tune_id = %s AND operation = 'DELETE'",
        (sid, newt))
    assert db_cursor.fetchone()[0] == 1


def test_remove_tune_keeps_repertoire_while_another_play_lives(
    client, authenticated_user, live_instance, db_cursor
):
    """Only the LAST live play un-enrolls; a tune played twice stays in the repertoire."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        # A second set, so the add isn't collapsed into a corroboration of the first.
        _op(client, inst, op_type="set_break", action="insert")
        _op(client, inst, op_type="add_tune", tune_id=newt)
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, newt) == 1


def test_remove_tune_keeps_repertoire_when_played_another_night(
    client, authenticated_user, live_instance, db_cursor
):
    """A play at ANOTHER instance of the same session still counts — deleting tonight's
    play must not drop a tune the session plays regularly."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    other = INST + 1
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date)"
                    " VALUES (%s, %s, '2026-02-08')", (other, sid))
        cur.execute("INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type)"
                    " VALUES (%s, %s, 'a0', 'tune')", (other, newt))
        conn.commit()
        with authenticated_user:
            _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
            _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
        assert _repertoire_count(db_cursor, sid, newt) == 1
    finally:
        cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (other,))
        cur.execute("DELETE FROM session_instance_tune_history WHERE session_instance_id = %s", (other,))
        cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (other,))
        conn.commit()
        cur.close()
        conn.close()


def test_remove_tune_never_unenrolls_manually_added(client, authenticated_user, live_instance, db_cursor):
    """A repertoire entry someone added on purpose survives a log-then-delete (spec 045)."""
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    assert _repertoire_count(db_cursor, sid, reel) == 1
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=reel)
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, reel) == 1


def test_remove_tune_never_unenrolls_curated_row(client, authenticated_user, live_instance, db_cursor):
    """Belt and braces: a row carrying a session alias stays even with the flag cleared."""
    sid, inst, cooley = live_instance["session_id"], live_instance["instance_id"], live_instance["cooley"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE session_tune SET manually_added = FALSE WHERE session_id = %s AND tune_id = %s",
                (sid, cooley))
    conn.commit()
    cur.close()
    conn.close()
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=cooley)
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, cooley) == 1


def test_add_tune_pane_marks_repertoire_entry_protected(
    client, authenticated_user, live_instance, db_cursor
):
    """End to end: a tune added through the add-tune pane is flagged manually_added,
    so logging and then deleting it later leaves the entry standing."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        resp = client.post("/api/sessions/liveops-test/tunes", json={"tune_id": newt})
        assert resp.status_code == 201, resp.data
        db_cursor.execute("SELECT manually_added FROM session_tune WHERE session_id = %s AND tune_id = %s",
                          (sid, newt))
        assert db_cursor.fetchone()[0] is True
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, newt) == 1


def test_curating_an_auto_enrolled_row_protects_it(
    client, authenticated_admin_user, live_instance, db_cursor
):
    """Stating a session-scoped key on an auto-enrolled row (spec 037) makes it
    deliberate, so it stops being cleanup-eligible."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_admin_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        db_cursor.execute("SELECT manually_added FROM session_tune WHERE session_id = %s AND tune_id = %s",
                          (sid, newt))
        assert db_cursor.fetchone()[0] is False
        resp = client.put(f"/api/sessions/liveops-test/tunes/{newt}", json={"key": "Ador"})
        assert resp.status_code == 200, resp.data
        _op(client, inst, op_type="remove_tune", record_id=a["record"]["session_instance_tune_id"])
    assert _repertoire_count(db_cursor, sid, newt) == 1


def test_remove_tunes_bulk_unenrolls(client, authenticated_user, live_instance, db_cursor):
    """The bulk delete (spec 029 selection mode) un-enrolls too, once per tune."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        _op(client, inst, op_type="set_break", action="insert")
        _, b = _op(client, inst, op_type="add_tune", tune_id=newt)
        ids = [a["record"]["session_instance_tune_id"], b["record"]["session_instance_tune_id"]]
        _op(client, inst, op_type="remove_tunes", record_ids=ids)
    assert _repertoire_count(db_cursor, sid, newt) == 0


def test_restore_tunes_reenrolls(client, authenticated_user, live_instance, db_cursor):
    """Undo is a true round trip: restoring the play puts the repertoire row back."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        rid = a["record"]["session_instance_tune_id"]
        _op(client, inst, op_type="remove_tunes", record_ids=[rid])
        assert _repertoire_count(db_cursor, sid, newt) == 0
        _op(client, inst, op_type="restore_tunes", record_ids=[rid])
    assert _repertoire_count(db_cursor, sid, newt) == 1


def test_change_tune_unlink_unenrolls_old_tune(client, authenticated_user, live_instance, db_cursor):
    """Unlinking the only play of a tune strands its repertoire row — clean it up."""
    sid, inst, newt = live_instance["session_id"], live_instance["instance_id"], live_instance["newt"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        rid = a["record"]["session_instance_tune_id"]
        assert _repertoire_count(db_cursor, sid, newt) == 1
        _op(client, inst, op_type="change_tune", record_id=rid, unlink=True, name="Some Other Name")
    assert _repertoire_count(db_cursor, sid, newt) == 0


def test_change_tune_relink_unenrolls_previous_tune(client, authenticated_user, live_instance, db_cursor):
    """Relinking onto a different tune enrolls the new one and drops the stranded old one."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    newt, maid = live_instance["newt"], live_instance["maid"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=newt)
        rid = a["record"]["session_instance_tune_id"]
        _op(client, inst, op_type="change_tune", record_id=rid, tune_id=maid)
    assert _repertoire_count(db_cursor, sid, newt) == 0
    assert _repertoire_count(db_cursor, sid, maid) == 1


def test_merged_tune_id_remaps_to_canonical(client, authenticated_user, live_instance, db_cursor):
    """A direct add with a merged-away tune_id (stale typeahead cache / replayed offline
    op) remaps to the canonical tune (spec 030): the record links to the canonical id,
    the ack carries remapped_from, and the tombstoned id is never enrolled."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    reel, merged = live_instance["reel"], live_instance["merged"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=merged)
    assert body["success"] is True
    assert body["record"]["tune_id"] == reel
    assert body["remapped_from"] == merged
    assert _repertoire_count(db_cursor, sid, merged) == 0


def test_change_tune_relink_to_merged_id_remaps(client, authenticated_user, live_instance, db_cursor):
    """Relinking a record to a merged-away id lands on the canonical tune (spec 030)."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    reel, merged = live_instance["reel"], live_instance["merged"]
    with authenticated_user:
        _, add_body = _op(client, inst, op_type="add_tune", name="mystery reel xyz")
        rid = add_body["record"]["session_instance_tune_id"]
        resp, body = _op(client, inst, op_type="change_tune", record_id=rid, tune_id=merged)
    assert body["success"] is True
    assert body["record"]["tune_id"] == reel
    assert body["remapped_from"] == merged
    assert _repertoire_count(db_cursor, sid, merged) == 0


# --------------------------------------------------------------------------- #
# thesession.org import folded into add_tune (spec 026)
# --------------------------------------------------------------------------- #

def _no_fetch(reason):
    """A stand-in importer that fails the test if any network fetch is attempted."""
    def _boom(tune_id):
        raise AssertionError(reason)
    return _boom


def test_add_tune_by_thesession_id_imports_links_enrolls(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """thesession_id for a tune we don't have imports it (tune + default setting), logs it
    LINKED, and enrolls it in the repertoire — all in one op."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", lambda tid: dict(FAKE_TS_TUNE))
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", thesession_id=IMPORT_ID)
    assert resp.status_code == 200 and body["success"] is True
    assert body["record"]["tune_id"] == IMPORT_ID
    assert body["record"]["name"] == "The Imported Reel"
    assert body.get("import_failed") is None
    # tune row created in the catalog
    db_cursor.execute("SELECT name FROM tune WHERE tune_id = %s", (IMPORT_ID,))
    assert db_cursor.fetchone()[0] == "The Imported Reel"
    # default setting stored with ABC; image is left NULL (rendered lazily on first view)
    db_cursor.execute("SELECT tune_id, abc, image FROM tune_setting WHERE setting_id = %s", (IMPORT_SETTING,))
    ts = db_cursor.fetchone()
    assert ts is not None and ts[0] == IMPORT_ID and ts[1] and ts[2] is None
    # enrolled in the session repertoire (via the shared spec-025 enrollment)
    assert _repertoire_count(db_cursor, sid, IMPORT_ID) == 1


def test_add_tune_thesession_id_idempotent_by_op_id(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """A retried import op (same op_id) dedupes: no second tune/setting/record, no re-fetch."""
    import live_logging_routes
    calls = {"n": 0}
    def _once(tid):
        calls["n"] += 1
        return dict(FAKE_TS_TUNE)
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", _once)
    inst = live_instance["instance_id"]
    op_id = str(uuid.uuid4())
    with authenticated_user:
        _op(client, inst, op_type="add_tune", thesession_id=IMPORT_ID, op_id=op_id)
        resp, body = _op(client, inst, op_type="add_tune", thesession_id=IMPORT_ID, op_id=op_id)
    assert body.get("duplicate") is True
    assert calls["n"] == 1  # the retry returned the cached ack without importing again
    assert len(_records(db_cursor, inst)) == 1


def test_add_tune_thesession_id_already_local_no_fetch(
        client, authenticated_user, live_instance, monkeypatch):
    """If we already have the tune, thesession_id links it without any network fetch."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune",
                        _no_fetch("should not fetch a tune already in the catalog"))
    inst, reel = live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", thesession_id=reel)
    assert body["success"] is True
    assert body["record"]["tune_id"] == reel


def test_add_tune_thesession_id_merged_follows_redirect(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """A merged/redirect thesession id logs the canonical tune (never the merged id)."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune",
                        _no_fetch("a known redirect resolves locally, no fetch"))
    sid, inst, reel, merged = (live_instance["session_id"], live_instance["instance_id"],
                               live_instance["reel"], live_instance["merged"])
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", thesession_id=merged)
    assert body["success"] is True
    assert body["record"]["tune_id"] == reel  # canonical, not the merged id
    assert _repertoire_count(db_cursor, sid, merged) == 0


def test_add_tune_thesession_id_import_failure_logs_unlinked(
        client, authenticated_user, live_instance, monkeypatch):
    """A failed import (fake/dead id) does NOT reject the op: the entry is logged unlinked and
    the ack carries import_failed so the client settles it as an unmatched row."""
    import live_logging_routes
    from api_routes import TuneImportError
    def _fail(tid):
        raise TuneImportError(f"Tune #{tid} not found on thesession.org", 404)
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", _fail)
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", thesession_id=IMPORT_ID)
    assert resp.status_code == 200 and body["success"] is True
    assert body["record"]["tune_id"] is None
    assert body["record"]["name"] == f"#{IMPORT_ID}"
    assert body["import_failed"] is True


# --------------------------------------------------------------------------- #
# chosen setting on add (spec 032: the preview's settings pager)
# --------------------------------------------------------------------------- #

def _session_setting(cur, sid, tid):
    cur.execute("SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s", (sid, tid))
    row = cur.fetchone()
    return row[0] if row else None


def test_add_tune_chosen_setting_becomes_session_preference(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """No session-level override yet -> the chosen setting becomes the session's
    preferred setting (session_tune.setting_id); the row itself carries no override."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune",
                        _no_fetch("locally-cached setting must not fetch"))
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL)
    assert body["success"] is True
    assert body["setting_applied"] == "session"
    assert _session_setting(db_cursor, sid, reel) == SET_LOCAL
    assert body["record"]["setting_override"] is None


def test_add_tune_chosen_setting_instance_only_when_session_prefers_another(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """The session already prefers a different NON-DEFAULT setting -> the chosen one
    applies to THIS row only (setting_override), importing it from thesession.org if
    needed. (A default-valued preference would be replaced instead — see the
    replaces_auto_default test.)"""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", lambda tid: dict(FAKE_TS_REEL))
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL2)  # explicit non-default pref
        # no_merge: a second add of the same tune would otherwise corroborate, not insert
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_REMOTE, no_merge=True)
    assert body["success"] is True
    assert body["setting_applied"] == "instance"
    assert body["record"]["setting_override"] == SET_REMOTE
    assert _session_setting(db_cursor, sid, reel) == SET_LOCAL2  # session preference untouched
    # the remote setting was imported ("!" unfolded to a newline)
    db_cursor.execute("SELECT tune_id, abc FROM tune_setting WHERE setting_id = %s", (SET_REMOTE,))
    row = db_cursor.fetchone()
    assert row is not None and row[0] == reel and "\n" in row[1]


def test_add_tune_chosen_setting_already_preferred_noop(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """Choosing the setting the session already prefers changes nothing."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune",
                        _no_fetch("locally-cached setting must not fetch"))
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL)
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL, no_merge=True)
    assert body["success"] is True
    assert body["setting_applied"] == "already"
    assert body["record"]["setting_override"] is None
    assert _session_setting(db_cursor, sid, reel) == SET_LOCAL


def test_add_tune_chosen_setting_import_failure_is_soft(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """A chosen setting that can't be imported never fails the op: the tune logs
    normally and the ack carries setting_failed."""
    import live_logging_routes
    from api_routes import TuneImportError

    def _fail(tid):
        raise TuneImportError("thesession.org is down", 502)

    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", _fail)
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_REMOTE)
    assert body["success"] is True
    assert body["record"]["tune_id"] == reel
    assert body.get("setting_applied") is None
    assert "setting_failed" in body
    assert _session_setting(db_cursor, sid, reel) is None


def test_add_tune_chosen_setting_survives_corroboration(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """A duplicate append collapses into a corroboration — but an explicitly chosen
    setting still applies (to the corroborated row / session), never silently dropped."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", lambda tid: dict(FAKE_TS_REEL))
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL2)  # non-default pref
        # same tune again, pure append -> corroborates; the chosen (different) setting
        # must land on the corroborated row as an override
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_REMOTE)
    assert body["success"] is True
    assert body["op_type"] == "corroborate"
    assert body["setting_applied"] == "instance"
    assert body["record"]["setting_override"] == SET_REMOTE
    assert _session_setting(db_cursor, sid, reel) == SET_LOCAL2


def test_enrollment_fills_default_setting_and_chosen_replaces_it(
        client, authenticated_user, live_instance, db_cursor, monkeypatch):
    """Enrollment always stores a setting_id — the tune's default when nothing was
    chosen (spec 032). And because an auto-filled default is not a real preference,
    a later explicitly chosen setting REPLACES it at the session level."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", lambda tid: dict(FAKE_TS_REEL))
    sid, inst, newt, reel = (live_instance["session_id"], live_instance["instance_id"],
                             live_instance["newt"], live_instance["reel"])
    with authenticated_user:
        # NEWT enrolls on first add; its default (only) setting is stored automatically.
        _op(client, inst, op_type="add_tune", tune_id=newt)
        # REEL: choose its default first (== auto-fill value), then a different setting —
        # the default-valued preference is replaceable, so the session pref moves.
        _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL)
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel, setting_id=SET_LOCAL2, no_merge=True)
    assert _session_setting(db_cursor, sid, newt) == SET_NEWT
    assert body["success"] is True
    assert body["setting_applied"] == "session"
    assert body["record"]["setting_override"] is None
    assert _session_setting(db_cursor, sid, reel) == SET_LOCAL2


def test_add_tune_without_setting_id_leaves_settings_alone(
        client, authenticated_user, live_instance, db_cursor):
    """The one-tap paths (＋ rail, composer) send no setting_id -> no setting writes."""
    sid, inst, reel = live_instance["session_id"], live_instance["instance_id"], live_instance["reel"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=reel)
    assert body["success"] is True
    assert body.get("setting_applied") is None
    assert body["record"]["setting_override"] is None
    assert _session_setting(db_cursor, sid, reel) is None


# --------------------------------------------------------------------------- #
# set_confidence
# --------------------------------------------------------------------------- #

def test_set_confidence_and_corroboration(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"], confidence=50)
        rid = a["record"]["session_instance_tune_id"]
        _, conf = _op(client, inst, op_type="set_confidence", record_id=rid, confidence=100)
    assert conf["record"]["confidence"] == 100
    db_cursor.execute("SELECT COUNT(*) FROM corroboration WHERE record_id = %s", (rid,))
    assert db_cursor.fetchone()[0] == 1


# --------------------------------------------------------------------------- #
# attribute_set_starter
# --------------------------------------------------------------------------- #

def test_attribute_set_starter_applies_to_whole_set(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    pid = live_instance["person_id"]
    with authenticated_user:
        _, a = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"])
        _, b = _op(client, inst, op_type="add_tune", tune_id=live_instance["maid"])
        _, res = _op(client, inst, op_type="attribute_set_starter",
                     record_id=a["record"]["session_instance_tune_id"], person_id=pid)
    assert len(res["records"]) == 2  # both tunes in the open set
    for r in _records(db_cursor, inst):
        assert r[6] == pid  # started_by_person_id


# --------------------------------------------------------------------------- #
# metadata ops
# --------------------------------------------------------------------------- #

def test_edit_notes(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, body = _op(client, inst, op_type="edit_notes", notes="Great craic tonight")
    assert body["notes"] == "Great craic tonight"
    db_cursor.execute("SELECT comments FROM session_instance WHERE session_instance_id = %s", (inst,))
    assert db_cursor.fetchone()[0] == "Great craic tonight"


def test_mark_complete_then_incomplete(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, done = _op(client, inst, op_type="mark_complete")
        assert done["log_complete"] is True
        db_cursor.execute("SELECT log_complete_date FROM session_instance WHERE session_instance_id = %s", (inst,))
        assert db_cursor.fetchone()[0] is not None
        _, undo = _op(client, inst, op_type="mark_incomplete")
    assert undo["log_complete"] is False
    db_cursor.execute("SELECT log_complete_date FROM session_instance WHERE session_instance_id = %s", (inst,))
    assert db_cursor.fetchone()[0] is None


# --------------------------------------------------------------------------- #
# idempotency (§C)
# --------------------------------------------------------------------------- #

def test_idempotent_replay_same_op_id(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    op_id = str(uuid.uuid4())
    with authenticated_user:
        _, first = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"], op_id=op_id)
        _, second = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"], op_id=op_id)
    assert first["success"] is True and "duplicate" not in first
    assert second["duplicate"] is True
    assert second["event_id"] == first["event_id"]
    # exactly one tune row and one feed event despite two POSTs
    assert len(_records(db_cursor, inst)) == 1
    db_cursor.execute("SELECT COUNT(*) FROM session_event WHERE session_instance_id = %s", (inst,))
    assert db_cursor.fetchone()[0] == 1


def test_op_id_must_be_uuid(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=live_instance["reel"], op_id="not-a-uuid")
    assert resp.status_code == 400
    assert body["success"] is False


# --------------------------------------------------------------------------- #
# rejection / errors
# --------------------------------------------------------------------------- #

def test_change_missing_record_rejected(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="change_tune", record_id=99999999, name="x")
    # OpRejected surfaces as HTTP 200 with success=False + a machine reason (§E),
    # not a 4xx — the affected client renders the reason itself.
    assert resp.status_code == 200
    assert body["success"] is False
    assert body["rejected"] is True
    assert body["reason"] == "not_found"


def test_unknown_op_type(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="frobnicate")
    assert resp.status_code == 400
    assert body["success"] is False


def test_unknown_instance_404(client, authenticated_user):
    with authenticated_user:
        resp, body = _op(client, 99999999, op_type="add_tune", name="x")
    assert resp.status_code == 404
    assert body["success"] is False


def test_ops_require_auth(client, live_instance):
    """No authenticated user -> 401 (api_login_required)."""
    resp = client.post(f"/api/live/instances/{live_instance['instance_id']}/ops",
                        json={"op_type": "add_tune", "name": "x", "op_id": str(uuid.uuid4())})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# _position_for — focused unit test (no HTTP; rolled back via db_cursor)
# --------------------------------------------------------------------------- #

def test_position_for_branches(db_cursor):
    """append -> after -> before, driven directly against an uncommitted instance."""
    db_cursor.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                      (9310, "Pos Test", "pos-test"))
    db_cursor.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, %s)",
                      (9391, 9310, "2026-03-01"))

    def add(pos):
        db_cursor.execute(
            "INSERT INTO session_instance_tune (session_instance_id, name, order_position, record_type) "
            "VALUES (%s, %s, %s, 'tune') RETURNING session_instance_tune_id",
            (9391, "t", pos))
        return db_cursor.fetchone()[0]

    # empty instance -> append yields the same as generate_append_position(None)
    p_append = _position_for(db_cursor, 9391, None, None)
    assert p_append == generate_append_position(None)
    a = add(p_append)

    p_b = _position_for(db_cursor, 9391, None, None)  # append after A
    assert p_b > p_append
    b = add(p_b)

    # insert between A and B via after=A
    p_mid = _position_for(db_cursor, 9391, a, None)
    assert p_append < p_mid < p_b

    # insert before B via before=B (also lands between A and B)
    p_before = _position_for(db_cursor, 9391, None, b)
    assert p_append < p_before < p_b


# --------------------------------------------------------------------------- #
# bulk ops (spec 029): move_tunes / remove_tunes / restore_tunes
# --------------------------------------------------------------------------- #

def _seed_sets(client, inst, sets):
    """Log unlinked tunes as sets (breaks between). Returns (name->id, [break ids])."""
    ids, breaks = {}, []
    for si, names in enumerate(sets):
        for name in names:
            _, r = _op(client, inst, op_type="add_tune", name=name)
            ids[name] = r["record"]["session_instance_tune_id"]
        if si < len(sets) - 1:
            _, b = _op(client, inst, op_type="set_break", action="insert",
                       after_record_id=ids[names[-1]])
            breaks.append(b["record"]["session_instance_tune_id"])
    return ids, breaks


def _shape(cur, inst):
    """[(record_type, name-or-'|')] in live order — easy structural assertions."""
    return [("|" if r[3] == "break" else r[2]) for r in _records(cur, inst)]


def test_move_tunes_within_set(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"]], after_record_id=ids["mvA"])
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "mvC", "mvB"]
    assert res["moved_ids"] == [ids["mvC"]]


def test_move_tunes_across_sets_welds(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC", "mvD"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvD"]], after_record_id=ids["mvA"])
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "mvD", "mvB", "|", "mvC"]


def test_move_tunes_new_set_inserts_boundary_breaks(client, authenticated_user, live_instance, db_cursor):
    """Drop on an inter-set seam (before C, new_set) -> block becomes its own set."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC", "mvD"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvB"]], before_record_id=ids["mvC"], new_set=True)
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "|", "mvB", "|", "mvC", "mvD"]


def test_move_tunes_new_set_at_very_start(client, authenticated_user, live_instance, db_cursor):
    """new_set before the first tune: boundary break only on the tune side."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC", "mvD"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"], ids["mvD"]], before_record_id=ids["mvA"], new_set=True)
    assert res["success"] is True
    # no leading break above the block; one break separates it from A's set; the
    # original inter-set break is now orphaned (nothing after it) BUT a trailing
    # break is a legitimate closed end, so it stays.
    assert _shape(db_cursor, inst) == ["mvC", "mvD", "|", "mvA", "mvB", "|"]


def test_move_tunes_multiset_block_preserves_interior_breaks(client, authenticated_user, live_instance, db_cursor):
    """Interior breaks travel: a 2-set block dropped at the start is still 2 sets."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC", "mvD"], ["mvE", "mvF"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"], ids["mvD"], ids["mvE"], ids["mvF"]],
                     before_record_id=ids["mvA"], new_set=True)
    assert res["success"] is True
    # block [C D | E F] + boundary break, then A B; break formerly after B is now
    # trailing (closed end) and stays.
    assert _shape(db_cursor, inst) == ["mvC", "mvD", "|", "mvE", "mvF", "|", "mvA", "mvB", "|"]


def test_move_tunes_source_remnants_merge(client, authenticated_user, live_instance, db_cursor):
    """Taking [B C | D] out of A B C | D E leaves A and E adjacent -> they merge."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"], ["mvD", "mvE"], ["mvF"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvB"], ids["mvC"], ids["mvD"]],
                     after_record_id=ids["mvF"])
    assert res["success"] is True
    # A+E merged (their break travelled with the block); block welds onto open set F.
    assert _shape(db_cursor, inst) == ["mvA", "mvE", "|", "mvF", "mvB", "mvC", "|", "mvD"]


def test_move_tunes_orphan_break_cleanup(client, authenticated_user, live_instance, db_cursor):
    """Emptying the first set leaves a leading break -> deleted in the same txn."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, breaks = _seed_sets(client, inst, [["mvA"], ["mvB", "mvC"]])
        _, res = _op(client, inst, op_type="move_tunes", record_ids=[ids["mvA"]])  # append
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvB", "mvC", "mvA"]
    assert breaks[0] in res["removed_break_ids"]


def test_move_tunes_back_to_back_breaks_collapse(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC"], ["mvD"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"]], after_record_id=ids["mvA"])
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "mvC", "mvB", "|", "mvD"]


def test_move_tunes_anchor_inside_block_rejected(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvA"], ids["mvB"]], after_record_id=ids["mvA"])
    assert res["success"] is False
    assert res["reason"] == "invalid_anchor"


def test_move_tunes_vanished_anchor_appends(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _op(client, inst, op_type="remove_tune", record_id=ids["mvC"])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvA"]], after_record_id=ids["mvC"])  # deleted anchor
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvB", "mvA"]


def test_move_tunes_server_resorts_stale_client_order(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC", "mvD"]])
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"], ids["mvA"]])  # scrambled; A precedes C today
    assert res["success"] is True
    # non-contiguous ids re-pack in CURRENT relative order (A then C), appended.
    assert _shape(db_cursor, inst) == ["mvB", "mvD", "mvA", "mvC"]


def test_move_tunes_started_by_untouched(client, authenticated_user, live_instance, db_cursor):
    """A move NEVER stamps/clears started_by — per-tune claims are durable (spec 029 F)."""
    inst = live_instance["instance_id"]
    pid = live_instance["person_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"], ["mvC", "mvD"]])
        _op(client, inst, op_type="attribute_set_starter", record_id=ids["mvC"], person_id=pid)
        _, res = _op(client, inst, op_type="move_tunes",
                     record_ids=[ids["mvC"]], after_record_id=ids["mvA"])
    assert res["success"] is True
    rows = {r[2]: r for r in _records(db_cursor, inst)}
    assert rows["mvC"][6] == pid          # claim survives the move
    assert rows["mvA"][6] is None         # destination set untouched
    assert rows["mvD"][6] == pid          # left-behind set-mate untouched


def test_move_tunes_idempotent_replay(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    op_id = str(uuid.uuid4())
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _, first = _op(client, inst, op_type="move_tunes", op_id=op_id,
                       record_ids=[ids["mvC"]], after_record_id=ids["mvA"])
        _, replay = _op(client, inst, op_type="move_tunes", op_id=op_id,
                        record_ids=[ids["mvC"]], after_record_id=ids["mvA"])
    assert replay["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "mvC", "mvB"]  # applied exactly once


def test_move_tunes_requires_ids(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        _, res = _op(client, inst, op_type="move_tunes", record_ids=[])
    assert res["success"] is False
    assert res["reason"] == "invalid"


def test_remove_tunes_bulk_tombstones(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _, res = _op(client, inst, op_type="remove_tunes",
                     record_ids=[ids["mvA"], ids["mvC"]])
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvB"]
    assert {r["session_instance_tune_id"] for r in res["records"]} == {ids["mvA"], ids["mvC"]}
    assert all(r["deleted"] for r in res["records"])


def test_remove_tunes_skips_already_deleted(client, authenticated_user, live_instance, db_cursor):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"]])
        _op(client, inst, op_type="remove_tune", record_id=ids["mvA"])
        _, res = _op(client, inst, op_type="remove_tunes",
                     record_ids=[ids["mvA"], ids["mvB"]])
    assert res["success"] is True
    assert [r["session_instance_tune_id"] for r in res["records"]] == [ids["mvB"]]
    assert _shape(db_cursor, inst) == []


def test_remove_tunes_rejects_breaks(client, authenticated_user, live_instance):
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, breaks = _seed_sets(client, inst, [["mvA"], ["mvB"]])
        _, res = _op(client, inst, op_type="remove_tunes", record_ids=[breaks[0]])
    assert res["success"] is False
    assert res["reason"] == "wrong_record_type"


def test_restore_tunes_round_trip(client, authenticated_user, live_instance, db_cursor):
    """Delete then restore: rows come back live in their original positions."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB", "mvC"]])
        _op(client, inst, op_type="remove_tunes", record_ids=[ids["mvA"], ids["mvB"]])
        _, res = _op(client, inst, op_type="restore_tunes",
                     record_ids=[ids["mvA"], ids["mvB"]])
    assert res["success"] is True
    assert _shape(db_cursor, inst) == ["mvA", "mvB", "mvC"]  # original order preserved
    assert all(not r["deleted"] for r in res["records"])


def test_restore_tunes_only_flips_tombstones(client, authenticated_user, live_instance, db_cursor):
    """Restoring a mix where one id was never deleted only touches the tombstoned one."""
    inst = live_instance["instance_id"]
    with authenticated_user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"]])
        _op(client, inst, op_type="remove_tune", record_id=ids["mvA"])
        _, res = _op(client, inst, op_type="restore_tunes",
                     record_ids=[ids["mvA"], ids["mvB"]])
    assert res["success"] is True
    assert [r["session_instance_tune_id"] for r in res["records"]] == [ids["mvA"]]
    assert _shape(db_cursor, inst) == ["mvA", "mvB"]


# --- People-tracking flags (spec 039) -------------------------------------------

def _set_flags(db_cursor, session_id, *, attendance, starters):
    """Flip a session's people-tracking flags. The op endpoint reads its OWN committed
    connection, so this must commit — db_cursor is READ COMMITTED and the fixture cleans
    the session up afterward regardless of flag state."""
    db_cursor.execute(
        "UPDATE session SET track_attendance = %s, track_set_starters = %s WHERE session_id = %s",
        (attendance, starters, session_id),
    )
    db_cursor.connection.commit()


def test_attendance_ops_refused_when_attendance_off(client, authenticated_user, live_instance, db_cursor):
    """A stale client, a queued offline op, or a direct POST must not slip a check-in into
    a session that has turned attendance off — the op is refused, not merely UI-hidden."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    _set_flags(db_cursor, sid, attendance=False, starters=False)
    with authenticated_user as user:
        resp, body = _op(client, inst, op_type="attendance_add", person_id=user.person_id)
    assert resp.status_code == 200  # the endpoint answers; the OP is rejected
    assert body["success"] is False and body["rejected"] is True
    assert body["reason"] == "people_tracking_off"
    db_cursor.execute(
        "SELECT COUNT(*) FROM session_instance_person WHERE session_instance_id = %s", (inst,)
    )
    assert db_cursor.fetchone()[0] == 0


def test_set_starter_refused_when_starters_off(client, authenticated_user, live_instance, db_cursor):
    """Attendance may stay on while starters are off; the starter op is refused on its own."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    _set_flags(db_cursor, sid, attendance=True, starters=False)
    with authenticated_user as user:
        ids, _ = _seed_sets(client, inst, [["mvA", "mvB"]])
        resp, body = _op(client, inst, op_type="attribute_set_starter",
                         record_id=ids["mvA"], person_id=user.person_id)
    assert resp.status_code == 200
    assert body["success"] is False and body["reason"] == "people_tracking_off"
    db_cursor.execute(
        "SELECT COUNT(*) FROM session_instance_tune WHERE session_instance_id = %s AND started_by_person_id IS NOT NULL",
        (inst,),
    )
    assert db_cursor.fetchone()[0] == 0


def test_people_ops_allowed_when_flags_on(client, authenticated_user, live_instance, db_cursor):
    """The default (all flags on) still lets a check-in through — the gate is specific."""
    sid, inst = live_instance["session_id"], live_instance["instance_id"]
    _set_flags(db_cursor, sid, attendance=True, starters=True)
    with authenticated_user as user:
        resp, body = _op(client, inst, op_type="attendance_add", person_id=user.person_id)
    assert resp.status_code == 200 and body["success"] is True
