"""A row's setting must be a setting of that row's tune.

Setting ids are numbered across all of thesession.org, not per tune: "setting 1" is
Cooley's, whatever tune it is typed against. Rows pointing at another tune's setting
drew that tune's notation under this tune's name. Migration 064's trigger blanks
such a setting on every write; the add endpoint refuses one; the notation lookup
never draws one.
"""
import json

import pytest

from serializers import _load_setting_notation
from test_setting_chooser import played, remote_setting, REMOTE_SETTING  # noqa: F401


@pytest.fixture
def other_setting(db_cursor, played):  # noqa: F811
    """A setting we hold that belongs to some other tune."""
    db_cursor.execute(
        "SELECT setting_id FROM tune_setting WHERE tune_id <> %s ORDER BY setting_id LIMIT 1",
        (played["tune_id"],),
    )
    return db_cursor.fetchone()[0]


class TestTheTrigger:
    def test_a_session_tune_cannot_point_at_another_tunes_setting(
        self, db_cursor, played, other_setting  # noqa: F811
    ):
        db_cursor.execute(
            "UPDATE session_tune SET setting_id = %s WHERE session_id = %s AND tune_id = %s",
            (other_setting, played["session_id"], played["tune_id"]),
        )
        db_cursor.execute(
            "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (played["session_id"], played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] is None

    def test_its_own_setting_is_kept(self, db_cursor, played):  # noqa: F811
        db_cursor.execute(
            "UPDATE session_tune SET setting_id = %s WHERE session_id = %s AND tune_id = %s",
            (played["held"], played["session_id"], played["tune_id"]),
        )
        db_cursor.execute(
            "SELECT setting_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (played["session_id"], played["tune_id"]),
        )
        assert db_cursor.fetchone()[0] == played["held"]

    def test_a_nights_row_cannot_either(
        self, db_cursor, played, other_setting  # noqa: F811
    ):  # noqa: F811
        db_cursor.execute(
            """UPDATE session_instance_tune SET setting_override = %s
               WHERE session_instance_id = %s AND tune_id = %s""",
            (other_setting, played["instance_id"], played["tune_id"]),
        )
        db_cursor.execute(
            """SELECT DISTINCT setting_override FROM session_instance_tune
               WHERE session_instance_id = %s AND tune_id = %s""",
            (played["instance_id"], played["tune_id"]),
        )
        assert [r[0] for r in db_cursor.fetchall()] == [None]

    def test_relinking_a_nights_row_drops_the_old_tunes_setting(
        self, db_cursor, played, other_setting  # noqa: F811
    ):
        db_cursor.execute(
            "SELECT tune_id FROM tune_setting WHERE setting_id = %s", (other_setting,)
        )
        other_tune = db_cursor.fetchone()[0]
        db_cursor.execute(
            """UPDATE session_instance_tune SET setting_override = %s
               WHERE session_instance_id = %s AND tune_id = %s
               RETURNING session_instance_tune_id""",
            (played["held"], played["instance_id"], played["tune_id"]),
        )
        row_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "UPDATE session_instance_tune SET tune_id = %s WHERE session_instance_tune_id = %s",
            (other_tune, row_id),
        )
        db_cursor.execute(
            "SELECT setting_override FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (row_id,),
        )
        assert db_cursor.fetchone()[0] is None

    def test_a_person_tune_cannot_either(
        self, db_cursor, played, other_setting  # noqa: F811
    ):  # noqa: F811
        db_cursor.execute(
            """INSERT INTO person_tune (person_id, tune_id, learn_status, setting_id)
               VALUES (2, %s, 'learning', %s)
               ON CONFLICT (person_id, tune_id) DO UPDATE SET setting_id = EXCLUDED.setting_id""",
            (played["tune_id"], other_setting),
        )
        db_cursor.execute(
            "SELECT setting_id FROM person_tune WHERE person_id = 2 AND tune_id = %s",
            (played["tune_id"],),
        )
        assert db_cursor.fetchone()[0] is None


def test_the_notation_is_never_another_tunes(
    db_conn, played, other_setting  # noqa: F811
):  # noqa: F811
    notation = _load_setting_notation(db_conn, played["tune_id"], other_setting)
    cur = db_conn.cursor()
    cur.execute(
        "SELECT MIN(setting_id) FROM tune_setting WHERE tune_id = %s",
        (played["tune_id"],),
    )
    assert notation["setting_id"] == cur.fetchone()[0]


def test_adding_a_tune_with_another_tunes_setting_is_refused(
    client,
    authenticated_user,
    db_cursor,
    db_conn,
    played,  # noqa: F811
    other_setting,
    remote_setting,  # noqa: F811
):
    db_cursor.execute(
        """SELECT t.tune_id FROM tune t
           WHERE t.redirect_to_tune_id IS NULL
             AND NOT EXISTS (SELECT 1 FROM session_tune st
                             WHERE st.session_id = %s AND st.tune_id = t.tune_id)
             AND NOT EXISTS (SELECT 1 FROM tune_setting ts
                             WHERE ts.setting_id = %s AND ts.tune_id = t.tune_id)
           ORDER BY t.tune_id LIMIT 1""",
        (played["session_id"], other_setting),
    )
    tune_id = db_cursor.fetchone()[0]
    with authenticated_user:
        resp = client.post(
            f"/api/sessions/{played['path']}/tunes",
            data=json.dumps({"tune_id": tune_id, "setting_id": other_setting}),
            content_type="application/json",
        )
        assert resp.status_code == 404, resp.data
    db_cursor.execute(
        "SELECT 1 FROM session_tune WHERE session_id = %s AND tune_id = %s",
        (played["session_id"], tune_id),
    )
    assert db_cursor.fetchone() is None
