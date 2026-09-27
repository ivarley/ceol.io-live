"""Pending registrations (migration 056).

Typing an address with no account on the email-first login page must not create
anything but a pending_registration row. The person and the account appear only
when the emailed link is clicked, so a mistyped address (ian@gmial.com) leaves no
phantom account behind.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest

from database import get_db_connection
from timezone_utils import now_utc

IOS = {"X-Ceol-Client": "ios/1.4.0 (build 12)"}


def _q(sql, params=()):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else None
        conn.commit()
        return rows
    finally:
        conn.close()


def _pending(email):
    return _q(
        "SELECT verification_token, verification_token_expires FROM pending_registration "
        "WHERE LOWER(email) = LOWER(%s)",
        (email,),
    )


def _accounts(email):
    return _q(
        "SELECT user_id, person_id, email_verified, hashed_password FROM user_account "
        "WHERE LOWER(user_email) = LOWER(%s)",
        (email,),
    )


def _max_person_id():
    return _q("SELECT COALESCE(MAX(person_id), 0) FROM person")[0][0]


@pytest.fixture
def new_email():
    """A made-up address with nothing behind it; everything it causes is removed."""
    email = f"newperson+{uuid.uuid4().hex[:10]}@example.com"
    yield email
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, person_id FROM user_account WHERE LOWER(user_email) = LOWER(%s)",
            (email,),
        )
        for uid, pid in cur.fetchall():
            for table in ("login_history", "user_session", "user_account_history"):
                cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM user_account WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM person_history WHERE person_id = %s", (pid,))
            cur.execute("DELETE FROM person WHERE person_id = %s", (pid,))
        cur.execute("DELETE FROM person WHERE LOWER(email) = LOWER(%s)", (email,))
        cur.execute(
            "DELETE FROM login_history WHERE LOWER(username) = LOWER(%s)", (email,)
        )
        cur.execute(
            "DELETE FROM pending_registration WHERE LOWER(email) = LOWER(%s)", (email,)
        )
        conn.commit()
    finally:
        conn.close()


def _enter_email(client, email):
    r = client.post("/api/auth/check-email", json={"email": email})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


@patch("web_routes.send_registration_email", return_value=True)
class TestEnteringAnUnknownEmail:
    def test_records_a_pending_row_and_creates_nothing_else(
        self, mock_send, client, new_email
    ):
        before = _max_person_id()

        body = _enter_email(client, new_email)

        assert body["action"] == "registration_started"
        assert _accounts(new_email) == []
        assert _max_person_id() == before
        rows = _pending(new_email)
        assert len(rows) == 1
        mock_send.assert_called_once_with(new_email, rows[0][0])

    def test_entering_it_again_reuses_the_row_and_the_link(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        first_token = _pending(new_email)[0][0]

        _enter_email(client, new_email.upper())

        rows = _pending(new_email)
        assert len(rows) == 1
        assert rows[0][0] == first_token  # the first email's link still works
        assert mock_send.call_count == 2

    def test_an_expired_row_gets_a_new_link(self, mock_send, client, new_email):
        _enter_email(client, new_email)
        old_token = _pending(new_email)[0][0]
        _q(
            "UPDATE pending_registration SET verification_token_expires = %s WHERE LOWER(email) = LOWER(%s)",
            (now_utc() - timedelta(minutes=1), new_email),
        )

        _enter_email(client, new_email)

        rows = _pending(new_email)
        assert len(rows) == 1
        assert rows[0][0] != old_token
        assert rows[0][1] > now_utc()


@patch("web_routes.send_registration_email", return_value=True)
class TestClickingTheLink:
    def test_creates_the_account_and_continues_to_set_password(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]

        r = client.get(f"/verify-email/{token}")

        assert r.status_code == 302
        assert "/auth/set-password" in r.headers["Location"]
        accounts = _accounts(new_email)
        assert len(accounts) == 1
        _, person_id, verified, hashed_password = accounts[0]
        assert verified is True
        assert hashed_password is None
        assert _pending(new_email) == []

        # The rest of the flow is unchanged: skipping the password goes on to
        # profile setup, since the new person has no name or location yet.
        r = client.post(
            "/auth/set-password", data={"password": "", "confirm_password": ""}
        )
        assert r.status_code == 302
        assert "/auth/setup-profile" in r.headers["Location"]
        assert client.get("/auth/setup-profile").status_code == 200

    def test_takes_over_an_accountless_person_with_that_email(
        self, mock_send, client, new_email
    ):
        # An admin added this person to a roster by email before they signed up.
        person_id = _q(
            "INSERT INTO person (first_name, last_name, email) VALUES ('Nora', 'New', %s) RETURNING person_id",
            (new_email,),
        )[0][0]
        _enter_email(client, new_email)

        client.get(f"/verify-email/{_pending(new_email)[0][0]}")

        accounts = _accounts(new_email)
        assert len(accounts) == 1
        assert accounts[0][1] == person_id
        assert (
            _q("SELECT email FROM person WHERE person_id = %s", (person_id,))[0][0]
            is None
        )

    def test_a_second_click_does_not_create_a_second_account(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]
        client.get(f"/verify-email/{token}")
        client.get("/logout")

        r = client.get(f"/verify-email/{token}")

        assert r.status_code == 302
        assert "/resend-verification" in r.headers["Location"]
        assert len(_accounts(new_email)) == 1

    def test_a_stale_link_after_the_account_exists_creates_nothing(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]
        # Meanwhile the address got an account some other way (e.g. /register).
        pid = _q(
            "INSERT INTO person (first_name, last_name) VALUES ('Other', 'Way') RETURNING person_id"
        )[0][0]
        _q(
            "INSERT INTO user_account (person_id, username, user_email, email_verified) "
            "VALUES (%s, %s, %s, TRUE)",
            (pid, f"otherway{uuid.uuid4().hex[:8]}", new_email),
        )
        before = _max_person_id()

        r = client.get(f"/verify-email/{token}")

        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        assert len(_accounts(new_email)) == 1
        assert _max_person_id() == before
        assert _pending(new_email) == []
        with client.session_transaction() as sess:
            assert "_user_id" not in sess


class TestResendVerification:
    @patch("web_routes.send_registration_email", return_value=True)
    def test_web_resend_sends_the_pending_link_again(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]
        mock_send.reset_mock()

        r = client.post("/resend-verification", data={"email": new_email})

        assert r.status_code == 302
        mock_send.assert_called_once_with(new_email, token)
        assert _accounts(new_email) == []

    @patch("web_routes.send_registration_email", return_value=True)
    def test_web_resend_for_an_unknown_email_starts_nothing(
        self, mock_send, client, new_email
    ):
        client.post("/resend-verification", data={"email": new_email})

        mock_send.assert_not_called()
        assert _pending(new_email) == []

    @patch("api_app_routes.send_registration_email", return_value=True)
    @patch("web_routes.send_registration_email", return_value=True)
    def test_native_resend_sends_the_pending_link_again(
        self, _web_send, native_send, client, new_email
    ):
        _enter_email(client, new_email)

        r = client.post("/api/auth/resend-verification", json={"email": new_email})

        assert r.status_code == 200
        native_send.assert_called_once_with(new_email, _pending(new_email)[0][0])


@patch("web_routes.send_registration_email", return_value=True)
class TestNativeExchange:
    def test_pending_token_creates_the_account_and_returns_a_bearer_token(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]

        r = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)

        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["method"] == "email_verification"
        assert body["token"]
        assert len(_accounts(new_email)) == 1
        assert _pending(new_email) == []

    def test_stale_pending_token_is_409_and_creates_nothing(
        self, mock_send, client, new_email
    ):
        _enter_email(client, new_email)
        token = _pending(new_email)[0][0]
        pid = _q(
            "INSERT INTO person (first_name, last_name) VALUES ('Other', 'Way') RETURNING person_id"
        )[0][0]
        _q(
            "INSERT INTO user_account (person_id, username, user_email, email_verified) "
            "VALUES (%s, %s, %s, TRUE)",
            (pid, f"otherway{uuid.uuid4().hex[:8]}", new_email),
        )

        r = client.post("/api/auth/exchange", json={"token": token}, headers=IOS)

        assert r.status_code == 409
        assert r.get_json()["code"] == "account_exists"
        assert len(_accounts(new_email)) == 1
