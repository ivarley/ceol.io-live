"""Account deletion (spec 054): POST /api/me/delete-account.

The product decision this pins: the LOGIN and everything PRIVATE goes — account,
tokens, login history, tune list, instruments, contact details, and the history-table
copies of all of them — while the person's NAME stays on the rosters and attendance
lists session admins keep, as a no-login person. The shared session record (tunes
logged) stays too.

The user is created, signed in and given data through the real endpoints where one
exists, so the audit rows those endpoints write are the ones deletion must find.
"""

import uuid

import bcrypt
import pytest

from database import get_db_connection, save_to_history
from timezone_utils import now_utc

IOS = {"X-Ceol-Client": "ios/1.0.0 (build 1)"}
PASSWORD = "delete-me-123"


def _one(sql, params):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


def _count(sql, params):
    return _one(sql, params)[0]


@pytest.fixture
def doomed_user():
    """A password account with a tune list, an instrument, a session membership, an
    attendance record and a logged tune. The person row outlives the test by design,
    so the teardown removes what deletion deliberately keeps."""
    tag = uuid.uuid4().hex[:8]
    email = f"doomed{tag}@example.com"
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO person (first_name, last_name, email, sms_number, city, country,
                                thesession_user_id, created_date, last_modified_date)
            VALUES ('Dora', 'Doomed', %s, '555-0100', 'Ennis', 'Ireland', 424242, %s, %s)
            RETURNING person_id
            """,
            (email, now_utc(), now_utc()),
        )
        pid = cur.fetchone()[0]
        hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone,
                                      email_verified, is_active, created_date, last_modified_date)
            VALUES (%s, %s, %s, %s, 'UTC', TRUE, TRUE, %s, %s) RETURNING user_id
            """,
            (pid, f"doomed{tag}", email, hashed, now_utc(), now_utc()),
        )
        uid = cur.fetchone()[0]
        cur.execute("INSERT INTO person_instrument (person_id, instrument) VALUES (%s, 'Fiddle')", (pid,))
        cur.execute("SELECT session_id FROM session WHERE path = 'austin/mueller'")
        sid = cur.fetchone()[0]
        cur.execute(
            "SELECT session_instance_id FROM session_instance WHERE session_id = %s ORDER BY date LIMIT 1",
            (sid,),
        )
        siid = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed)
            VALUES (%s, %s, 'member', TRUE)
            """,
            (sid, pid),
        )
        cur.execute(
            """
            INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
            VALUES (%s, %s, 'yes')
            """,
            (siid, pid),
        )
        cur.execute(
            """
            INSERT INTO session_instance_tune (session_instance_id, name, order_position,
                                               created_by_user_id, created_date)
            VALUES (%s, 'Doomed Reel', 'zzzzV', %s, %s) RETURNING session_instance_tune_id
            """,
            (siid, uid, now_utc()),
        )
        sitid = cur.fetchone()[0]
        conn.commit()
        yield {
            "user_id": uid, "person_id": pid, "email": email, "session_id": sid,
            "session_instance_id": siid, "sit_id": sitid,
        }
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM session_instance_tune WHERE session_instance_tune_id = %s", (sitid,))
        cur.execute("DELETE FROM session_instance_person WHERE person_id = %s", (pid,))
        cur.execute("DELETE FROM session_person WHERE person_id = %s", (pid,))
        for t in ("person_tune_instrument", "person_tune", "person_instrument"):
            cur.execute(f"DELETE FROM {t} WHERE person_id = %s", (pid,))
            cur.execute(f"DELETE FROM {t}_history WHERE person_id = %s", (pid,))
        cur.execute("DELETE FROM user_session WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM login_history WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM user_account_history WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM user_account WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM person_history WHERE person_id = %s", (pid,))
        cur.execute("DELETE FROM person WHERE person_id = %s", (pid,))
        conn.commit()
        conn.close()


def _sign_in(client, user):
    """Native sign-in -> Bearer headers. Writes login_history and a user_session."""
    r = client.post(
        "/api/auth/login-password", json={"email": user["email"], "password": PASSWORD}, headers=IOS
    )
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}", **IOS}


def _add_tune(client, headers, person_id):
    """A tune on the list through the real ops endpoint, then an audit copy of it and
    of the instrument through the app's own history writer — the rows deletion must
    also find."""
    tune_id = _one("SELECT tune_id FROM tune ORDER BY tune_id LIMIT 1", ())[0]
    r = client.post(
        "/api/my-tunes/ops",
        json={"op_id": uuid.uuid4().hex, "type": "add", "tune_id": tune_id, "learn_status": "learning"},
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        ptid = _one("SELECT person_tune_id FROM person_tune WHERE person_id = %s", (person_id,))[0]
        save_to_history(cur, "person_tune", "UPDATE", ptid)
        save_to_history(cur, "person", "UPDATE", person_id)
        conn.commit()
    finally:
        conn.close()


class TestConfirmation:
    def test_the_email_must_be_typed(self, client, doomed_user):
        headers = _sign_in(client, doomed_user)
        for body in ({}, {"confirm_email": ""}, {"confirm_email": "someone@else.com"}):
            r = client.post("/api/me/delete-account", json=body, headers=headers)
            assert r.status_code == 400
            assert r.get_json()["code"] == "confirmation_mismatch"
        assert _count("SELECT COUNT(*) FROM user_account WHERE user_id = %s", (doomed_user["user_id"],)) == 1

    def test_the_email_match_ignores_case_and_spaces(self, client, doomed_user):
        headers = _sign_in(client, doomed_user)
        r = client.post(
            "/api/me/delete-account",
            json={"confirm_email": f"  {doomed_user['email'].upper()} "},
            headers=headers,
        )
        assert r.status_code == 200, r.get_json()

    def test_signed_out_is_401(self, client):
        assert client.post("/api/me/delete-account", json={"confirm_email": "x@y.z"}).status_code == 401


class TestWhatGoes:
    @pytest.fixture
    def deleted(self, client, doomed_user):
        headers = _sign_in(client, doomed_user)
        _add_tune(client, headers, doomed_user["person_id"])
        pid = doomed_user["person_id"]
        assert _count("SELECT COUNT(*) FROM person_tune_history WHERE person_id = %s", (pid,)) > 0
        assert _count("SELECT COUNT(*) FROM person_history WHERE person_id = %s AND email IS NOT NULL", (pid,)) > 0
        r = client.post("/api/me/delete-account", json={"confirm_email": doomed_user["email"]}, headers=headers)
        assert r.status_code == 200, r.get_json()
        return doomed_user, headers

    def test_the_login_and_its_trail(self, client, deleted):
        user, headers = deleted
        uid = user["user_id"]
        for table in ("user_account", "user_session", "login_history", "user_account_history"):
            assert _count(f"SELECT COUNT(*) FROM {table} WHERE user_id = %s", (uid,)) == 0, table
        # The token used a moment ago no longer authenticates anything.
        assert client.get("/api/me", headers=headers).status_code == 401

    def test_the_private_lists_and_their_history(self, deleted):
        user, _ = deleted
        pid = user["person_id"]
        for table in ("person_tune", "person_tune_instrument", "person_instrument"):
            assert _count(f"SELECT COUNT(*) FROM {table} WHERE person_id = %s", (pid,)) == 0, table
            assert _count(f"SELECT COUNT(*) FROM {table}_history WHERE person_id = %s", (pid,)) == 0, table

    def test_contact_details_on_the_person_and_in_its_history(self, deleted):
        user, _ = deleted
        cols = "email, sms_number, city, state, country, thesession_user_id"
        assert _one(f"SELECT {cols} FROM person WHERE person_id = %s", (user["person_id"],)) == (None,) * 6
        assert _count(
            "SELECT COUNT(*) FROM person_history WHERE person_id = %s AND "
            "(email IS NOT NULL OR sms_number IS NOT NULL OR city IS NOT NULL "
            " OR country IS NOT NULL OR thesession_user_id IS NOT NULL)",
            (user["person_id"],),
        ) == 0

    def test_the_email_is_free_to_register_again(self, client, deleted):
        user, _ = deleted
        try:
            r = client.post("/api/auth/check-email", json={"email": user["email"]})
            assert r.status_code == 200
            assert r.get_json().get("action") != "password"
        finally:
            # check-email on an unknown address starts a registration: a fresh account
            # and a blank person. Not ours to keep.
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT user_id, person_id FROM user_account WHERE LOWER(user_email) = LOWER(%s)", (user["email"],))
                for uid, pid in cur.fetchall():
                    cur.execute("DELETE FROM user_account_history WHERE user_id = %s", (uid,))
                    cur.execute("DELETE FROM user_account WHERE user_id = %s", (uid,))
                    if pid != user["person_id"]:
                        cur.execute("DELETE FROM person_history WHERE person_id = %s", (pid,))
                        cur.execute("DELETE FROM person WHERE person_id = %s", (pid,))
                conn.commit()
            finally:
                conn.close()


class TestWhatStays:
    def test_the_roster_entry_attendance_and_the_shared_log(self, client, doomed_user):
        headers = _sign_in(client, doomed_user)
        r = client.post("/api/me/delete-account", json={"confirm_email": doomed_user["email"]}, headers=headers)
        assert r.status_code == 200
        pid = doomed_user["person_id"]
        assert _one("SELECT first_name, last_name FROM person WHERE person_id = %s", (pid,)) == ("Dora", "Doomed")
        assert _count(
            "SELECT COUNT(*) FROM session_person WHERE person_id = %s AND session_id = %s",
            (pid, doomed_user["session_id"]),
        ) == 1
        assert _count("SELECT COUNT(*) FROM session_instance_person WHERE person_id = %s", (pid,)) == 1
        assert _count(
            "SELECT COUNT(*) FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (doomed_user["sit_id"],),
        ) == 1


class TestRefusals:
    def test_a_system_admin_is_refused_and_nothing_changes(self, client):
        r = client.post(
            "/api/auth/login-password", json={"email": "ian@ceol.io", "password": "password123"}, headers=IOS
        )
        headers = {"Authorization": f"Bearer {r.get_json()['token']}", **IOS}
        r = client.post("/api/me/delete-account", json={"confirm_email": "ian@ceol.io"}, headers=headers)
        assert r.status_code == 403
        assert r.get_json()["code"] == "admin_account"
        assert client.get("/api/me", headers=headers).status_code == 200
