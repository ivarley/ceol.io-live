"""A session's path is its URL, and every admin route is keyed on it — so a
session written with an unusable path has no reachable screen that could repair
it. Only a direct database UPDATE gets it back.

That happened in production: a session was created with a path that passed the
old `.strip()` truthiness check but resolved to nothing in a browser, so the
admin list linked to `/admin/sessions/` and the session was stranded.

These tests pin the structural rule at both write paths — POST /api/add-session
and PUT /api/sessions/<path>/admin-update — plus the pure validator.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from auth import User
from database import get_db_connection
from session_path import normalize_session_path


@pytest.fixture
def cleanup_created_sessions():
    """These endpoints open their own connection and COMMIT, so the db_conn
    rollback doesn't undo them and the rows would perturb later tests."""
    yield
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM session_history WHERE session_id IN "
        "(SELECT session_id FROM session WHERE name LIKE 'Probe %%')"
    )
    cur.execute("DELETE FROM session WHERE name LIKE 'Probe %%'")
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def restore_session_one():
    """Same reason: the successful-update test commits against seeded session 1."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT live_cache_session_limit FROM session WHERE session_id = 1")
    original = cur.fetchone()[0]
    yield
    cur.execute(
        "UPDATE session SET live_cache_session_limit = %s WHERE session_id = 1",
        (original,),
    )
    cur.execute(
        "DELETE FROM session_history WHERE session_id = 1 AND operation = 'UPDATE'"
    )
    conn.commit()
    cur.close()
    conn.close()


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


# Values that are non-empty (so the old check passed) but unusable as a URL.
STRANDING_PATHS = [
    pytest.param("/", id="bare-slash"),
    pytest.param(".", id="dot"),
    pytest.param("..", id="dot-dot"),
    pytest.param("\u200b", id="zero-width-space"),
    pytest.param("\ufeff", id="byte-order-mark"),
    pytest.param("-", id="hyphen-only"),
    pytest.param("/austin", id="leading-slash"),
    pytest.param("austin/", id="trailing-slash"),
    pytest.param("austin//mueller", id="empty-segment"),
    pytest.param("austin/./mueller", id="dot-segment"),
    pytest.param("austin mueller", id="space"),
    pytest.param("austin\u200bmueller", id="embedded-zero-width"),
    pytest.param("austin?x=1", id="query-string"),
    pytest.param("austin#frag", id="fragment"),
    pytest.param("a/b/c/d/e", id="too-many-segments"),
]

VALID_PATHS = [
    "austin/mueller",
    "mueller",
    "austin/mcgraths-irish-pub",
    "st.james",
    "with_underscore",
    "a/b/c/d",
    "MixedCase/Path",
]


@pytest.mark.integration
class TestValidator:
    @pytest.mark.parametrize("value", [p.values[0] for p in STRANDING_PATHS])
    def test_rejects_unusable(self, value):
        path, error = normalize_session_path(value)
        assert path is None
        assert error

    @pytest.mark.parametrize("value", VALID_PATHS)
    def test_accepts_usable(self, value):
        path, error = normalize_session_path(value)
        assert error is None
        assert path == value

    @pytest.mark.parametrize("value", ["", "   ", "\t", "\n", None, 0, False, [], {}])
    def test_rejects_empty_and_non_strings(self, value):
        path, error = normalize_session_path(value)
        assert path is None
        assert error == "Path is required"

    def test_trims_surrounding_whitespace(self):
        assert normalize_session_path("  austin/mueller  ") == ("austin/mueller", None)

    def test_rejects_overlong(self):
        path, error = normalize_session_path("a" * 256)
        assert path is None
        assert "255" in error


def _create_payload(name, path):
    return {
        "name": name,
        "path": path,
        "city": "Testville",
        "state": "Texas",
        "country": "USA",
        "add_current_user": False,
    }


@pytest.mark.integration
class TestCreateRejectsUnusablePaths:
    @pytest.mark.parametrize("bad_path", STRANDING_PATHS)
    def test_rejected(self, client, db_conn, bad_path):
        name = "Path Validation Probe"
        with logged_in(client):
            resp = client.post("/api/add-session", json=_create_payload(name, bad_path))

        assert resp.status_code == 200
        assert resp.get_json()["success"] is False

        cur = db_conn.cursor()
        cur.execute("SELECT session_id FROM session WHERE name = %s", (name,))
        assert cur.fetchall() == []
        cur.close()

    @pytest.mark.parametrize(
        "bad_value", [None, 0, False, [], {"nested": True}]
    )
    def test_non_string_path_is_rejected_not_a_500(self, client, bad_value):
        """These used to raise AttributeError on .strip() before the try block."""
        with logged_in(client):
            resp = client.post(
                "/api/add-session", json=_create_payload("Probe NonString", bad_value)
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is False
        assert body["message"] == "Path is required"

    def test_path_is_stored_trimmed(self, client, db_conn, cleanup_created_sessions):
        """The old code validated data["path"].strip() but inserted it unstripped."""
        name = "Probe Trimmed"
        with logged_in(client):
            resp = client.post(
                "/api/add-session", json=_create_payload(name, "  probe/trimmed  ")
            )
        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        cur.execute("SELECT path FROM session WHERE name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        assert row is not None
        assert row[0] == "probe/trimmed"


@pytest.mark.integration
class TestUpdateRejectsUnusablePaths:
    """The update endpoint had no server-side path check at all — only the admin
    form's own guard stood between a blank path and an unreachable session."""

    @pytest.mark.parametrize("bad_path", STRANDING_PATHS + [pytest.param("", id="blank")])
    def test_rejected(self, client, db_conn, bad_path):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"name": "Mueller", "path": bad_path},
            )

        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

        cur = db_conn.cursor()
        cur.execute("SELECT path FROM session WHERE session_id = 1")
        assert cur.fetchone()[0] == "austin/mueller"
        cur.close()

    def test_partial_payload_without_path_still_works(
        self, client, db_conn, restore_session_one
    ):
        """The cache and recurrence saves send no path — they must not be blocked."""
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"live_cache_session_limit": 150},
            )

        assert resp.get_json()["success"] is True

        cur = db_conn.cursor()
        cur.execute("SELECT path FROM session WHERE session_id = 1")
        assert cur.fetchone()[0] == "austin/mueller"
        cur.close()

    def test_collision_reports_the_conflict(self, client):
        with logged_in(client):
            resp = client.put(
                "/api/sessions/austin/mueller/admin-update",
                json={"path": "austin/downtown"},
            )

        assert resp.status_code == 400
        assert "already used by" in resp.get_json()["error"]
