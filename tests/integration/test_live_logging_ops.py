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

# Canned thesession.org tune JSON for the mocked importer (spec 026).
FAKE_TS_TUNE = {
    "name": "The Imported Reel",
    "type": "reel",
    "tunebooks": 42,
    "settings": [{"id": IMPORT_SETTING, "key": "Dmaj", "abc": "D2FA d2FA|BAFA B2A2"}],
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
        cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, tid))
    # NEWT: a canonical tune deliberately NOT enrolled, so enrollment on add is observable.
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Jig')", (NEWT, "The Unenrolled Jig"))
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


def test_merged_tune_not_enrolled(client, authenticated_user, live_instance, db_cursor):
    """A merged/redirect tune is never enrolled, matching the old logger."""
    sid, inst, merged = live_instance["session_id"], live_instance["instance_id"], live_instance["merged"]
    with authenticated_user:
        resp, body = _op(client, inst, op_type="add_tune", tune_id=merged)
    assert body["success"] is True  # the play is still logged
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
