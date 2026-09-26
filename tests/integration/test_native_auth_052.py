"""The native auth handshake (spec 052 A1) and the app-shell endpoints.

What a native client cannot do without, and what the web must not lose:

- A login that returns a Bearer token to a caller announcing itself as native, and
  a cookie (no token) to the web — from the same endpoint.
- A one-time-token exchange for the two emailed links (magic-link login and email
  verification), so a Universal Link tap lands in the app and still logs in.
- Logout that actually revokes the token.
- GET /api/me and /api/app-config, the two calls an app makes before anything else.
- /api/home == the Jinja home's data; /api/resolve == session_handler's path rules.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest

from auth import User, generate_login_token, generate_verification_token
from database import get_db_connection
from timezone_utils import now_utc

ADMIN = {"email": "ian@ceol.io", "password": "password123"}
IOS = {"X-Ceol-Client": "ios/1.4.0 (build 12)"}


def _login_native(client, creds=ADMIN):
    r = client.post("/api/auth/login-password", json=creds, headers=IOS)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _bearer(token):
    return {"Authorization": f"Bearer {token}", **IOS}


def _session_row(token):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, user_agent FROM user_session WHERE session_id = %s",
            (token,),
        )
        return cur.fetchone()
    finally:
        conn.close()


@pytest.fixture
def passwordless_user():
    """A verified magic-link (no password) account, cleaned up after."""
    conn = get_db_connection()
    uid = None
    try:
        cur = conn.cursor()
        tag = uuid.uuid4().hex[:8]
        cur.execute(
            """
            INSERT INTO person (first_name, last_name, email, city, created_date, last_modified_date)
            VALUES ('Magic', 'Link', %s, 'Galway', %s, %s) RETURNING person_id
            """,
            (f"magic{tag}@example.com", now_utc(), now_utc()),
        )
        pid = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone,
                                      email_verified, is_active, created_date, last_modified_date)
            VALUES (%s, %s, %s, NULL, 'UTC', TRUE, TRUE, %s, %s) RETURNING user_id
            """,
            (pid, f"magic{tag}", f"magic{tag}@example.com", now_utc(), now_utc()),
        )
        uid = cur.fetchone()[0]
        conn.commit()
        yield {"user_id": uid, "person_id": pid, "email": f"magic{tag}@example.com"}
    finally:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM login_history WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM user_session WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM user_account WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM person WHERE person_id = %s", (pid,))
            conn.commit()
        except Exception:
            conn.rollback()
        conn.close()


def _set_token(user_id, column, token, minutes):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE user_account SET {column} = %s, {column}_expires = %s WHERE user_id = %s",
            (token, now_utc() + timedelta(minutes=minutes), user_id),
        )
        if column == "verification_token":
            cur.execute(
                "UPDATE user_account SET email_verified = FALSE WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


class TestPasswordLogin:
    def test_native_caller_gets_token_and_no_cookie(self, client):
        r = client.post("/api/auth/login-password", json=ADMIN, headers=IOS)
        body = r.get_json()
        assert r.status_code == 200
        assert body["token_type"] == "Bearer"
        assert body["method"] == "password"
        assert body["user"]["username"] == "ian"
        assert body["user"]["has_password"] is True
        assert "redirect" not in body
        assert "Set-Cookie" not in r.headers
        # The token IS a user_session row, tagged with the client.
        row = _session_row(body["token"])
        assert row and row[0] == body["user"]["user_id"]
        assert row[1].startswith("ios/1.4.0")

    def test_web_caller_gets_cookie_and_redirect_no_token(self, client):
        r = client.post("/api/auth/login-password", json=ADMIN)
        body = r.get_json()
        assert r.status_code == 200
        assert "token" not in body
        assert body["redirect"] == "/"
        assert body["user"]["username"] == "ian"
        assert "session=" in " ".join(r.headers.getlist("Set-Cookie"))

    def test_wrong_password_is_401_envelope(self, client):
        r = client.post(
            "/api/auth/login-password", json={**ADMIN, "password": "nope"}, headers=IOS
        )
        assert r.status_code == 401
        body = r.get_json()
        assert body["success"] is False and body["code"] == "unauthenticated"
        assert body["error"] == body["message"]


class TestBearerToken:
    def test_token_authenticates_api_me(self, client):
        token = _login_native(client)["token"]
        r = client.get("/api/me", headers=_bearer(token))
        assert r.status_code == 200
        user = r.get_json()["user"]
        assert user["username"] == "ian"
        assert user["has_password"] is True  # loaded by get_by_id, not only at login
        assert user["is_system_admin"] is True

    def test_logout_revokes_token(self, client):
        token = _login_native(client)["token"]
        assert client.get("/api/me", headers=_bearer(token)).status_code == 200
        r = client.post("/api/auth/logout", headers=_bearer(token))
        assert r.status_code == 200
        assert _session_row(token) is None
        assert client.get("/api/me", headers=_bearer(token)).status_code == 401

    def test_garbage_token_is_401(self, client):
        assert client.get("/api/me", headers=_bearer("not-a-token")).status_code == 401


class TestExchange:
    def test_magic_link_token_exchanges_for_session(self, client, passwordless_user):
        token = generate_login_token()
        _set_token(passwordless_user["user_id"], "login_token", token, 15)
        r = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["method"] == "magic_link"
        assert body["token_type"] == "Bearer"
        assert body["user"]["email"] == passwordless_user["email"]
        assert body["user"]["has_password"] is False
        assert body["next"] == "set_password"
        # single use
        r2 = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)
        assert r2.status_code == 401
        assert r2.get_json()["code"] == "invalid_token"

    def test_verification_token_verifies_and_logs_in(self, client, passwordless_user):
        token = generate_verification_token()
        _set_token(passwordless_user["user_id"], "verification_token", token, 60)
        r = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["method"] == "email_verification"
        assert body["user"]["email_verified"] is True
        me = client.get("/api/me", headers=_bearer(body["token"])).get_json()["user"]
        assert me["email_verified"] is True

    def test_expired_token_rejected(self, client, passwordless_user):
        token = generate_login_token()
        _set_token(passwordless_user["user_id"], "login_token", token, -1)
        r = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)
        assert r.status_code == 401

    def test_missing_token(self, client):
        r = client.post("/api/auth/exchange", json={}, headers=IOS)
        assert r.status_code == 400
        assert r.get_json()["code"] == "missing_token"


