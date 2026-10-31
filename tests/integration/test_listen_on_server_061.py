"""
The right to listen on the server (spec 061 stage 1): a system admin gives it to a
named person, /api/me reports it, the listening service admits on it, and the
night's known tunes (which the service asks for with the listener's token) are
open to whoever has it.

Fixtures are committed in the 961xx block, since the HTTP calls open their own
connections; teardown deletes them and takes the right back from sarah_fiddle.
"""

import io
import json
from unittest.mock import patch

import pytest

SESSION = 96100
NIGHT = 96101
SARAH = 2  # the seeded non-admin authenticated_user stands for


def _reset(cur):
    cur.execute(
        "UPDATE user_account SET can_listen_on_server = FALSE WHERE user_id = %s",
        (SARAH,),
    )
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SESSION,))


@pytest.fixture
def night(db_setup):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    _reset(cur)
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Listen061', 'listen061-test')",
        (SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-10-01')",
        (NIGHT, SESSION),
    )
    conn.commit()
    yield cur
    conn.rollback()
    _reset(cur)
    conn.commit()
    conn.close()


# The test client keeps the first user it signs in for the whole test, so each
# test signs in one person; the right is set directly where a test needs it.
def _grant(cur, allowed=True):
    cur.execute(
        "UPDATE user_account SET can_listen_on_server = %s WHERE user_id = %s",
        (allowed, SARAH),
    )
    cur.connection.commit()


def _flag(cur):
    cur.execute(
        "SELECT can_listen_on_server FROM user_account WHERE user_id = %s", (SARAH,)
    )
    return cur.fetchone()[0]


def test_a_system_admin_gives_the_right_and_takes_it_back(client, admin_user, night):
    url = f"/api/admin/user/{SARAH}/listen-on-server"
    with admin_user:
        resp = client.put(url, json={"allowed": True})
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["can_listen_on_server"] is True
        assert _flag(night) is True
        assert client.put(url, json={"allowed": False}).status_code == 200
        assert _flag(night) is False
    # each change is in the account's history
    night.execute(
        "SELECT count(*) FROM user_account_history WHERE user_id = %s AND changed_by_user_id = 1",
        (SARAH,),
    )
    assert night.fetchone()[0] >= 2


def test_me_reports_the_right(client, authenticated_user, night):
    _grant(night)
    with authenticated_user:
        assert client.get("/api/me").get_json()["user"]["can_listen_on_server"] is True


def test_me_reports_no_right(client, authenticated_user, night):
    with authenticated_user:
        assert client.get("/api/me").get_json()["user"]["can_listen_on_server"] is False


def test_a_system_admin_has_the_right_without_the_flag(client, admin_user, night):
    with admin_user:
        assert client.get("/api/me").get_json()["user"]["can_listen_on_server"] is True


def test_only_a_system_admin_can_give_it(client, authenticated_user, night):
    with authenticated_user:
        resp = client.put(
            f"/api/admin/user/{SARAH}/listen-on-server", json={"allowed": True}
        )
        assert resp.status_code == 403
    assert _flag(night) is False


def test_the_request_must_say_true_or_false(client, admin_user, night):
    with admin_user:
        bad = client.put(
            f"/api/admin/user/{SARAH}/listen-on-server", json={"allowed": "yes"}
        )
        assert bad.status_code == 400
        missing = client.put(
            "/api/admin/user/99999999/listen-on-server", json={"allowed": True}
        )
        assert missing.status_code == 404


def test_the_admin_person_page_carries_the_flag(night):
    from database import get_db_connection
    from serializers import build_person_details_payload

    _grant(night)
    conn = get_db_connection()
    try:
        payload = build_person_details_payload(
            conn, SARAH, is_user_profile=False, is_system_admin=True
        )
    finally:
        conn.close()
    assert payload["user"]["can_listen_on_server"] is True


def test_without_the_right_the_nights_known_tunes_are_refused(
    client, authenticated_user, night
):
    with authenticated_user:
        url = f"/api/session-instances/{NIGHT}/known-tunes"
        assert client.get(url).status_code == 403


def test_a_listener_may_read_the_nights_known_tunes(client, authenticated_user, night):
    _grant(night)
    with authenticated_user:
        resp = client.get(f"/api/session-instances/{NIGHT}/known-tunes")
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["tune_ids"] == []
        # a night that isn't there is still not there
        assert (
            client.get("/api/session-instances/99999999/known-tunes").status_code == 404
        )


def _me(user):
    return io.BytesIO(json.dumps({"success": True, "user": user}).encode())


@pytest.mark.parametrize(
    "user, allowed",
    [
        ({"is_system_admin": False, "can_listen_on_server": True}, True),
        ({"is_system_admin": False, "can_listen_on_server": False}, False),
        ({"is_system_admin": True, "can_listen_on_server": True}, True),
        # a web app from before the right: the admin bit alone decides
        ({"is_system_admin": True}, True),
        ({"is_system_admin": False}, False),
    ],
)
def test_the_listening_service_admits_on_the_right(user, allowed):
    from listen import service

    service._app_tokens.clear()
    with patch("urllib.request.urlopen", return_value=_me(user)):
        assert service._app_token_allowed("tok-061") is allowed
    service._app_tokens.clear()
