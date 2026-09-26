"""Session-scoped recording management (schema/053).

The segmenter was system-admin only because it builds an ML training corpus, not
because the work belongs to site administrators — the person who recorded a night
and knows what was played is usually the one running it. So the grant moved onto
session_person, and these tests pin down the three things that makes load-bearing:

1. **It takes both bits.** `can_manage_recordings` without `is_admin` is nothing.
   Anything else would make "who can do this here" unanswerable from the session's
   admin list.
2. **It is one session wide.** A grant on session A must not reach session B's
   audio — that is the whole reason it isn't a role on the user account.
3. **The cross-session surfaces stay shut.** /admin/recordings and the session
   picker behind it show every night in the system; a session admin has no
   business there no matter what they hold on their own session.

The system-admin path is covered by the other 050 suites; here a system admin
only appears as the control that proves a test is measuring the grant and not
some unrelated refusal.
"""

from unittest.mock import patch

import pytest

from auth import User

PERM_SESSION = 95400          # the session the grant is for
PERM_OTHER_SESSION = 95401    # a second session, to prove the grant doesn't reach it
PERM_INSTANCE = 95402
PERM_OTHER_INSTANCE = 95403
PERM_PERSON = 95404
PERM_USER = 95405
PERM_RECORDING = 95406
PERM_OTHER_RECORDING = 95407


@pytest.fixture
def granted_world(db_setup):
    """Two sessions, each with an instance and a recording, and one person who is
    an admin of the first only. The grant bit starts OFF."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Perm053', 'perm053-test'), "
        "(%s, 'Perm053 Other', 'perm053-other')",
        (PERM_SESSION, PERM_OTHER_SESSION),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES "
        "(%s, %s, '2026-06-04'), (%s, %s, '2026-06-05')",
        (PERM_INSTANCE, PERM_SESSION, PERM_OTHER_INSTANCE, PERM_OTHER_SESSION),
    )
    cur.execute(
        "INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'Perm', 'Tester')",
        (PERM_PERSON,),
    )
    cur.execute(
        "INSERT INTO user_account (user_id, person_id, username, user_email, hashed_password, "
        "is_system_admin, is_active, email_verified) "
        "VALUES (%s, %s, 'perm053', 'perm053@example.com', 'x', FALSE, TRUE, TRUE)",
        (PERM_USER, PERM_PERSON),
    )
    # A session admin of PERM_SESSION, with the recordings bit OFF.
    cur.execute(
        "INSERT INTO session_person (session_id, person_id, is_admin, can_manage_recordings) "
        "VALUES (%s, %s, TRUE, FALSE)",
        (PERM_SESSION, PERM_PERSON),
    )
    for recording_id, instance_id in ((PERM_RECORDING, PERM_INSTANCE),
                                      (PERM_OTHER_RECORDING, PERM_OTHER_INSTANCE)):
        cur.execute(
            "INSERT INTO recording (recording_id, session_instance_id, storage_key, duration_ms, "
            "is_clock_anchor, status) VALUES (%s, %s, %s, 600000, TRUE, 'ready')",
            (recording_id, instance_id, f"recordings/perm053/{recording_id}.mp3"),
        )
    conn.commit()
    yield
    cur.execute("DELETE FROM recording_history WHERE recording_id IN (%s, %s)",
                (PERM_RECORDING, PERM_OTHER_RECORDING))
    cur.execute("DELETE FROM recording WHERE recording_id IN (%s, %s)",
                (PERM_RECORDING, PERM_OTHER_RECORDING))
    cur.execute("DELETE FROM session_person_history WHERE person_id = %s", (PERM_PERSON,))
    cur.execute("DELETE FROM session_person WHERE person_id = %s", (PERM_PERSON,))
    cur.execute("DELETE FROM user_account WHERE user_id = %s", (PERM_USER,))
    cur.execute("DELETE FROM person WHERE person_id = %s", (PERM_PERSON,))
    cur.execute("DELETE FROM session_instance WHERE session_id IN (%s, %s)",
                (PERM_SESSION, PERM_OTHER_SESSION))
    cur.execute("DELETE FROM session WHERE session_id IN (%s, %s)", (PERM_SESSION, PERM_OTHER_SESSION))
    conn.commit()
    conn.close()


def _set_flags(is_admin=None, can_manage=None):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    if is_admin is not None:
        cur.execute("UPDATE session_person SET is_admin = %s WHERE session_id = %s AND person_id = %s",
                    (is_admin, PERM_SESSION, PERM_PERSON))
    if can_manage is not None:
        cur.execute("UPDATE session_person SET can_manage_recordings = %s "
                    "WHERE session_id = %s AND person_id = %s",
                    (can_manage, PERM_SESSION, PERM_PERSON))
    conn.commit()
    conn.close()


class as_the_session_admin:
    """Sign in as the non-system-admin person the fixture created."""

    def __init__(self, client):
        self.client = client

    def __enter__(self):
        self.patcher = patch("auth.User.get_by_id")
        mock = self.patcher.start()
        mock.return_value = User(
            user_id=PERM_USER, person_id=PERM_PERSON, username="perm053",
            email="perm053@example.com", is_system_admin=False,
            first_name="Perm", last_name="Tester",
        )
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(PERM_USER)
            sess["_fresh"] = True
            sess["is_system_admin"] = False
        return self

    def __exit__(self, *exc):
        self.patcher.stop()
        with self.client.session_transaction() as sess:
            sess.clear()


# --------------------------------------------------------------------------- #
# 1. it takes both bits
# --------------------------------------------------------------------------- #


def test_session_admin_without_the_grant_is_refused(client, granted_world):
    """Where every session admin starts: the bit defaults off, so this migration
    handed nobody anything they didn't already have."""
    with as_the_session_admin(client):
        assert client.get(f"/api/recordings/{PERM_RECORDING}/segmenter").status_code == 403
        assert client.get(f"/api/session-instances/{PERM_INSTANCE}/recordings").status_code == 403


