"""The setting chooser's writes (the web drawer and the iOS tune sheet).

The chooser pages every setting thesession.org has for a tune, so the one picked is
often one we've never imported. Whichever layer it lands on — mine (the set_setting
op), the session's, or one night's — the server imports it first: nothing may point at
a setting we don't hold. A setting thesession.org doesn't have for the tune is refused,
and nothing is written.
"""
import json
import uuid

import pytest

REMOTE_SETTING = 990000001  # far above any seeded setting id


@pytest.fixture
def remote_setting(monkeypatch, db_cursor, db_conn):
    """thesession.org, faked: the tune has one setting we don't hold."""
    import live_logging_routes

    calls = {"n": 0}

    def fetch(tune_id):
        calls["n"] += 1
        return {
            "name": "Faked",
            "type": "reel",
            "settings": [
                {
                    "id": REMOTE_SETTING,
                    "key": "Gmajor",
                    "abc": "|:GABc dedB|dedB dedB:|",
                }
            ],
        }

    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", fetch)
    yield calls
    db_cursor.execute(
        "DELETE FROM tune_setting_history WHERE setting_id = %s", (REMOTE_SETTING,)
    )
    db_cursor.execute(
        "UPDATE person_tune SET setting_id = NULL WHERE setting_id = %s",
        (REMOTE_SETTING,),
    )
    db_cursor.execute(
        "UPDATE session_tune SET setting_id = NULL WHERE setting_id = %s",
        (REMOTE_SETTING,),
    )
    db_cursor.execute(
        "UPDATE session_instance_tune SET setting_override = NULL WHERE setting_override = %s",
        (REMOTE_SETTING,),
    )
    db_cursor.execute(
        "DELETE FROM tune_setting WHERE setting_id = %s", (REMOTE_SETTING,)
    )
    db_conn.commit()


@pytest.fixture
def played(db_cursor, db_conn):
    """A tune logged at a night of a session, with a setting we hold."""
    db_cursor.execute(
        """SELECT s.session_id, s.path, si.session_instance_id, sit.tune_id
           FROM session_instance_tune sit
           JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
           JOIN session s ON s.session_id = si.session_id
           WHERE sit.tune_id IS NOT NULL AND sit.deleted = FALSE
             AND EXISTS (SELECT 1 FROM tune_setting ts WHERE ts.tune_id = sit.tune_id)
           ORDER BY sit.session_instance_tune_id LIMIT 1"""
    )
    session_id, path, instance_id, tune_id = db_cursor.fetchone()
    db_cursor.execute(
        "SELECT setting_id FROM tune_setting WHERE tune_id = %s ORDER BY setting_id DESC LIMIT 1",
        (tune_id,),
    )
    held = db_cursor.fetchone()[0]
    # The tests run against the shared dev database: put back what they touch. The
    # signed-in test user is the seeded sarah_fiddle (person 2).
    person_id = 2
    db_cursor.execute(
        "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
        (session_id, person_id),
    )
    membership = db_cursor.fetchone()
    db_cursor.execute(
        "SELECT setting_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
        (person_id, tune_id),
    )
    mine = db_cursor.fetchone()
    db_cursor.execute(
        "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
        (session_id, tune_id),
    )
    theirs = db_cursor.fetchone()
    db_cursor.execute(
        """INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)
           ON CONFLICT (session_id, tune_id) DO NOTHING""",
        (session_id, tune_id),
    )
    db_conn.commit()
    yield {
        "session_id": session_id,
        "path": path,
        "instance_id": instance_id,
        "tune_id": tune_id,
        "held": held,
    }
    db_conn.rollback()
    if membership is None:
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
    else:
        db_cursor.execute(
            "UPDATE session_person SET is_admin = %s WHERE session_id = %s AND person_id = %s",
            (membership[0], session_id, person_id),
        )
    if mine is None:
        db_cursor.execute(
            "DELETE FROM person_tune WHERE person_id = %s AND tune_id = %s",
            (person_id, tune_id),
        )
    else:
        db_cursor.execute(
            "UPDATE person_tune SET setting_id = %s WHERE person_id = %s AND tune_id = %s",
            (mine[0], person_id, tune_id),
        )
    if theirs is None:
        db_cursor.execute(
            "DELETE FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id),
        )
    else:
        db_cursor.execute(
            "UPDATE session_tune SET setting_id = %s WHERE session_id = %s AND tune_id = %s",
            (theirs[0], session_id, tune_id),
        )
    db_conn.commit()


def _member(db_cursor, db_conn, session_id, person_id, is_admin):
    db_cursor.execute(
        """INSERT INTO session_person (session_id, person_id, is_admin) VALUES (%s, %s, %s)
           ON CONFLICT (session_id, person_id) DO UPDATE SET is_admin = EXCLUDED.is_admin""",
        (session_id, person_id, is_admin),
    )
    db_conn.commit()


def _on_my_list(db_cursor, db_conn, person_id, tune_id):
    db_cursor.execute(
        """INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, 'learning')
           ON CONFLICT (person_id, tune_id) DO NOTHING""",
        (person_id, tune_id),
    )
    db_conn.commit()


