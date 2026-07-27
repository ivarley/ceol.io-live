"""The four session columns that had no editor: thesession_id, session_type, and
the two active_buffer_minutes_* values.

They were readable (the admin grid links thesession_id; session_type reorders the
public page's tabs; the buffers drive the "happening now" window) but reachable
only by direct SQL — `build_session_admin_payload` didn't select them and
`update_session_ajax`'s whitelist had no entry, so even a hand-crafted PUT was
silently dropped. These pin both write paths plus the shared validator.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from auth import User
from database import get_db_connection
from session_fields import (
    normalize_active_buffer,
    normalize_session_type,
    parse_thesession_session_id,
)

pytestmark = pytest.mark.integration

PROBE_TS_ID = 987654  # unused upstream id for the create tests


@contextmanager
def logged_in(client, person_id=1, is_system_admin=True):
    user = User(
        user_id=1,
        person_id=person_id,
        username="admin",
        email="t@example.com",
        first_name="T",
        last_name="U",
        is_active=True,
        is_system_admin=is_system_admin,
        timezone="UTC",
        email_verified=True,
    )
    with patch("auth.User.get_by_id", return_value=user):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.user_id)
            sess["_fresh"] = True
            sess["is_system_admin"] = is_system_admin
            sess["admin_session_ids"] = []
        yield user
        with client.session_transaction() as sess:
            sess.clear()


@pytest.fixture
def restore_session_one():
    """The endpoint commits on its own connection, so snapshot the four columns and
    put them back (plus the UPDATE history rows the saves generate)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT thesession_id, session_type, active_buffer_minutes_before,
               active_buffer_minutes_after
        FROM session WHERE session_id = 1
        """
    )
    original = cur.fetchone()
    yield
    cur.execute(
        """
        UPDATE session
        SET thesession_id = %s, session_type = %s,
            active_buffer_minutes_before = %s, active_buffer_minutes_after = %s
        WHERE session_id = 1
        """,
        original,
    )
    cur.execute(
        "DELETE FROM session_history WHERE session_id = 1 AND operation = 'UPDATE'"
    )
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def cleanup_created_sessions():
    yield
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM session_history WHERE session_id IN "
        "(SELECT session_id FROM session WHERE name LIKE 'Fields Probe %%')"
    )
    cur.execute("DELETE FROM session WHERE name LIKE 'Fields Probe %%'")
    conn.commit()
    cur.close()
    conn.close()


def _fields(cur, session_id=1):
    cur.execute(
        """
        SELECT thesession_id, session_type, active_buffer_minutes_before,
               active_buffer_minutes_after
        FROM session WHERE session_id = %s
        """,
        (session_id,),
    )
    return cur.fetchone()


class TestValidator:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (1234, 1234),
            ("1234", 1234),
            ("  1234  ", 1234),
            ("https://thesession.org/sessions/1234", 1234),
            ("thesession.org/sessions/1234", 1234),
            ("https://thesession.org/sessions/1234#comments", 1234),
        ],
    )
    def test_accepts_ids_and_session_urls(self, raw, expected):
        assert parse_thesession_session_id(raw) == (expected, None)

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_blank_means_no_link(self, raw):
        assert parse_thesession_session_id(raw) == (None, None)

    @pytest.mark.parametrize(
        "raw",
        [
            "https://thesession.org/tunes/1234",  # a TUNE url must not pass
            "not a number",
            "12.5",
            "-3",
            0,
            True,
        ],
    )
    def test_rejects_junk_and_tune_urls(self, raw):
        value, error = parse_thesession_session_id(raw)
        assert value is None
        assert error

    @pytest.mark.parametrize("raw,expected", [("regular", "regular"), ("Festival", "festival"), (None, "regular"), ("", "regular")])
    def test_session_type_normalizes(self, raw, expected):
        assert normalize_session_type(raw) == (expected, None)

    def test_session_type_rejects_unknown(self):
        value, error = normalize_session_type("carnival")
        assert value is None
        assert "regular" in error and "festival" in error

    @pytest.mark.parametrize("raw,expected", [(0, 0), ("90", 90), (None, 60), ("", 60), (1440, 1440)])
    def test_buffer_normalizes(self, raw, expected):
        assert normalize_active_buffer(raw) == (expected, None)

    @pytest.mark.parametrize("raw", [-1, "abc", 1441, 2.5])
    def test_buffer_rejects_out_of_range(self, raw):
        value, error = normalize_active_buffer(raw, "Minutes before")
        assert value is None
        assert error.startswith("Minutes before")


class TestAdminPayload:
    def test_payload_carries_all_four(self, db_conn):
        from serializers import build_session_admin_payload

        payload = build_session_admin_payload(db_conn, "austin/mueller")
        session = payload["session"] if "session" in payload else payload
        for key in (
            "thesession_id",
            "session_type",
            "active_buffer_minutes_before",
            "active_buffer_minutes_after",
        ):
            assert key in session, f"{key} missing from the admin payload"
        assert session["session_type"] in ("regular", "festival")


class TestUpdate:
    def test_saves_all_four(self, client, db_conn, restore_session_one):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={
                    "thesession_id": "4321",
                    "session_type": "festival",
                    "active_buffer_minutes_before": 15,
                    "active_buffer_minutes_after": 90,
                },
            )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        assert _fields(cur) == (4321, "festival", 15, 90)
        cur.close()

    def test_accepts_a_pasted_session_url(self, client, db_conn, restore_session_one):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": "https://thesession.org/sessions/6247"},
            )
        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        assert _fields(cur)[0] == 6247
        cur.close()

    def test_blank_clears_the_link(self, client, db_conn, restore_session_one):
        with logged_in(client):
            client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": 5555},
            )
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": ""},
            )
        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        assert _fields(cur)[0] is None
        cur.close()

    def test_rejects_a_tune_url(self, client, db_conn, restore_session_one):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": "https://thesession.org/tunes/182"},
            )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

        cur = db_conn.cursor()
        assert _fields(cur)[0] != 182
        cur.close()

    def test_rejects_an_id_another_session_already_uses(
        self, client, db_conn, restore_session_one
    ):
        """One upstream session maps to one of ours — the create path checks the same."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE session SET thesession_id = %s WHERE session_id = 2", (7777,)
        )
        conn.commit()
        try:
            with logged_in(client):
                resp = client.put(
                    "/api/sessions/austin/mueller/admin-update",
                    json={"thesession_id": 7777},
                )
            assert resp.status_code == 400
            body = resp.get_json()
            assert body["success"] is False
            assert "already linked" in body["error"]

            check = db_conn.cursor()
            assert _fields(check)[0] != 7777
            check.close()
        finally:
            cur.execute(
                "UPDATE session SET thesession_id = NULL WHERE session_id = 2"
            )
            cur.execute(
                "DELETE FROM session_history WHERE session_id = 2 AND operation = 'UPDATE'"
            )
            conn.commit()
            cur.close()
            conn.close()

    def test_keeping_its_own_id_is_not_a_collision(
        self, client, db_conn, restore_session_one
    ):
        with logged_in(client):
            client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": 8888},
            )
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"thesession_id": 8888, "session_type": "regular"},
            )
        assert resp.get_json()["success"] is True

    @pytest.mark.parametrize(
        "payload",
        [
            {"session_type": "carnival"},
            {"active_buffer_minutes_before": -5},
            {"active_buffer_minutes_after": "soon"},
            {"active_buffer_minutes_before": 100000},
        ],
    )
    def test_rejects_bad_values(self, client, db_conn, payload):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update", json=payload
            )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_partial_payload_leaves_the_four_alone(
        self, client, db_conn, restore_session_one
    ):
        """The cache/recurrence saves send neither — absent must mean untouched."""
        cur = db_conn.cursor()
        before = _fields(cur)
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"live_cache_session_limit": 150},
            )
        assert resp.get_json()["success"] is True
        db_conn.rollback()  # re-read outside the stale snapshot
        assert _fields(db_conn.cursor()) == before
        cur.close()