def test_the_grant_alone_without_session_admin_is_nothing(client, granted_world):
    _set_flags(is_admin=False, can_manage=True)
    with as_the_session_admin(client):
        resp = client.get(f"/api/recordings/{PERM_RECORDING}/segmenter")
    assert resp.status_code == 403


def test_both_bits_together_open_the_session(client, granted_world):
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        assert client.get(f"/api/recordings/{PERM_RECORDING}/segmenter").status_code == 200
        listing = client.get(f"/api/session-instances/{PERM_INSTANCE}/recordings")
        assert listing.status_code == 200
        assert [r["recording_id"] for r in listing.get_json()["recordings"]] == [PERM_RECORDING]


# --------------------------------------------------------------------------- #
# 2. one session wide
# --------------------------------------------------------------------------- #


def test_the_grant_does_not_reach_another_session(client, granted_world):
    """The reason this lives on session_person rather than on the account."""
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        assert client.get(f"/api/recordings/{PERM_OTHER_RECORDING}/segmenter").status_code == 403
        assert client.get(f"/api/session-instances/{PERM_OTHER_INSTANCE}/recordings").status_code == 403
        assert client.delete(f"/api/recordings/{PERM_OTHER_RECORDING}").status_code == 403
        assert client.post(
            "/api/recordings/upload-url",
            json={"session_instance_id": PERM_OTHER_INSTANCE, "filename": "x.mp3"},
        ).status_code == 403


def test_every_write_verb_is_gated_the_same_way(client, granted_world):
    """One missed endpoint is the whole hole, so each is asserted rather than
    trusting that they share a helper."""
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        for path, method in (
            (f"/api/recordings/{PERM_OTHER_RECORDING}/peaks", "get"),
            (f"/api/recordings/{PERM_OTHER_RECORDING}/status", "get"),
            (f"/api/recordings/{PERM_OTHER_RECORDING}/export", "get"),
            (f"/api/recordings/{PERM_OTHER_RECORDING}/reprocess", "post"),
            (f"/api/recordings/{PERM_OTHER_RECORDING}", "delete"),
            (f"/api/recordings/{PERM_OTHER_RECORDING}/segments/1", "delete"),
        ):
            resp = getattr(client, method)(path)
            assert resp.status_code == 403, f"{method.upper()} {path} returned {resp.status_code}"

        resp = client.put(f"/api/recordings/{PERM_OTHER_RECORDING}/segments/1", json={"start_ms": 1})
        assert resp.status_code == 403


