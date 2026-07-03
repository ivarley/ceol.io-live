"""
Integration tests for spec 027: app update emails.

Covers the profile opt-in round-trip (PUT /api/person/<id>/update), the
no-login unsubscribe route, the admin send screen, and the admin test/send
API endpoints. SendGrid is never hit: send tests patch api_routes.send_update_email.
"""

import json
import uuid
import pytest
from contextlib import contextmanager
from unittest.mock import patch

from app import app as flask_app
from auth import User
from email_utils import generate_unsubscribe_token


@pytest.fixture
def make_user(db_conn):
    """Factory for committed person + user_account rows, cleaned up afterwards."""
    created = []

    def _make(opted_in=None, active=True, is_admin=False):
        """opted_in=None leaves receive_update_emails at the column default."""
        db_conn.rollback()
        cur = db_conn.cursor()
        unique = uuid.uuid4().hex[:10]
        email = f"upd-{unique}@example.com"
        # person.email deliberately differs from user_account.user_email:
        # emails must go to user_email, and current_user.email is person.email.
        person_email = f"upd-person-{unique}@example.com"
        cur.execute(
            "INSERT INTO person (first_name, last_name, email) VALUES (%s, %s, %s) RETURNING person_id",
            ("Upd", f"Test{unique}", person_email),
        )
        person_id = cur.fetchone()[0]
        if opted_in is not None:
            cur.execute(
                """
                INSERT INTO user_account
                    (person_id, username, user_email, timezone, is_active, is_system_admin,
                     receive_update_emails, email_verified)
                VALUES (%s, %s, %s, 'UTC', %s, %s, %s, TRUE)
                RETURNING user_id
                """,
                (person_id, f"updtest_{unique}", email, active, is_admin, opted_in),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_account
                    (person_id, username, user_email, timezone, is_active, is_system_admin,
                     email_verified)
                VALUES (%s, %s, %s, 'UTC', %s, %s, TRUE)
                RETURNING user_id
                """,
                (person_id, f"updtest_{unique}", email, active, is_admin),
            )
        user_id = cur.fetchone()[0]
        db_conn.commit()
        created.append((user_id, person_id))
        return {
            "user_id": user_id,
            "person_id": person_id,
            "username": f"updtest_{unique}",
            "email": email,  # user_account.user_email — where emails must go
            "person_email": person_email,  # person.email — what current_user.email holds
            "is_admin": is_admin,
        }

    yield _make

    db_conn.rollback()
    cur = db_conn.cursor()
    # Recipient rows can reference messages sent by another created user, so
    # clear all recipient rows first, then messages, then the users themselves.
    for user_id, _ in created:
        cur.execute("DELETE FROM email_message_recipient WHERE user_id = %s", (user_id,))
        cur.execute(
            """
            DELETE FROM email_message_recipient WHERE email_message_id IN
                (SELECT email_message_id FROM email_message WHERE sent_by_user_id = %s)
            """,
            (user_id,),
        )
    for user_id, _ in created:
        cur.execute("DELETE FROM email_message WHERE sent_by_user_id = %s", (user_id,))
    for user_id, person_id in created:
        cur.execute("DELETE FROM user_account_history WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM user_account WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM person_history WHERE person_id = %s", (person_id,))
        cur.execute("DELETE FROM person WHERE person_id = %s", (person_id,))
    db_conn.commit()


@contextmanager
def login_as(client, u):
    """Log the test client in as a make_user-created user."""
    with patch("auth.User.get_by_id") as mock_get:
        # Faithful to the real User.get_by_id: User.email comes from person.email,
        # NOT user_account.user_email.
        mock_get.return_value = User(
            user_id=u["user_id"],
            person_id=u["person_id"],
            username=u["username"],
            email=u["person_email"],
            first_name="Upd",
            last_name="Test",
            is_active=True,
            is_system_admin=u["is_admin"],
            timezone="UTC",
            email_verified=True,
        )
        with client.session_transaction() as sess:
            sess["_user_id"] = str(u["user_id"])
            sess["_fresh"] = True
            sess["is_system_admin"] = u["is_admin"]
            sess["admin_session_ids"] = []
        yield


def get_flag(db_conn, user_id):
    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "SELECT receive_update_emails FROM user_account WHERE user_id = %s", (user_id,)
    )
    return cur.fetchone()[0]


def history_count(db_conn, user_id):
    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM user_account_history WHERE user_id = %s", (user_id,)
    )
    return cur.fetchone()[0]


def make_token(user_id):
    with flask_app.app_context():
        return generate_unsubscribe_token(user_id)


@pytest.mark.integration
class TestProfileOptIn:
    def _put(self, client, u, user_fields):
        payload = {
            "person": {"first_name": "Upd", "last_name": "Test"},
            "user": {
                "user_id": u["user_id"],
                "username": u["username"],
                "user_email": u["email"],
                "timezone": "UTC",
                **user_fields,
            },
        }
        return client.put(
            f"/api/person/{u['person_id']}/update",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_opt_in_round_trip_with_history(self, client, db_conn, make_user):
        u = make_user(opted_in=False)
        before = history_count(db_conn, u["user_id"])
        with login_as(client, u):
            resp = self._put(client, u, {"receive_update_emails": True})
        assert resp.status_code == 200
        assert json.loads(resp.data)["success"] is True
        assert get_flag(db_conn, u["user_id"]) is True
        assert history_count(db_conn, u["user_id"]) == before + 1

    def test_opt_out(self, client, db_conn, make_user):
        u = make_user(opted_in=True)
        with login_as(client, u):
            resp = self._put(client, u, {"receive_update_emails": False})
        assert resp.status_code == 200
        assert get_flag(db_conn, u["user_id"]) is False

    def test_absent_key_preserves_flag(self, client, db_conn, make_user):
        """An update that doesn't mention the flag (e.g. admin edit form) must not clear it."""
        u = make_user(opted_in=True)
        with login_as(client, u):
            resp = self._put(client, u, {})
        assert resp.status_code == 200
        assert get_flag(db_conn, u["user_id"]) is True

    def test_profile_page_shows_opt_in_checkbox(self, client, make_user):
        u = make_user(opted_in=False)
        with login_as(client, u):
            resp = client.get("/me")
        assert resp.status_code == 200
        assert b"receive_update_emails" in resp.data
        assert b"Get regular updates about this app via email" in resp.data

    def test_new_account_defaults_to_subscribed(self, db_conn, make_user):
        """New accounts are subscribed by default (opt-out model)."""
        u = make_user()  # receive_update_emails left at the column default
        assert get_flag(db_conn, u["user_id"]) is True


@pytest.mark.integration
class TestUpdatePersonDetailsAuth:
    """update_person_details shipped with no auth at all (found during 027).
    It must be limited to the profile owner or a system admin, and the user
    block may only touch the user_account belonging to that person."""

    def _put(self, client, person_id, payload):
        return client.put(
            f"/api/person/{person_id}/update",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _person_payload(self, first_name="Upd"):
        return {"person": {"first_name": first_name, "last_name": "Test"}}

    def _first_name(self, db_conn, person_id):
        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute("SELECT first_name FROM person WHERE person_id = %s", (person_id,))
        return cur.fetchone()[0]

    def test_unauthenticated_rejected(self, client, db_conn, make_user):
        u = make_user()
        resp = self._put(client, u["person_id"], self._person_payload("Hacked"))
        assert resp.status_code == 401
        assert self._first_name(db_conn, u["person_id"]) == "Upd"

    def test_non_admin_cannot_update_someone_else(self, client, db_conn, make_user):
        attacker = make_user()
        victim = make_user()
        with login_as(client, attacker):
            resp = self._put(client, victim["person_id"], self._person_payload("Hacked"))
        assert resp.status_code == 403
        assert self._first_name(db_conn, victim["person_id"]) == "Upd"

    def test_owner_can_update_self(self, client, db_conn, make_user):
        u = make_user()
        with login_as(client, u):
            resp = self._put(client, u["person_id"], self._person_payload("Renamed"))
        assert resp.status_code == 200
        assert self._first_name(db_conn, u["person_id"]) == "Renamed"

    def test_admin_can_update_someone_else(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        target = make_user()
        with login_as(client, admin):
            resp = self._put(client, target["person_id"], self._person_payload("Renamed"))
        assert resp.status_code == 200
        assert self._first_name(db_conn, target["person_id"]) == "Renamed"

    def test_user_block_must_match_persons_account(self, client, db_conn, make_user):
        """An owner must not be able to smuggle another user's user_id into the
        payload and modify that account."""
        attacker = make_user()
        victim = make_user(opted_in=True)
        with login_as(client, attacker):
            resp = self._put(
                client,
                attacker["person_id"],
                {
                    "user": {
                        "user_id": victim["user_id"],
                        "username": attacker["username"] + "x",
                        "user_email": attacker["email"],
                        "receive_update_emails": False,
                    }
                },
            )
        assert resp.status_code == 403
        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute(
            "SELECT username, user_email, receive_update_emails FROM user_account WHERE user_id = %s",
            (victim["user_id"],),
        )
        assert cur.fetchone() == (victim["username"], victim["email"], True)


@pytest.mark.integration
class TestUnsubscribe:
    def test_get_valid_token_unsubscribes_without_login(self, client, db_conn, make_user):
        u = make_user(opted_in=True)
        before = history_count(db_conn, u["user_id"])
        resp = client.get(f"/unsubscribe/{make_token(u['user_id'])}")
        assert resp.status_code == 200
        assert b"unsubscribed" in resp.data.lower()
        assert get_flag(db_conn, u["user_id"]) is False
        assert history_count(db_conn, u["user_id"]) == before + 1

    def test_get_is_idempotent(self, client, db_conn, make_user):
        u = make_user(opted_in=True)
        token = make_token(u["user_id"])
        assert client.get(f"/unsubscribe/{token}").status_code == 200
        assert client.get(f"/unsubscribe/{token}").status_code == 200
        assert get_flag(db_conn, u["user_id"]) is False

    def test_post_one_click_returns_200(self, client, db_conn, make_user):
        u = make_user(opted_in=True)
        resp = client.post(f"/unsubscribe/{make_token(u['user_id'])}")
        assert resp.status_code == 200
        assert get_flag(db_conn, u["user_id"]) is False

    def test_tampered_token_changes_nothing(self, client, db_conn, make_user):
        u = make_user(opted_in=True)
        token = make_token(u["user_id"])
        resp = client.get(f"/unsubscribe/{token[:-2]}xx")
        assert resp.status_code == 404
        assert get_flag(db_conn, u["user_id"]) is True


@pytest.mark.integration
class TestAdminEmailUpdatesPage:
    def test_non_admin_redirected(self, client, make_user):
        u = make_user()
        with login_as(client, u):
            resp = client.get("/admin/email-updates")
        assert resp.status_code == 302

    def test_admin_sees_recipient_count_and_compose_form(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        make_user(opted_in=True)
        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM user_account
            WHERE receive_update_emails = TRUE AND is_active = TRUE AND user_email IS NOT NULL
            """
        )
        expected_count = cur.fetchone()[0]
        with login_as(client, admin):
            resp = client.get("/admin/email-updates")
        assert resp.status_code == 200
        assert f"{expected_count}".encode() in resp.data
        assert b"subject" in resp.data.lower()
        assert b"markdown" in resp.data.lower()

    def test_history_table_shows_past_messages(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        db_conn.rollback()
        cur = db_conn.cursor()
        unique_subject = f"Past message {uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO email_message (subject, body_markdown, sent_by_user_id,
                                       recipient_count, success_count, failure_count)
            VALUES (%s, 'body', %s, 3, 2, 1)
            """,
            (unique_subject, admin["user_id"]),
        )
        db_conn.commit()
        with login_as(client, admin):
            resp = client.get("/admin/email-updates")
        assert resp.status_code == 200
        assert unique_subject.encode() in resp.data
        assert admin["username"].encode() in resp.data


@pytest.mark.integration
class TestAdminEmailUpdatesApi:
    TEST_URL = "/api/admin/email-updates/test"
    SEND_URL = "/api/admin/email-updates/send"

    def _post(self, client, url, payload):
        return client.post(url, data=json.dumps(payload), content_type="application/json")

    def _messages_count(self, db_conn):
        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM email_message")
        return cur.fetchone()[0]

    def test_non_admin_gets_403(self, client, make_user):
        u = make_user()
        with login_as(client, u):
            for url in (self.TEST_URL, self.SEND_URL):
                resp = self._post(client, url, {"subject": "s", "body_markdown": "b"})
                assert resp.status_code == 403

    def test_missing_subject_or_body_rejected(self, client, make_user):
        admin = make_user(is_admin=True)
        with login_as(client, admin):
            for url in (self.TEST_URL, self.SEND_URL):
                assert self._post(client, url, {"subject": "", "body_markdown": "b"}).status_code == 400
                assert self._post(client, url, {"subject": "s", "body_markdown": " "}).status_code == 400

    def test_test_send_goes_only_to_admin_and_records_nothing(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        make_user(opted_in=True)  # would be a recipient of a real send
        before = self._messages_count(db_conn)
        with login_as(client, admin), patch("api_routes.send_update_email", return_value=True) as mock_send:
            resp = self._post(client, self.TEST_URL, {"subject": "Test", "body_markdown": "Hi"})
        assert resp.status_code == 200
        assert json.loads(resp.data)["success"] is True
        mock_send.assert_called_once_with(admin["user_id"], admin["email"], "Test", "Hi")
        assert self._messages_count(db_conn) == before

    def test_send_records_message_and_recipients(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        in1 = make_user(opted_in=True)
        in2 = make_user(opted_in=True)
        out = make_user(opted_in=False)
        inactive = make_user(opted_in=True, active=False)
        with login_as(client, admin), patch("api_routes.send_update_email", return_value=True) as mock_send:
            resp = self._post(client, self.SEND_URL, {"subject": "News", "body_markdown": "# Hi"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["success_count"] == data["recipient_count"]
        assert data["failure_count"] == 0

        sent_to_user_ids = {c.args[0] for c in mock_send.call_args_list}
        assert {in1["user_id"], in2["user_id"]} <= sent_to_user_ids
        assert out["user_id"] not in sent_to_user_ids
        assert inactive["user_id"] not in sent_to_user_ids

        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT em.email_message_id, em.subject, em.recipient_count, em.success_count, em.failure_count
            FROM email_message em ORDER BY em.email_message_id DESC LIMIT 1
            """
        )
        msg_id, subject, recipient_count, success_count, failure_count = cur.fetchone()
        assert subject == "News"
        assert recipient_count == data["recipient_count"]
        assert success_count == data["recipient_count"]
        assert failure_count == 0
        cur.execute(
            "SELECT user_id, email, status FROM email_message_recipient WHERE email_message_id = %s",
            (msg_id,),
        )
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        assert rows[in1["user_id"]] == (in1["email"], "sent")
        assert rows[in2["user_id"]] == (in2["email"], "sent")
        assert len(rows) == recipient_count
        # cleanup rows tied to seeded/admin sender handled by make_user teardown

    def test_one_failure_is_recorded_and_does_not_abort(self, client, db_conn, make_user):
        admin = make_user(is_admin=True)
        ok_user = make_user(opted_in=True)
        bad_user = make_user(opted_in=True)

        def fake_send(user_id, to_email, subject, body_markdown):
            return user_id != bad_user["user_id"]

        with login_as(client, admin), patch("api_routes.send_update_email", side_effect=fake_send):
            resp = self._post(client, self.SEND_URL, {"subject": "News", "body_markdown": "Hi"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["failure_count"] == 1
        assert data["success_count"] == data["recipient_count"] - 1

        db_conn.rollback()
        cur = db_conn.cursor()
        cur.execute(
            """
            SELECT status FROM email_message_recipient
            WHERE user_id = %s AND email_message_id =
                  (SELECT MAX(email_message_id) FROM email_message)
            """,
            (bad_user["user_id"],),
        )
        assert cur.fetchone()[0] == "failed"
        cur.execute(
            """
            SELECT status FROM email_message_recipient
            WHERE user_id = %s AND email_message_id =
                  (SELECT MAX(email_message_id) FROM email_message)
            """,
            (ok_user["user_id"],),
        )
        assert cur.fetchone()[0] == "sent"