def _op(client, **body):
    resp = client.post(
        "/api/my-tunes/ops",
        data=json.dumps({"op_id": str(uuid.uuid4()), **body}),
        content_type="application/json",
    )
    return resp, resp.get_json()


def _held(db_cursor, setting_id):
    db_cursor.execute(
        "SELECT tune_id FROM tune_setting WHERE setting_id = %s", (setting_id,)
    )
    row = db_cursor.fetchone()
    return row[0] if row else None


class TestMySetting:
    def test_a_held_setting_saves_without_asking_thesession(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _on_my_list(db_cursor, db_conn, user.person_id, played["tune_id"])
            resp, body = _op(
                client,
                type="set_setting",
                tune_id=played["tune_id"],
                setting_id=played["held"],
            )
            assert resp.status_code == 200 and body["success"] is True
        assert remote_setting["n"] == 0
        db_cursor.execute(
            "SELECT setting_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
            (user.person_id, played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] == played["held"]

    def test_one_only_thesession_has_is_imported_first(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _on_my_list(db_cursor, db_conn, user.person_id, played["tune_id"])
            resp, body = _op(
                client,
                type="set_setting",
                tune_id=played["tune_id"],
                setting_id=REMOTE_SETTING,
            )
            assert resp.status_code == 200, body
        assert _held(db_cursor, REMOTE_SETTING) == played["tune_id"]
        db_cursor.execute(
            "SELECT setting_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
            (user.person_id, played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] == REMOTE_SETTING

    def test_null_clears_and_nonsense_is_refused(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _on_my_list(db_cursor, db_conn, user.person_id, played["tune_id"])
            _op(
                client,
                type="set_setting",
                tune_id=played["tune_id"],
                setting_id=played["held"],
            )
            resp, _ = _op(
                client, type="set_setting", tune_id=played["tune_id"], setting_id=None
            )
            assert resp.status_code == 200
            for bad in ("12", 0, -3, True):
                resp, _ = _op(
                    client,
                    type="set_setting",
                    tune_id=played["tune_id"],
                    setting_id=bad,
                )
                assert resp.status_code == 400, bad
        db_cursor.execute(
            "SELECT setting_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
            (user.person_id, played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] is None

    def test_a_setting_thesession_does_not_have_is_refused(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _on_my_list(db_cursor, db_conn, user.person_id, played["tune_id"])
            resp, _ = _op(
                client,
                type="set_setting",
                tune_id=played["tune_id"],
                setting_id=REMOTE_SETTING + 1,
            )
            assert resp.status_code == 404
        assert _held(db_cursor, REMOTE_SETTING + 1) is None


class TestTheSessionsSetting:
    def test_an_admin_picks_one_only_thesession_has(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _member(
                db_cursor, db_conn, played["session_id"], user.person_id, is_admin=True
            )
            resp = client.put(
                f"/api/sessions/{played['path']}/tunes/{played['tune_id']}",
                data=json.dumps({"setting_id": REMOTE_SETTING}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
        assert _held(db_cursor, REMOTE_SETTING) == played["tune_id"]
        db_cursor.execute(
            "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (played["session_id"], played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] == REMOTE_SETTING

    def test_a_setting_thesession_does_not_have_writes_nothing(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        db_cursor.execute(
            "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (played["session_id"], played["tune_id"]),
        )
        before = db_cursor.fetchone()[0]
        with authenticated_user as user:
            _member(
                db_cursor, db_conn, played["session_id"], user.person_id, is_admin=True
            )
            resp = client.put(
                f"/api/sessions/{played['path']}/tunes/{played['tune_id']}",
                data=json.dumps({"setting_id": REMOTE_SETTING + 1}),
                content_type="application/json",
            )
            assert resp.status_code == 404
        db_cursor.execute(
            "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (played["session_id"], played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] == before


class TestOneNightsSetting:
    def test_a_member_marks_a_different_setting_for_the_night(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _member(
                db_cursor, db_conn, played["session_id"], user.person_id, is_admin=False
            )
            resp = client.put(
                f"/api/sessions/{played['path']}/{played['instance_id']}/tunes/{played['tune_id']}",
                data=json.dumps({"setting_override": REMOTE_SETTING}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
        assert _held(db_cursor, REMOTE_SETTING) == played["tune_id"]
        db_cursor.execute(
            """SELECT DISTINCT setting_override FROM session_instance_tune
               WHERE session_instance_id = %s AND tune_id = %s""",
            (played["instance_id"], played["tune_id"]),
        )
        assert [r[0] for r in db_cursor.fetchall()] == [REMOTE_SETTING]

    def test_a_setting_thesession_does_not_have_is_refused(
        self, client, authenticated_user, played, remote_setting, db_cursor, db_conn
    ):
        with authenticated_user as user:
            _member(
                db_cursor, db_conn, played["session_id"], user.person_id, is_admin=False
            )
            resp = client.put(
                f"/api/sessions/{played['path']}/{played['instance_id']}/tunes/{played['tune_id']}",
                data=json.dumps({"setting_override": REMOTE_SETTING + 1}),
                content_type="application/json",
            )
            assert resp.status_code == 404
        assert _held(db_cursor, REMOTE_SETTING + 1) is None
