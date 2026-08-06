"""Playback for the session-instance page — the read side of the segmenter.

GET /api/session-instances/<id>/audio is what puts a play button on a tune row.
It answers a much narrower question than the segmenter's payload does ("where
does each tune sit in the audio?"), and these tests pin the three decisions that
are easy to get wrong later:

1. **A recording with no marks is not playable.** The endpoint selects on having
   segments, so the page never renders a play button that would do nothing.
2. **The proxy, never the master.** This is listening, not corpus work; handing
   a phone the full-fidelity file would stall every seek.
3. **The gate is the segmenter's gate.** Anyone who may PLACE these marks may
   hear them. Nothing looser (it's still per session), nothing tighter.
"""

from unittest.mock import patch

import pytest

from auth import User

PB_SESSION = 95500
PB_INSTANCE = 95501
PB_PERSON = 95502
PB_USER = 95503
PB_RECORDING = 95504
PB_BARE_RECORDING = 95505  # ready, but nobody ever timestamped it
PB_TUNE_BASE = 95510


@pytest.fixture
def playback_world(db_setup):
    """One night: three logged tunes, two recordings, marks on only one of them.

    The marked recording carries an EXPLICIT end on the first tune with a gap
    after it (chat between tunes) and an IMPLICIT end on the second, so both end
    kinds are exercised by whatever reads this.
    """
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Playback050', 'playback050-test')",
        (PB_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')",
        (PB_INSTANCE, PB_SESSION),
    )
    cur.execute(
        "INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'Play', 'Backer')",
        (PB_PERSON,),
    )
    cur.execute(
        "INSERT INTO user_account (user_id, person_id, username, user_email, hashed_password, "
        "is_system_admin, is_active, email_verified) "
        "VALUES (%s, %s, 'playback050', 'playback050@example.com', 'x', FALSE, TRUE, TRUE)",
        (PB_USER, PB_PERSON),
    )
    cur.execute(
        "INSERT INTO session_person (session_id, person_id, is_admin, can_manage_recordings) "
        "VALUES (%s, %s, TRUE, TRUE)",
        (PB_SESSION, PB_PERSON),
    )
    for i in range(3):
        cur.execute(
            "INSERT INTO session_instance_tune (session_instance_tune_id, session_instance_id, name, "
            "order_position, record_type) VALUES (%s, %s, %s, %s, 'tune')",
            (PB_TUNE_BASE + i, PB_INSTANCE, f"Playback Tune {i}", f"a{i}"),
        )
    # The marked one: a proxy exists, so playback must choose it over the master.
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, label, storage_key, stream_key, "
        "stream_mime_type, duration_ms, is_clock_anchor, status) "
        "VALUES (%s, %s, 'Marked', 'recordings/pb/master.wav', 'recordings/pb/proxy.m4a', "
        "'audio/mp4', 600000, TRUE, 'ready')",
        (PB_RECORDING, PB_INSTANCE),
    )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, label, storage_key, duration_ms, "
        "is_clock_anchor, status) VALUES (%s, %s, 'Unmarked', 'recordings/pb/other.wav', 600000, "
        "FALSE, 'ready')",
        (PB_BARE_RECORDING, PB_INSTANCE),
    )
    cur.execute(
        "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms, end_ms) "
        "VALUES (%s, %s, 10000, 130000), (%s, %s, 150000, NULL)",
        (PB_RECORDING, PB_TUNE_BASE, PB_RECORDING, PB_TUNE_BASE + 1),
    )
    conn.commit()
    yield conn, cur
    cur.execute("DELETE FROM recording_tune_segment WHERE recording_id IN (%s, %s)",
                (PB_RECORDING, PB_BARE_RECORDING))
    cur.execute("DELETE FROM recording_tune_segment_history WHERE recording_id IN (%s, %s)",
                (PB_RECORDING, PB_BARE_RECORDING))
    cur.execute("DELETE FROM recording_history WHERE recording_id IN (%s, %s)",
                (PB_RECORDING, PB_BARE_RECORDING))
    cur.execute("DELETE FROM recording WHERE recording_id IN (%s, %s)",
                (PB_RECORDING, PB_BARE_RECORDING))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (PB_INSTANCE,))
    cur.execute("DELETE FROM session_person_history WHERE person_id = %s", (PB_PERSON,))
    cur.execute("DELETE FROM session_person WHERE person_id = %s", (PB_PERSON,))
    cur.execute("DELETE FROM user_account WHERE user_id = %s", (PB_USER,))
    cur.execute("DELETE FROM person WHERE person_id = %s", (PB_PERSON,))
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (PB_SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (PB_SESSION,))
    conn.commit()
    conn.close()


class as_the_grantee:
    """Sign in as the (non-system-admin) session admin who holds the grant."""

    def __init__(self, client):
        self.client = client

    def __enter__(self):
        self.patcher = patch("auth.User.get_by_id")
        self.patcher.start().return_value = User(
            user_id=PB_USER, person_id=PB_PERSON, username="playback050",
            email="playback050@example.com", is_system_admin=False,
            first_name="Play", last_name="Backer",
        )
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(PB_USER)
            sess["_fresh"] = True
            sess["is_system_admin"] = False
        return self

    def __exit__(self, *exc):
        self.patcher.stop()
        with self.client.session_transaction() as sess:
            sess.clear()


