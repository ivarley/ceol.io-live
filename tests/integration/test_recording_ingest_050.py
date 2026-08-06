"""Recording ingest — the pipeline that runs after an upload (spec 050).

These tests really run ffmpeg over a real (tiny) audio file, because the parts
worth pinning down are exactly the parts a mock would paper over: that the
waveform comes out the right length, that the duration on the row stops being
the browser's guess, that the proxy is uploaded under a key derived from the
master's rather than over the top of it, and that a failure lands somewhere the
operator can read it.

Only S3 is stubbed — swapped for a dict and a local file copy.

They also cover the ffprobe-less path, which is the one that matters in
production: Render's Python runtime has no apt step, so the server gets ffmpeg
from a wheel (imageio-ffmpeg) that ships no ffprobe. Locally, where ffprobe
exists, that path would otherwise never be exercised at all.
"""

import os
import shutil
import subprocess

import pytest

ING_SESSION = 95300
ING_INSTANCE = 95301


def _ffmpeg_or_skip():
    import recording as rec

    try:
        return rec._ffmpeg_exe()
    except RuntimeError:
        pytest.skip("no ffmpeg available")


@pytest.fixture
def source_audio(tmp_path):
    """Six seconds of tone with a silent gap in the middle.

    The gap is the point: a flat envelope would pass a "peaks are non-empty"
    assertion while being useless to a human, and the whole reason the envelope
    is RMS in fitted dB is so quiet stretches read as quiet.
    """
    ffmpeg = _ffmpeg_or_skip()
    path = str(tmp_path / "night.mp3")
    subprocess.run(
        [
            ffmpeg, "-v", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=2",
            "-f", "lavfi", "-i", "sine=frequency=660:duration=2",
            "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
            "-ar", "44100", "-ac", "2", "-b:a", "128k",
            path,
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def committed_recording(db_setup, source_audio):
    """A recording row in the state POST /api/recordings leaves it in: uploaded,
    'processing', duration a guess, no waveform."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Ingest050', 'ingest050-test')",
        (ING_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-05-07')",
        (ING_INSTANCE, ING_SESSION),
    )
    cur.execute(
        """
        INSERT INTO recording (session_instance_id, label, storage_key, mime_type, duration_ms,
                               is_clock_anchor, status, status_detail)
        VALUES (%s, 'Ingest050 night', 'recordings/deadbeef/night.mp3', 'audio/mpeg', 99000, TRUE,
                'processing', 'Queued')
        RETURNING recording_id
        """,
        (ING_INSTANCE,),
    )
    recording_id = cur.fetchone()[0]
    conn.commit()
    yield recording_id
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (recording_id,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (recording_id,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (ING_INSTANCE,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (ING_SESSION,))
    conn.commit()
    conn.close()


@pytest.fixture
def fake_bucket(monkeypatch, source_audio):
    """S3 as a dict: downloads hand back the fixture file, uploads are recorded."""
    import recording as rec

    uploaded = {}

    def _download(storage_key, dest_path):
        shutil.copyfile(source_audio, dest_path)
        return dest_path

    def _upload(file_path, storage_key, mime_type="audio/mp4"):
        uploaded[storage_key] = {"size": os.path.getsize(file_path), "mime_type": mime_type}
        return storage_key

    monkeypatch.setattr(rec, "check_configured", lambda: None)
    monkeypatch.setattr(rec, "download_recording", _download)
    monkeypatch.setattr(rec, "upload_recording", _upload)
    return uploaded


def _row(db_cursor, recording_id):
    db_cursor.execute(
        "SELECT status, status_detail, duration_ms, sample_rate, channels, peaks, peaks_hz, "
        "       stream_key, stream_mime_type, stream_size_bytes, file_size_bytes "
        "FROM recording WHERE recording_id = %s",
        (recording_id,),
    )
    keys = ("status", "status_detail", "duration_ms", "sample_rate", "channels", "peaks", "peaks_hz",
            "stream_key", "stream_mime_type", "stream_size_bytes", "file_size_bytes")
    return dict(zip(keys, db_cursor.fetchone()))


def test_ingest_fills_in_everything_the_segmenter_needs(committed_recording, fake_bucket, db_cursor):
    import base64

    from services.recording_ingest import ingest_recording

    ingest_recording(committed_recording)
    row = _row(db_cursor, committed_recording)

    assert row["status"] == "ready"
    assert row["status_detail"] is None

    # The browser's 99000ms guess is gone, replaced by the container's own.
    assert 5800 <= row["duration_ms"] <= 6300
    assert row["sample_rate"] == 44100
    assert row["channels"] == 2

    # One bucket per 1/peaks_hz of audio, so the envelope's length IS the duration.
    peaks = base64.b64decode(row["peaks"])
    expected = round(row["duration_ms"] / 1000 * float(row["peaks_hz"]))
    assert abs(len(peaks) - expected) <= 2

    # The silent middle two seconds have to read as quieter than the tone either
    # side, otherwise the operator is looking at a solid block.
    third = len(peaks) // 3
    assert max(peaks[third:2 * third]) < min(peaks[:third // 2])


def test_ingest_uploads_the_proxy_beside_the_master_not_over_it(committed_recording, fake_bucket, db_cursor):
    """Keeping the two keys apart is what stops the training corpus ever being
    cut from a 32kbps mono encode."""
    from services.recording_ingest import ingest_recording

    ingest_recording(committed_recording)
    row = _row(db_cursor, committed_recording)

    assert row["stream_key"] == "recordings/deadbeef/night.mp3.stream.m4a"
    assert row["stream_key"] != "recordings/deadbeef/night.mp3"
    assert list(fake_bucket) == [row["stream_key"]]  # the master is already there; only the proxy is written
    assert row["stream_mime_type"] == "audio/mp4"
    assert row["stream_size_bytes"] == fake_bucket[row["stream_key"]]["size"]
    # file_size_bytes describes the MASTER, measured from what was downloaded.
    assert row["file_size_bytes"] > row["stream_size_bytes"]


def test_ingest_is_repeatable(committed_recording, fake_bucket, db_cursor):
    """Retry is the only recovery the admin page offers, so running twice has to
    land in the same place rather than accumulating proxies."""
    from services.recording_ingest import ingest_recording

    ingest_recording(committed_recording)
    first = _row(db_cursor, committed_recording)
    ingest_recording(committed_recording)
    second = _row(db_cursor, committed_recording)

    assert first == second
    assert len(fake_bucket) == 1


def test_ingest_leaves_a_readable_reason_when_it_fails(committed_recording, monkeypatch, db_cursor):
    import recording as rec
    from services.recording_ingest import ingest_recording

    monkeypatch.setattr(rec, "check_configured", lambda: None)

    def _boom(storage_key, dest_path):
        raise RuntimeError("the bucket said no")

    monkeypatch.setattr(rec, "download_recording", _boom)

    ingest_recording(committed_recording)
    row = _row(db_cursor, committed_recording)

    assert row["status"] == "failed"
    assert "the bucket said no" in row["status_detail"]
    # The row still describes an uploaded file; only the derived parts are absent.
    assert row["peaks"] is None


def test_ingest_records_a_history_row_for_the_metadata_it_writes(committed_recording, fake_bucket, db_cursor):
    from services.recording_ingest import ingest_recording

    ingest_recording(committed_recording)
    db_cursor.execute(
        "SELECT operation FROM recording_history WHERE recording_id = %s", (committed_recording,)
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["UPDATE"]


# --------------------------------------------------------------------------- #
# The server has ffmpeg but no ffprobe
# --------------------------------------------------------------------------- #


def test_probe_agrees_with_ffprobe_when_there_is_no_ffprobe(source_audio, monkeypatch):
    """imageio-ffmpeg ships ffmpeg alone, so on Render probe_audio reads ffmpeg's
    own stream report instead. It has to reach the same answer."""
    import recording as rec

    _ffmpeg_or_skip()
    if not rec._ffprobe_exe():
        pytest.skip("no ffprobe to compare against")

    with_probe = rec.probe_audio(source_audio)
    monkeypatch.setitem(rec._BINARIES, "ffprobe", None)
    without_probe = rec.probe_audio(source_audio)

    assert without_probe["sample_rate"] == with_probe["sample_rate"]
    assert without_probe["channels"] == with_probe["channels"]
    # ffmpeg reports centiseconds, ffprobe microseconds, so they differ in the
    # last few ms on any real file. That is nothing next to a 50ms peaks bucket.
    assert abs(without_probe["duration_ms"] - with_probe["duration_ms"]) <= 20


def test_probe_reads_mono_from_the_layout_name(tmp_path, monkeypatch):
    """ffmpeg names common layouts ("mono", "stereo") rather than counting them,
    which a naive "(\\d+) channels" regex silently reads as None."""
    import recording as rec

    ffmpeg = _ffmpeg_or_skip()
    path = str(tmp_path / "mono.mp3")
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ac", "1", "-ar", "22050", path],
        check=True, capture_output=True,
    )

    monkeypatch.setitem(rec._BINARIES, "ffprobe", None)
    assert rec.probe_audio(path)["channels"] == 1


def test_probe_says_which_file_it_could_not_read(tmp_path, monkeypatch):
    import recording as rec

    _ffmpeg_or_skip()
    path = tmp_path / "not-audio.mp3"
    path.write_text("this is not an audio file")

    monkeypatch.setitem(rec._BINARIES, "ffprobe", None)
    with pytest.raises(ValueError) as excinfo:
        rec.probe_audio(str(path))
    assert "not-audio.mp3" in str(excinfo.value)
