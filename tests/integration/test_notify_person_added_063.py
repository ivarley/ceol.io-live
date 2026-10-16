"""Migration 063: a session admin can stop the "someone was added" emails.

The setting is person.notify_person_added: on by default, turned off on the profile
(PUT /api/person/<id>/update) or by the one-click link in the email
(/unsubscribe/person-added/<token>). Admins who turned it off get no email, and their
session doesn't fall back to emailing the system admins instead.
"""

import json
from unittest.mock import patch

import pytest

from app import app as flask_app
from database import get_db_connection
from email_utils import (
    generate_person_unsubscribe_token,
    generate_unsubscribe_token,
    send_person_added_email,
    verify_person_unsubscribe_token,
)
from places_helpers import logged_in
from test_update_emails import login_as, make_user  # noqa: F401 (fixture)


def flag(db_conn, person_id):
    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "SELECT notify_person_added FROM person WHERE person_id = %s", (person_id,)
    )
    return cur.fetchone()[0]


def history_rows(db_conn, person_id):
    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM person_history WHERE person_id = %s", (person_id,)
    )
    return cur.fetchone()[0]


def test_on_by_default(db_conn, make_user):
    u = make_user()
    assert flag(db_conn, u["person_id"]) is True


class TestTheEmail:
    def _send(self):
        with flask_app.test_request_context("/"), patch(
            "email_utils.send_email_via_sendgrid", return_value=True
        ) as send:
            send_person_added_email(
                {
                    "name": "A B",
                    "email": "a@example.com",
                    "language": "en",
                    "person_id": 42,
                },
                {"name": "P Q", "email": None, "relationship": "member"},
                {"name": "Mueller", "location": "Austin", "path": "austin/mueller"},
            )
        return send.call_args

    def test_ends_with_why_a_stop_link_and_the_settings_link(self):
        args, kwargs = self._send()
        body = args[2]
        assert 'because you look after "Mueller" on Ceol.' in body
        assert "Change which emails you get from Ceol: http://localhost/me" in body
        url = kwargs["unsubscribe_url"]
        assert f"Stop these emails: {url}" in body
        token = url.rsplit("/", 1)[1]
        with flask_app.app_context():
            assert verify_person_unsubscribe_token(token) == 42

    def test_the_tokens_dont_cross(self):
        # An update email's token names a user, this one a person.
        with flask_app.app_context():
            assert (
                verify_person_unsubscribe_token(generate_unsubscribe_token(42)) is None
            )


class TestTheLink:
    def test_turns_it_off(self, client, db_conn, make_user):
        u = make_user()
        before = history_rows(db_conn, u["person_id"])
        token = generate_person_unsubscribe_token(u["person_id"])
        resp = client.get(f"/unsubscribe/person-added/{token}")
        assert resp.status_code == 200
        assert b"session you look after" in resp.data
        assert flag(db_conn, u["person_id"]) is False
        assert history_rows(db_conn, u["person_id"]) == before + 1

    def test_one_click_post(self, client, db_conn, make_user):
        u = make_user()
        token = generate_person_unsubscribe_token(u["person_id"])
        resp = client.post(
            f"/unsubscribe/person-added/{token}", data="List-Unsubscribe=One-Click"
        )
        assert resp.status_code == 200
        assert flag(db_conn, u["person_id"]) is False

    def test_a_bad_token(self, client):
        assert client.get("/unsubscribe/person-added/nonsense").status_code == 404

    def test_an_update_email_token_is_refused(self, client, db_conn, make_user):
        u = make_user()
        token = generate_unsubscribe_token(u["person_id"])
        assert client.get(f"/unsubscribe/person-added/{token}").status_code == 404
        assert flag(db_conn, u["person_id"]) is True


class TestTheProfile:
    def _put(self, client, u, person_fields):
        return client.put(
            f"/api/person/{u['person_id']}/update",
            data=json.dumps(
                {"person": {"first_name": "Upd", "last_name": "Test", **person_fields}}
            ),
            content_type="application/json",
        )

    def test_off_and_on(self, client, db_conn, make_user):
        u = make_user()
        with login_as(client, u):
            assert (
                self._put(client, u, {"notify_person_added": False}).status_code == 200
            )
        assert flag(db_conn, u["person_id"]) is False
        with login_as(client, u):
            assert (
                self._put(client, u, {"notify_person_added": True}).status_code == 200
            )
        assert flag(db_conn, u["person_id"]) is True

    def test_a_save_that_leaves_it_out_keeps_it(self, client, db_conn, make_user):
        u = make_user()
        with login_as(client, u):
            self._put(client, u, {"notify_person_added": False})
            self._put(client, u, {})
        assert flag(db_conn, u["person_id"]) is False


def test_admins_who_said_no_get_nothing(client):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id FROM session_person WHERE is_admin GROUP BY session_id LIMIT 1"
    )
    session_id = cur.fetchone()[0]
    cur.execute(
        "SELECT person_id FROM session_person WHERE session_id = %s AND is_admin",
        (session_id,),
    )
    admin_ids = [r[0] for r in cur.fetchall()]
    cur.execute(
        """SELECT person_id FROM person WHERE person_id NOT IN
           (SELECT person_id FROM session_person WHERE session_id = %s) LIMIT 1""",
        (session_id,),
    )
    newcomer = cur.fetchone()[0]
    cur.execute(
        "UPDATE person SET notify_person_added = FALSE WHERE person_id = ANY(%s)",
        (admin_ids,),
    )
    conn.commit()
    try:
        with logged_in(client), patch(
            "api_routes.send_person_added_email", return_value=True
        ) as send:
            resp = client.post(
                "/api/add-person-to-session",
                json={"person_id": newcomer, "session_id": session_id},
            )
        assert resp.status_code == 200, resp.get_json()
        assert not send.called
    finally:
        cur.execute(
            "DELETE FROM session_person WHERE person_id = %s AND session_id = %s",
            (newcomer, session_id),
        )
        cur.execute(
            "UPDATE person SET notify_person_added = TRUE WHERE person_id = ANY(%s)",
            (admin_ids,),
        )
        conn.commit()
        conn.close()