def test_a_missing_recording_still_reads_as_missing(client, granted_world):
    """404 and 403 stay distinguishable: every caller here is an admin of
    something, and collapsing the two would make a misconfigured permission look
    like a deleted recording."""
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        assert client.get("/api/recordings/987654321/status").status_code == 404


# --------------------------------------------------------------------------- #
# 3. the cross-session surfaces stay shut
# --------------------------------------------------------------------------- #


def test_the_site_wide_index_and_picker_remain_system_admin_only(client, granted_world):
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        # The picker behind the admin upload form spans every session.
        assert client.get(f"/api/admin/sessions/{PERM_SESSION}/instances").status_code == 403
        # And the index page itself redirects rather than rendering.
        page = client.get("/admin/recordings")
        assert page.status_code == 302


def test_the_segmenter_page_opens_for_a_granted_session_admin(client, granted_world):
    """The page and the API behind it have to agree about who is allowed in."""
    _set_flags(is_admin=True, can_manage=True)
    with as_the_session_admin(client):
        assert client.get(f"/admin/recordings/{PERM_RECORDING}/segment").status_code == 200
        # ...and not for someone else's night.
        other = client.get(f"/admin/recordings/{PERM_OTHER_RECORDING}/segment")
        assert other.status_code == 302
        assert other.headers["Location"].endswith("/")


def test_a_signed_out_visitor_gets_nothing(client, granted_world):
    assert client.get(f"/api/recordings/{PERM_RECORDING}/segmenter").status_code in (302, 401, 403)


# --------------------------------------------------------------------------- #
# 4. granting it
# --------------------------------------------------------------------------- #


def test_a_system_admin_can_grant_and_revoke_the_bit(client, admin_user, granted_world, db_cursor):
    with admin_user:
        granted = client.put(
            f"/api/admin/sessions/perm053-test/people/{PERM_PERSON}/admin",
            json={"can_manage_recordings": True},
        )
    assert granted.status_code == 200
    db_cursor.execute(
        "SELECT is_admin, can_manage_recordings FROM session_person "
        "WHERE session_id = %s AND person_id = %s",
        (PERM_SESSION, PERM_PERSON),
    )
    # is_admin was NOT in the body, so it must be untouched.
    assert db_cursor.fetchone() == (True, True)

    with admin_user:
        client.put(
            f"/api/admin/sessions/perm053-test/people/{PERM_PERSON}/admin",
            json={"can_manage_recordings": False},
        )
    db_cursor.execute(
        "SELECT can_manage_recordings FROM session_person WHERE session_id = %s AND person_id = %s",
        (PERM_SESSION, PERM_PERSON),
    )
    assert db_cursor.fetchone()[0] is False


def test_setting_one_grant_leaves_the_other_alone(client, admin_user, granted_world, db_cursor):
    """The two checkboxes post to one endpoint; a body carrying only one field
    must not clear the other."""
    _set_flags(is_admin=True, can_manage=True)
    with admin_user:
        client.put(
            f"/api/admin/sessions/perm053-test/people/{PERM_PERSON}/admin",
            json={"is_admin": False},
        )
    db_cursor.execute(
        "SELECT is_admin, can_manage_recordings FROM session_person "
        "WHERE session_id = %s AND person_id = %s",
        (PERM_SESSION, PERM_PERSON),
    )
    # The recordings bit is remembered, so restoring session-admin restores the
    # grant rather than silently dropping it.
    assert db_cursor.fetchone() == (False, True)


def test_a_session_admin_cannot_grant_it_to_themselves(client, granted_world):
    """It hands out a tool that writes to object storage and deletes audio, so it
    is not something a session admin can pass onward."""
    _set_flags(is_admin=True, can_manage=False)
    with as_the_session_admin(client):
        resp = client.put(
            f"/api/admin/sessions/perm053-test/people/{PERM_PERSON}/admin",
            json={"can_manage_recordings": True},
        )
    assert resp.status_code == 403
