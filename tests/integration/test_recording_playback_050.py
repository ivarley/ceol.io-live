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


def test_playback_opens_on_the_proxy_with_the_master_behind_it(client, playback_world):
    """Order is the contract: the page plays audio_sources[0]. The proxy leads
    because 32kbps mono is indistinguishable for 'what was that tune?' at a
    fraction of the bytes; the master rides along as the HD option."""
    with as_the_grantee(client):
        rec = _fetch(client).get_json()["recording"]
    assert [s["id"] for s in rec["audio_sources"]] == ["proxy", "master"]
    assert "proxy.m4a" in rec["audio_sources"][0]["url"]
    assert "master.wav" in rec["audio_sources"][1]["url"]


def test_both_encodes_are_signed_in_one_payload(client, playback_world):
    """So switching to HD keeps the listener's place instead of stalling on a
    round trip mid-tune. Presigning is local HMAC — the second URL is free."""
    with as_the_grantee(client):
        rec = _fetch(client).get_json()["recording"]
    assert all(s["url"] for s in rec["audio_sources"])


def test_sizes_ride_along_so_hd_is_an_informed_choice(client, playback_world):
    """The size is the only honest basis a listener has for deciding whether HD
    is a good idea on the connection they're on, so the button can show it."""
    conn, cur = playback_world
    cur.execute(
        "UPDATE recording SET file_size_bytes = 348303266, stream_size_bytes = 44716235 "
        "WHERE recording_id = %s",
        (PB_RECORDING,),
    )
    conn.commit()
    with as_the_grantee(client):
        sources = _fetch(client).get_json()["recording"]["audio_sources"]
    assert {s["id"]: s["size_bytes"] for s in sources} == {
        "proxy": 44716235,
        "master": 348303266,
    }


def test_no_proxy_means_the_master_is_the_only_source(client, playback_world):
    """An ingest predating schema/051, or a transcode that failed. The master is
    all there is, and the page must not offer an 'HD' switch to the same file."""
    conn, cur = playback_world
    cur.execute(
        "UPDATE recording SET stream_key = NULL, stream_mime_type = NULL WHERE recording_id = %s",
        (PB_RECORDING,),
    )
    conn.commit()
    with as_the_grantee(client):
        sources = _fetch(client).get_json()["recording"]["audio_sources"]
    assert [s["id"] for s in sources] == ["master"]


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
# downloading one tune
# --------------------------------------------------------------------------- #


def _dl(client, sit_id, recording_id=PB_RECORDING, source=None):
    """GET the download with S3 presigning stubbed.

    `source` lets a test hand ffmpeg a LOCAL path instead of a URL — ffmpeg
    doesn't care which it gets, so the cut can be exercised for real without
    touching the network.
    """
    url = source or "https://s3.test/master.wav"
    with patch("recording.generate_presigned_url", return_value=url):
        return client.get(f"/api/recordings/{recording_id}/segments/{sit_id}/download")


def test_download_cuts_the_tune_out_for_real(client, playback_world, tmp_path):
    """End to end through ffmpeg: a 4-minute tone in, one tune's worth out.

    The segment is 10s->130s, so the cut must be ~120s — not the whole file.
    """
    import subprocess

    from recording import _ffmpeg_exe, probe_audio

    src = tmp_path / "master.wav"
    subprocess.run(
        [_ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:sample_rate=22050:duration=240", str(src)],
        check=True,
    )
    with as_the_grantee(client):
        resp = _dl(client, PB_TUNE_BASE, source=str(src))
    assert resp.status_code == 200

    out = tmp_path / "out.wav"
    out.write_bytes(resp.data)
    # ~120s out of a 240s source: proof it cut rather than passing the file through.
    assert abs(probe_audio(str(out))["duration_ms"] - 120000) < 1500


def test_download_uses_the_resolved_end_for_an_implicit_segment(client, playback_world):
    """Tune 2 has end_ms NULL, so it must be cut to where playback would stop —
    the recording's end (600000), since nothing is placed after it."""
    captured = {}

    def fake_slice(source, start_ms, end_ms, dest_path, **kw):
        captured.update(start=start_ms, end=end_ms)
        open(dest_path, "wb").write(b"RIFFfake")
        return dest_path

    with as_the_grantee(client), patch("recording.slice_segment", side_effect=fake_slice):
        resp = _dl(client, PB_TUNE_BASE + 1)
    assert resp.status_code == 200
    assert captured == {"start": 150000, "end": 600000}


def test_download_is_named_for_the_tune_and_the_night(client, playback_world):
    with as_the_grantee(client), patch(
        "recording.slice_segment",
        side_effect=lambda s, a, b, dest, **kw: (open(dest, "wb").write(b"x"), dest)[1],
    ):
        resp = _dl(client, PB_TUNE_BASE)
    disposition = resp.headers["Content-Disposition"]
    assert "attachment" in disposition
    assert "Playback Tune 0 (2026-07-01).wav" in disposition


def test_download_cuts_from_the_master_not_the_proxy(client, playback_world):
    """A file someone keeps shouldn't be the 32kbps mono playback encode."""
    with as_the_grantee(client), patch(
        "recording.generate_presigned_url", return_value="https://s3.test/x.wav"
    ) as presign, patch(
        "recording.slice_segment",
        side_effect=lambda s, a, b, dest, **kw: (open(dest, "wb").write(b"x"), dest)[1],
    ):
        client.get(f"/api/recordings/{PB_RECORDING}/segments/{PB_TUNE_BASE}/download")
    assert presign.call_args[0][0] == "recordings/pb/master.wav"


def test_download_404s_for_a_tune_with_no_segment(client, playback_world):
    with as_the_grantee(client):
        assert _dl(client, PB_TUNE_BASE + 2).status_code == 404


def test_download_takes_the_same_grant_as_everything_else(client, playback_world):
    assert client.get(
        f"/api/recordings/{PB_RECORDING}/segments/{PB_TUNE_BASE}/download"
    ).status_code == 401


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