class TestCreate:
    def _payload(self, name, **extra):
        return {
            "name": name,
            "path": name.lower().replace(" ", "-"),
            "city": "Testville",
            "state": "Texas",
            "country": "USA",
            "add_current_user": False,
            **extra,
        }

    def test_stores_all_four(self, client, db_conn, cleanup_created_sessions):
        with logged_in(client):
            resp = client.post(
                "/api/add-session",
                json=self._payload(
                    "Fields Probe Create",
                    thesession_id=f"https://thesession.org/sessions/{PROBE_TS_ID}",
                    session_type="festival",
                    active_buffer_minutes_before=30,
                    active_buffer_minutes_after=45,
                ),
            )
        assert resp.get_json()["success"] is True, resp.get_json()

        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT thesession_id, session_type, active_buffer_minutes_before,
                   active_buffer_minutes_after
            FROM session WHERE name = %s
            """,
            ("Fields Probe Create",),
        )
        assert cur.fetchone() == (PROBE_TS_ID, "festival", 30, 45)
        cur.close()

    def test_defaults_when_omitted(self, client, db_conn, cleanup_created_sessions):
        with logged_in(client):
            resp = client.post(
                "/api/add-session", json=self._payload("Fields Probe Defaults")
            )
        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT thesession_id, session_type, active_buffer_minutes_before,
                   active_buffer_minutes_after
            FROM session WHERE name = %s
            """,
            ("Fields Probe Defaults",),
        )
        assert cur.fetchone() == (None, "regular", 60, 60)
        cur.close()

    def test_rejects_bad_session_type(self, client, db_conn, cleanup_created_sessions):
        with logged_in(client):
            resp = client.post(
                "/api/add-session",
                json=self._payload("Fields Probe Bad Type", session_type="carnival"),
            )
        assert resp.get_json()["success"] is False

        cur = db_conn.cursor()
        cur.execute(
            "SELECT session_id FROM session WHERE name = %s", ("Fields Probe Bad Type",)
        )
        assert cur.fetchall() == []
        cur.close()