def _fetch(client, instance_id=PB_INSTANCE):
    """GET the audio payload with S3 presigning stubbed (no bucket in tests)."""
    with patch("recording.generate_presigned_url", side_effect=lambda k, **kw: f"https://s3.test/{k}?sig=x"):
        return client.get(f"/api/session-instances/{instance_id}/audio")


# --------------------------------------------------------------------------- #
# what comes back
# --------------------------------------------------------------------------- #


def test_returns_the_marked_recording_and_its_segments(client, playback_world):
    with as_the_grantee(client):
        resp = _fetch(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["recording"]["recording_id"] == PB_RECORDING
    assert data["recording"]["duration_ms"] == 600000
    assert [(s["session_instance_tune_id"], s["start_ms"], s["end_ms"]) for s in data["segments"]] == [
        (PB_TUNE_BASE, 10000, 130000),
        (PB_TUNE_BASE + 1, 150000, None),
    ]


def test_an_implicit_end_stays_null_on_the_wire(client, playback_world):
    """Resolution happens in the client, with the same shared function the
    segmenter uses. Resolving it here would fork the two."""
    with as_the_grantee(client):
        data = _fetch(client).get_json()
    assert data["segments"][1]["end_ms"] is None


def test_playback_gets_the_proxy_not_the_master(client, playback_world):
    """32kbps mono is indistinguishable for 'what was that tune?' and a tenth the
    bytes. The master stays behind the segmenter, where fidelity is the point."""
    with as_the_grantee(client):
        rec = _fetch(client).get_json()["recording"]
    assert "proxy.m4a" in rec["audio_url"]
    assert "master.wav" not in rec["audio_url"]
    assert rec["is_proxy"] is True


def test_the_most_segmented_recording_wins(client, playback_world):
    """Two ready recordings on the night; only one was ever worked on."""
    conn, cur = playback_world
    with as_the_grantee(client):
        assert _fetch(client).get_json()["recording"]["recording_id"] == PB_RECORDING
    # Give the other one MORE marks and it takes over.
    cur.execute(
        "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms) "
        "VALUES (%s, %s, 1000), (%s, %s, 2000), (%s, %s, 3000)",
        (PB_BARE_RECORDING, PB_TUNE_BASE, PB_BARE_RECORDING, PB_TUNE_BASE + 1,
         PB_BARE_RECORDING, PB_TUNE_BASE + 2),
    )
    conn.commit()
    with as_the_grantee(client):
        assert _fetch(client).get_json()["recording"]["recording_id"] == PB_BARE_RECORDING


# --------------------------------------------------------------------------- #
# when there is nothing to play
# --------------------------------------------------------------------------- #


def test_a_recording_with_no_marks_is_not_playable(client, playback_world):
    """An untimestamped recording would give the page play buttons with nowhere
    to jump to, so it is filtered out at selection rather than after."""
    conn, cur = playback_world
    cur.execute("DELETE FROM recording_tune_segment WHERE recording_id = %s", (PB_RECORDING,))
    conn.commit()
    with as_the_grantee(client):
        data = _fetch(client).get_json()
    assert data["success"] is True  # not an error — most nights have no audio
    assert data["recording"] is None
    assert data["segments"] == []


def test_a_recording_still_ingesting_is_not_offered(client, playback_world):
    """status != 'ready' means the proxy and the real duration aren't there yet."""
    conn, cur = playback_world
    cur.execute("UPDATE recording SET status = 'processing' WHERE recording_id = %s", (PB_RECORDING,))
    conn.commit()
    with as_the_grantee(client):
        assert _fetch(client).get_json()["recording"] is None


def test_a_tune_deleted_from_the_log_drops_out(client, playback_world):
    """The mark survives in the DB (segments are corpus data), but a row that
    isn't on screen can't be played from."""
    conn, cur = playback_world
    cur.execute("UPDATE session_instance_tune SET deleted = TRUE WHERE session_instance_tune_id = %s",
                (PB_TUNE_BASE,))
    conn.commit()
    with as_the_grantee(client):
        segments = _fetch(client).get_json()["segments"]
    assert [s["session_instance_tune_id"] for s in segments] == [PB_TUNE_BASE + 1]


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #


def test_signed_out_is_refused(client, playback_world):
    """Unlike the tune log itself, the audio is not public."""
    assert client.get(f"/api/session-instances/{PB_INSTANCE}/audio").status_code == 401


def test_it_takes_the_same_grant_as_marking(client, playback_world):
    """Listening is gated exactly like placing the marks — no looser, no tighter."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE session_person SET can_manage_recordings = FALSE WHERE session_id = %s",
                (PB_SESSION,))
    conn.commit()
    with as_the_grantee(client):
        assert _fetch(client).status_code == 403
    cur.execute("UPDATE session_person SET can_manage_recordings = TRUE WHERE session_id = %s",
                (PB_SESSION,))
    conn.commit()
    conn.close()
    with as_the_grantee(client):
        assert _fetch(client).status_code == 200
