"""Ingest that survives nobody watching (schema/054).

Uploading starts a thread on the web dyno, which is fast and usually enough. It
is not a guarantee: the thread is a daemon thread in a gunicorn worker, and a
deploy, an OOM, or a `max_requests` recycle takes it mid-transcode. The row then
says 'processing' while nothing is processing it.

Four mechanisms make that recoverable, and this is what pins them down:

1. **The claim.** One conditional UPDATE, so the web thread and the sweeper
   cannot both start the same transcode however their timing lines up.
2. **The heartbeat.** Liveness is stated every 30s rather than inferred from when
   a stage last changed, which is what lets "presumed dead" be 90 seconds instead
   of two hours.
3. **The budget.** A file ffmpeg genuinely cannot read fails visibly instead of
   being retried for ever.
4. **The sweep.** What actually re-runs an abandoned ingest, and what keeps two
   gunicorn workers from each starting a different transcode at the same moment.

The happy path through real ffmpeg lives in test_recording_ingest_050.
"""

import pytest

RES_SESSION = 95500
RES_INSTANCE = 95501
RES_RECORDING = 95502


@pytest.fixture
def committed_recording(db_setup):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Resume054', 'resume054-test')",
        (RES_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')",
        (RES_INSTANCE, RES_SESSION),
    )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, storage_key, duration_ms, "
        "is_clock_anchor, status, status_detail) "
        "VALUES (%s, %s, 'recordings/resume054/night.mp3', 1, TRUE, 'queued', 'Queued')",
        (RES_RECORDING, RES_INSTANCE),
    )
    conn.commit()
    yield RES_RECORDING
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (RES_RECORDING,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (RES_RECORDING,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (RES_INSTANCE,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (RES_SESSION,))
    conn.commit()
    conn.close()


def _set(**columns):
    """Put the row into a given state, committed."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    assignments = ", ".join(f"{k} = %s" for k in columns)
    cur.execute(
        f"UPDATE recording SET {assignments} WHERE recording_id = %s",
        (*columns.values(), RES_RECORDING),
    )
    conn.commit()
    conn.close()


def _beat_ago(seconds):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE recording SET ingest_heartbeat_at = (NOW() AT TIME ZONE 'UTC') "
        "- make_interval(secs => %s) WHERE recording_id = %s",
        (seconds, RES_RECORDING),
    )
    conn.commit()
    conn.close()


def _row(db_cursor, *columns):
    db_cursor.execute(
        f"SELECT {', '.join(columns)} FROM recording WHERE recording_id = %s", (RES_RECORDING,)
    )
    return db_cursor.fetchone()


# --------------------------------------------------------------------------- #
# 1. the claim
# --------------------------------------------------------------------------- #


def test_only_one_claimant_wins(committed_recording):
    """The whole point: two processes, one three-hour transcode."""
    from services.recording_ingest import claim_recording_for_ingest

    first = claim_recording_for_ingest(RES_RECORDING)
    second = claim_recording_for_ingest(RES_RECORDING)

    assert first is True
    assert second is False


def test_claiming_marks_it_processing_and_spends_an_attempt(committed_recording, db_cursor):
    from services.recording_ingest import claim_recording_for_ingest

    claim_recording_for_ingest(RES_RECORDING)
    status, attempts, heartbeat = _row(db_cursor, "status", "ingest_attempts", "ingest_heartbeat_at")
    assert status == "processing"
    assert attempts == 1
    assert heartbeat is not None


def test_a_run_that_stopped_beating_can_be_taken_over(committed_recording):
    """A dyno that slept mid-transcode leaves exactly this state."""
    from services.recording_ingest import HEARTBEAT_STALE_SECONDS, claim_recording_for_ingest

    _set(status="processing")
    _beat_ago(HEARTBEAT_STALE_SECONDS + 30)

    assert claim_recording_for_ingest(RES_RECORDING) is True


def test_a_live_run_is_left_alone(committed_recording):
    from services.recording_ingest import HEARTBEAT_STALE_SECONDS, claim_recording_for_ingest

    _set(status="processing")
    _beat_ago(HEARTBEAT_STALE_SECONDS - 30)

    assert claim_recording_for_ingest(RES_RECORDING) is False


def test_a_finished_recording_is_never_reclaimed(committed_recording):
    """Otherwise the sweeper would redo work every ten minutes for ever."""
    from services.recording_ingest import claim_recording_for_ingest

    _set(status="ready", ingest_heartbeat_at=None)
    assert claim_recording_for_ingest(RES_RECORDING) is False


def test_a_failed_recording_is_not_picked_up_automatically(committed_recording):
    """Failure means a human should look. Retry is how it comes back."""
    from services.recording_ingest import claim_recording_for_ingest

    _set(status="failed", status_detail="Proxy — ffmpeg fell over")
    assert claim_recording_for_ingest(RES_RECORDING) is False


def test_ingest_returns_immediately_when_it_cannot_claim(committed_recording, monkeypatch):
    """The guard is inside ingest_recording, not just at its callers."""
    import recording as rec
    from services.recording_ingest import claim_recording_for_ingest, ingest_recording

    touched = []
    monkeypatch.setattr(rec, "check_configured", lambda: None)
    monkeypatch.setattr(rec, "download_recording", lambda *a: touched.append(a))

    claim_recording_for_ingest(RES_RECORDING)   # somebody else holds it, freshly
    ingest_recording(RES_RECORDING)

    assert not touched, "ingest did work on a recording it did not own"


# --------------------------------------------------------------------------- #
# 2. what the sweeper sees
# --------------------------------------------------------------------------- #


def test_a_queued_recording_is_pending(committed_recording):
    from services.recording_ingest import find_pending_recordings

    assert RES_RECORDING in [r["recording_id"] for r in find_pending_recordings(limit=50)]


def test_a_live_run_is_not_pending(committed_recording):
    from services.recording_ingest import find_pending_recordings

    _set(status="processing")
    _beat_ago(10)
    assert RES_RECORDING not in [r["recording_id"] for r in find_pending_recordings(limit=50)]


def test_an_abandoned_run_is_pending(committed_recording):
    from services.recording_ingest import HEARTBEAT_STALE_SECONDS, find_pending_recordings

    _set(status="processing")
    _beat_ago(HEARTBEAT_STALE_SECONDS + 60)
    assert RES_RECORDING in [r["recording_id"] for r in find_pending_recordings(limit=50)]


def test_a_recording_out_of_attempts_is_not_pending(committed_recording):
    from services.recording_ingest import MAX_INGEST_ATTEMPTS, find_pending_recordings

    _set(status="processing", ingest_attempts=MAX_INGEST_ATTEMPTS)
    _beat_ago(9999)
    assert RES_RECORDING not in [r["recording_id"] for r in find_pending_recordings(limit=50)]


# --------------------------------------------------------------------------- #
# 3. the budget
# --------------------------------------------------------------------------- #


def test_an_exhausted_recording_is_marked_failed_rather_than_left_busy(committed_recording, db_cursor):
    """'processing' with nothing processing it is the state this whole mechanism
    exists to remove — so when the retries run out it has to say so."""
    from services.recording_ingest import MAX_INGEST_ATTEMPTS, abandon_exhausted_recordings

    _set(status="processing", ingest_attempts=MAX_INGEST_ATTEMPTS)
    _beat_ago(9999)

    assert RES_RECORDING in abandon_exhausted_recordings()
    status, detail = _row(db_cursor, "status", "status_detail")
    assert status == "failed"
    assert str(MAX_INGEST_ATTEMPTS) in detail


def test_a_live_run_at_the_cap_is_not_abandoned_mid_flight(committed_recording, db_cursor):
    """It spent its last attempt and is still going — killing it here would throw
    away a transcode that is about to finish."""
    from services.recording_ingest import MAX_INGEST_ATTEMPTS, abandon_exhausted_recordings

    _set(status="processing", ingest_attempts=MAX_INGEST_ATTEMPTS)
    _beat_ago(5)

    assert abandon_exhausted_recordings() == []
    assert _row(db_cursor, "status")[0] == "processing"


def test_finishing_clears_the_budget(committed_recording, db_cursor, monkeypatch, tmp_path):
    """A recording that took two goes shouldn't carry that forward for ever."""
    import subprocess

    import recording as rec
    from services.recording_ingest import ingest_recording

    try:
        ffmpeg = rec._ffmpeg_exe()
    except RuntimeError:
        pytest.skip("no ffmpeg available")

    source = str(tmp_path / "tiny.mp3")
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", source],
        check=True, capture_output=True,
    )

    import shutil

    monkeypatch.setattr(rec, "check_configured", lambda: None)
    monkeypatch.setattr(rec, "download_recording", lambda key, dest: shutil.copyfile(source, dest))
    monkeypatch.setattr(rec, "upload_recording", lambda path, key, mime_type=None: key)

    _set(status="queued", ingest_attempts=2)
    ingest_recording(RES_RECORDING)

    status, attempts, heartbeat = _row(db_cursor, "status", "ingest_attempts", "ingest_heartbeat_at")
    assert status == "ready"
    assert attempts == 0
    # Nothing is running, so nothing should be claiming to be alive.
    assert heartbeat is None


# --------------------------------------------------------------------------- #
# 5. the sweep
# --------------------------------------------------------------------------- #
# It used to be a cron job that was declared and never created. It now runs in
# the web service from gunicorn's post_fork, which is the same code path either
# way -- sweep_once() is what the manual jobs/ script calls too.


def _no_real_ingest(monkeypatch):
    """Record which recordings the sweep hands to ingest, without transcoding.

    Also pretends object storage is configured. It is not in the test
    environment, and sweep_once refuses to do anything without it -- correctly,
    which is what test_the_sweep_does_nothing_without_object_storage covers.
    """
    import recording as rec
    import services.recording_ingest as ri

    monkeypatch.setattr(rec, "check_configured", lambda: None)
    handed = []
    monkeypatch.setattr(ri, "ingest_recording", lambda rid, user_id=None: handed.append(rid))
    return handed


def test_the_sweep_finishes_an_abandoned_run(committed_recording, monkeypatch):
    import services.recording_ingest as ri

    handed = _no_real_ingest(monkeypatch)
    _set(status="processing")
    _beat_ago(ri.HEARTBEAT_STALE_SECONDS + 30)

    assert ri.sweep_once() == 1
    assert handed == [RES_RECORDING]


def test_the_sweep_takes_a_queued_recording(committed_recording, monkeypatch):
    import services.recording_ingest as ri

    handed = _no_real_ingest(monkeypatch)
    assert ri.sweep_once() == 1
    assert handed == [RES_RECORDING]


def test_the_sweep_leaves_a_live_run_alone(committed_recording, monkeypatch):
    """The point of _ingest_in_flight_anywhere.

    Not about claiming the same row -- find_pending_recordings already excludes
    anything beating. This is what stops the second gunicorn worker starting a
    transcode of a DIFFERENT recording while one is already running, which is how
    two ffmpegs end up sharing a 512MB dyno.
    """
    import services.recording_ingest as ri

    handed = _no_real_ingest(monkeypatch)
    _set(status="processing")
    _beat_ago(5)

    assert ri.sweep_once() == 0
    assert handed == []


def test_the_sweep_does_nothing_without_object_storage(committed_recording, monkeypatch, db_cursor):
    """An unset AWS_* must not burn the retry budget of a good recording.

    Every claim would spend an attempt on a download that cannot work, and three
    sweeps would exhaust a perfectly readable file for a reason that has nothing
    to do with it.
    """
    import recording as rec
    import services.recording_ingest as ri

    handed = _no_real_ingest(monkeypatch)
    monkeypatch.setattr(rec, "check_configured", lambda: "object storage is not configured (test)")  # noqa: E501

    assert ri.sweep_once() == 0
    assert handed == []
    assert _row(db_cursor, "status", "ingest_attempts") == ("queued", 0)


def test_the_sweep_abandons_an_exhausted_recording_before_looking_for_work(
    committed_recording, monkeypatch, db_cursor
):
    import services.recording_ingest as ri

    handed = _no_real_ingest(monkeypatch)
    _set(status="processing", ingest_attempts=ri.MAX_INGEST_ATTEMPTS)
    _beat_ago(ri.HEARTBEAT_STALE_SECONDS + 30)

    assert ri.sweep_once() == 0
    assert handed == []
    assert _row(db_cursor, "status")[0] == "failed"


def test_one_bad_recording_does_not_stop_the_batch(committed_recording, monkeypatch):
    """ingest_recording records its own failure; the sweep only has to continue."""
    import services.recording_ingest as ri

    _no_real_ingest(monkeypatch)

    def _explode(rid, user_id=None):
        raise RuntimeError("ffmpeg fell over")

    monkeypatch.setattr(ri, "ingest_recording", _explode)
    assert ri.sweep_once() == 0  # raised, so not counted -- and did not propagate


def test_starting_the_sweeper_twice_starts_one_thread(monkeypatch):
    """post_fork runs per worker, but nothing should start two in one process."""
    import services.recording_ingest as ri

    monkeypatch.setattr(ri, "_sweeper_running", False)
    started = []
    monkeypatch.setattr(ri, "_sweep_loop", lambda: started.append(1))

    first = ri.start_sweeper()
    second = ri.start_sweeper()

    assert first is not None
    assert second is None, "the second call should be a no-op, not a second sweeper"
    first.join(timeout=5)