class TestSetPasswordAndProfile:
    def test_set_password_then_password_login(self, client, passwordless_user):
        token = generate_login_token()
        _set_token(passwordless_user["user_id"], "login_token", token, 15)
        bearer = client.post(
            "/api/auth/exchange", json={"token": token}, headers=IOS
        ).get_json()["token"]
        r = client.post(
            "/api/auth/set-password",
            json={"password": "short"},
            headers=_bearer(bearer),
        )
        assert r.status_code == 400 and r.get_json()["code"] == "password_too_short"
        r = client.post(
            "/api/auth/set-password",
            json={"password": "longenough1"},
            headers=_bearer(bearer),
        )
        assert r.status_code == 200
        r = client.post(
            "/api/auth/login-password",
            json={"email": passwordless_user["email"], "password": "longenough1"},
            headers=IOS,
        )
        assert r.status_code == 200 and r.get_json()["user"]["has_password"] is True

    def test_profile_round_trip(self, client, passwordless_user):
        token = generate_login_token()
        _set_token(passwordless_user["user_id"], "login_token", token, 15)
        bearer = client.post(
            "/api/auth/exchange", json={"token": token}, headers=IOS
        ).get_json()["token"]
        r = client.put(
            "/api/me/profile",
            json={
                "first_name": "Maura",
                "state": "Clare",
                "timezone": "Europe/Dublin",
                "instruments": ["fiddle", "Fiddle", "Concertina"],
            },
            headers=_bearer(bearer),
        )
        assert r.status_code == 200, r.get_json()
        p = r.get_json()["profile"]
        assert p["first_name"] == "Maura" and p["last_name"] == "Link"
        assert p["city"] == "Galway" and p["state"] == "Clare"
        assert p["timezone"] == "Europe/Dublin"
        assert p["instruments"] == ["Concertina", "Fiddle"]
        # blank clears; absent keeps
        r = client.put("/api/me/profile", json={"city": ""}, headers=_bearer(bearer))
        p = r.get_json()["profile"]
        assert p["city"] == "" and p["state"] == "Clare"


class TestResendVerification:
    @patch("api_app_routes.send_verification_email")
    def test_unknown_email_is_a_quiet_200(self, mock_send, client):
        r = client.post(
            "/api/auth/resend-verification", json={"email": "nobody@example.com"}
        )
        assert r.status_code == 200 and r.get_json()["success"] is True
        mock_send.assert_not_called()

    @patch("api_app_routes.send_verification_email")
    def test_unverified_account_gets_an_email(
        self, mock_send, client, passwordless_user
    ):
        _set_token(passwordless_user["user_id"], "verification_token", "old", 1)
        r = client.post(
            "/api/auth/resend-verification", json={"email": passwordless_user["email"]}
        )
        assert r.status_code == 200
        mock_send.assert_called_once()
        assert mock_send.call_args[0][0].email == passwordless_user["email"]


