"""The home page's "Continue Tagging" card (spec 050).

The companion to "Continue Logging": a three-hour recording is not timestamped
in one sitting, and before this the only way back to a half-tagged one was to
remember it existed.

Four decisions are pinned here, because each of them is a way the card could
quietly become wrong:

1. **Half-done shows, with its counts.** Placed and total both come off the
   instance's own log, so the number in the card is the number in the tool.
2. **Finished drops off.** There is no completion flag on a recording — done is
   "every tune placed" — so the card empties itself rather than needing to be
   dismissed.
3. **Somebody else's work is not mine.** The list is keyed on who placed the
   marks, exactly as the logging list is keyed on who edited the log.
4. **The permission is re-checked now.** Having placed marks once is not the
   same as still being allowed to open the tool, and a card that links into a
   refusal is worse than no card.
"""

from unittest.mock import patch

import pytest

from auth import User

CT_SESSION = 95600
CT_INSTANCE = 95601
CT_PERSON = 95602
CT_USER = 95603
CT_OTHER_USER = 95604
CT_RECORDING = 95605
CT_TUNE_BASE = 95610
TUNE_COUNT = 4


@pytest.fixture
def tagging_world(db_setup):
    """One night with four logged tunes and one ready recording, nothing placed.

    Each test places what it needs, so "half done" and "all done" are the same
    fixture seen at two moments rather than two fixtures that can drift.
    """
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Tagging050', 'tagging050-test')",
        (CT_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-08')",
        (CT_INSTANCE, CT_SESSION),
    )
    cur.execute(
        "INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'Tag', 'Ger')",
        (CT_PERSON,),
    )
    cur.execute(
        "INSERT INTO user_account (user_id, person_id, username, user_email, hashed_password, "
        "is_system_admin, is_active, email_verified) "
        "VALUES (%s, %s, 'tagging050', 'tagging050@example.com', 'x', FALSE, TRUE, TRUE)",
        (CT_USER, CT_PERSON),
    )
    cur.execute(
        "INSERT INTO session_person (session_id, person_id, is_admin, can_manage_recordings) "
        "VALUES (%s, %s, TRUE, TRUE)",
        (CT_SESSION, CT_PERSON),
    )
    for i in range(TUNE_COUNT):
        cur.execute(
            "INSERT INTO session_instance_tune (session_instance_tune_id, session_instance_id, name, "
            "order_position, record_type) VALUES (%s, %s, %s, %s, 'tune')",
            (CT_TUNE_BASE + i, CT_INSTANCE, f"Tagging Tune {i}", f"a{i}"),
        )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, label, storage_key, duration_ms, "
        "is_clock_anchor, status) VALUES (%s, %s, 'Tagging Night', 'recordings/ct/master.m4a', "
        "600000, TRUE, 'ready')",
        (CT_RECORDING, CT_INSTANCE),
    )
    conn.commit()
    yield conn, cur
    cur.execute("DELETE FROM recording_tune_segment WHERE recording_id = %s", (CT_RECORDING,))
    cur.execute("DELETE FROM recording_tune_segment_history WHERE recording_id = %s", (CT_RECORDING,))
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (CT_RECORDING,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (CT_RECORDING,))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (CT_INSTANCE,))
    cur.execute("DELETE FROM session_person_history WHERE person_id = %s", (CT_PERSON,))
    cur.execute("DELETE FROM session_person WHERE person_id = %s", (CT_PERSON,))
    cur.execute("DELETE FROM user_account WHERE user_id = %s", (CT_USER,))
    cur.execute("DELETE FROM person WHERE person_id = %s", (CT_PERSON,))
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (CT_SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (CT_SESSION,))
    conn.commit()
    conn.close()


def _place(cur, conn, count, user_id=CT_USER):
    """Place the first `count` tunes, attributed to `user_id`."""
    for i in range(count):
        cur.execute(
            "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms, "
            "created_by_user_id, last_modified_user_id) VALUES (%s, %s, %s, %s, %s)",
            (CT_RECORDING, CT_TUNE_BASE + i, 10000 * (i + 1), user_id, user_id),
        )
    conn.commit()


class as_the_tagger:
    """Sign in as the session admin who holds the recordings grant."""

    def __init__(self, client):
        self.client = client

    def __enter__(self):
        self.patcher = patch("auth.User.get_by_id")
        self.patcher.start().return_value = User(
            user_id=CT_USER, person_id=CT_PERSON, username="tagging050",
            email="tagging050@example.com", is_system_admin=False,
            first_name="Tag", last_name="Ger",
        )
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(CT_USER)
            sess["_fresh"] = True
            sess["is_system_admin"] = False
        return self

    def __exit__(self, *exc):
        self.patcher.stop()
        with self.client.session_transaction() as sess:
            sess.clear()


def _home(client):
    with as_the_tagger(client):
        res = client.get("/")
    assert res.status_code == 200
    return res.get_data(as_text=True)


SEGMENT_LINK = f"/admin/recordings/{CT_RECORDING}/segment"


def test_half_tagged_recording_appears_with_its_counts(client, tagging_world):
    conn, cur = tagging_world
    _place(cur, conn, 2)

    html = _home(client)

    assert "Continue Tagging" in html
    assert SEGMENT_LINK in html
    assert f"2 of {TUNE_COUNT} tunes placed" in html


def test_fully_tagged_recording_drops_off(client, tagging_world):
    conn, cur = tagging_world
    _place(cur, conn, TUNE_COUNT)

    html = _home(client)

    assert SEGMENT_LINK not in html
    assert "Continue Tagging" not in html


def test_untouched_recording_never_appears(client, tagging_world):
    """The card continues work; it does not advertise work never started —
    same rule as the logging list, which needs an edit of yours to show."""
    html = _home(client)

    assert SEGMENT_LINK not in html


def test_someone_elses_marks_are_not_my_unfinished_work(client, tagging_world):
    conn, cur = tagging_world
    _place(cur, conn, 2, user_id=CT_OTHER_USER)

    html = _home(client)

    assert SEGMENT_LINK not in html


def test_revoked_grant_removes_the_card(client, tagging_world):
    """Placed marks are not a standing permission — the card links into the
    tool, and the tool would refuse."""
    conn, cur = tagging_world
    _place(cur, conn, 2)
    cur.execute(
        "UPDATE session_person SET can_manage_recordings = FALSE WHERE session_id = %s AND person_id = %s",
        (CT_SESSION, CT_PERSON),
    )
    conn.commit()

    html = _home(client)

    assert SEGMENT_LINK not in html