class TestAppConfig:
    def test_public_and_client_aware(self, client):
        r = client.get("/api/app-config", headers=IOS)
        assert r.status_code == 200
        body = r.get_json()
        assert body["client"] == {"platform": "ios", "version": "1.4.0"}
        assert body["force_upgrade"] is False
        assert "streaming_base_url" in body

    def test_force_upgrade_below_floor(self, client, monkeypatch):
        monkeypatch.setenv("MIN_CLIENT_VERSION_IOS", "2.0.0")
        assert (
            client.get("/api/app-config", headers=IOS).get_json()["force_upgrade"]
            is True
        )
        assert (
            client.get(
                "/api/app-config", headers={"X-Ceol-Client": "ios/2.0.1"}
            ).get_json()["force_upgrade"]
            is False
        )
        # a web caller is never told to upgrade
        assert client.get("/api/app-config").get_json()["force_upgrade"] is False


class TestHome:
    def test_api_home_matches_serializer(self, client):
        token = _login_native(client)["token"]
        r = client.get("/api/home", headers=_bearer(token))
        assert r.status_code == 200
        body = r.get_json()
        for key in (
            "learning_count",
            "want_to_learn_count",
            "suggested_tune",
            "upcoming_sessions",
            "in_progress_logs",
            "in_progress_recordings",
            "today",
            "week",
        ):
            assert key in body, key
        # ISO dates, not RFC 822 (the JSON provider)
        assert len(body["today"]) == 10 and body["today"][4] == "-"

    def test_home_page_still_renders(self, client):
        with client.session_transaction() as sess:
            sess["_user_id"] = "1"
            sess["_fresh"] = True
        r = client.get("/")
        assert r.status_code == 200
        assert b"Mueller" in r.data or b"learning" in r.data.lower()


class TestResolve:
    def test_session_and_instance_forms(self, client):
        assert (
            client.get("/api/resolve?path=austin/mueller").get_json()["kind"]
            == "session"
        )
        assert (
            client.get("/api/resolve?path=/sessions/austin/mueller/tunes").get_json()[
                "kind"
            ]
            == "session"
        )
        inst = client.get(
            "/api/resolve?path=https://ceol.io/sessions/austin/mueller/2024-09-03"
        ).get_json()
        assert (
            inst["kind"] == "instance" and inst["instance"]["session_instance_id"] == 1
        )
        live = client.get("/api/resolve?path=/live/instances/1").get_json()
        assert live["session"]["path"] == "austin/mueller"
        byid = client.get("/api/resolve?path=/sessions/austin/mueller/1").get_json()
        assert byid["kind"] == "instance"

    def test_unknown_is_404(self, client):
        r = client.get("/api/resolve?path=/sessions/nowhere/2024-01-01")
        assert r.status_code == 404 and r.get_json()["code"] == "not_found"
        assert client.get("/api/resolve").status_code == 400


class TestWebSession:
    def test_mints_link_that_logs_the_web_in_and_lands_on_next(self, client):
        token = _login_native(client)["token"]
        r = client.post(
            "/api/auth/web-session", json={"next": "/admin"}, headers=_bearer(token)
        )
        assert r.status_code == 200
        url = r.get_json()["url"]
        assert "/auth/login/" in url and "next=%2Fadmin" in url or "next=/admin" in url
        path = url.split("://", 1)[1]
        path = path[path.index("/"):]  # noqa: E203 (black slice style)
        r2 = client.get(path)
        assert r2.status_code == 302
        assert r2.headers["Location"].endswith("/admin")

    def test_rejects_offsite_next(self, client):
        token = _login_native(client)["token"]
        r = client.post(
            "/api/auth/web-session",
            json={"next": "https://evil.example"},
            headers=_bearer(token),
        )
        assert r.status_code == 400


class TestAASA:
    def test_absent_without_config(self, client):
        assert client.get("/.well-known/apple-app-site-association").status_code == 404

    def test_served_when_configured(self, client, monkeypatch):
        monkeypatch.setenv("IOS_APP_IDS", "ABCDE12345.io.ceol.app")
        r = client.get("/.well-known/apple-app-site-association")
        assert r.status_code == 200
        body = r.get_json()
        assert body["applinks"]["details"][0]["appIDs"] == ["ABCDE12345.io.ceol.app"]
        assert "/live/instances/*" in body["applinks"]["details"][0]["paths"]


class TestJsonDates:
    def test_provider_emits_iso_everywhere(self, client):
        import datetime

        from app import app

        with app.app_context():
            out = app.json.dumps(
                {
                    "d": datetime.date(2026, 9, 21),
                    "t": datetime.time(23, 0),
                    "dt": datetime.datetime(2026, 9, 21, 1, 2, 3),
                }
            )
        assert (
            '"2026-09-21"' in out
            and '"23:00:00"' in out
            and '"2026-09-21T01:02:03"' in out
        )
        assert "GMT" not in out
