"""In-app recording upload (spec 050).

The upload is three calls with S3 in the middle, and the interesting behaviour is
all in the seams:

1. `POST /api/recordings/upload-url` signs a write to the bucket, so it is fussy
   about what it will sign for.
2. `POST /api/recordings` is the only place that can tell "the upload finished"
   from "the operator closed the tab": it confirms the object exists before it
   writes a row claiming it does.
3. The row then exists for minutes in a state where its duration is a guess and
   its waveform is absent. Everything that reads a recording has to notice.

S3 itself is stubbed throughout — these tests are about the seams, not boto3 —
and so is the ingest thread, which is exercised separately by actually running
ffmpeg (test_recording_ingest_050).
"""

import pytest

UP_SESSION = 95200
UP_INSTANCE = 95201
UP_OTHER_INSTANCE = 95202


@pytest.fixture
def committed_instance(db_setup):
    """A session with one instance, committed — the endpoints open their own
    connections, so a transaction-local fixture would be invisible to them."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Upload050', 'upload050-test')",
        (UP_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-04-09'), (%s, %s, '2026-04-16')",
        (UP_INSTANCE, UP_SESSION, UP_OTHER_INSTANCE, UP_SESSION),
    )
    conn.commit()
    yield
    cur.execute("DELETE FROM recording_history WHERE session_instance_id IN (%s, %s)", (UP_INSTANCE, UP_OTHER_INSTANCE))
    cur.execute("DELETE FROM recording WHERE session_instance_id IN (%s, %s)", (UP_INSTANCE, UP_OTHER_INSTANCE))
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (UP_SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (UP_SESSION,))
    conn.commit()
    conn.close()


@pytest.fixture
def fake_s3(monkeypatch):
    """Stand in for the bucket. `stored` is what head_object will claim to see."""
    import recording as rec

    state = {"stored": {}, "signed": []}

    def _sign(storage_key, mime_type, expiry=3600):
        state["signed"].append((storage_key, mime_type))
        return f"https://bucket.example/{storage_key}?signature=stub"

    monkeypatch.setattr(rec, "check_configured", lambda: None)
    monkeypatch.setattr(rec, "generate_presigned_upload", _sign)
    monkeypatch.setattr(rec, "stored_object_size", lambda key: state["stored"].get(key))
    return state


@pytest.fixture
def no_ingest(monkeypatch):
    """Record ingest kick-offs instead of running them."""
    import services.recording_ingest as ingest

    started = []
    monkeypatch.setattr(ingest, "start_ingest", lambda rid, uid=None: started.append(rid))
    return started


def _upload(client, filename="session.mp3", instance=UP_INSTANCE):
    return client.post(
        "/api/recordings/upload-url",
        json={"session_instance_id": instance, "filename": filename},
    )


def _create(client, fake_s3, **overrides):
    """Sign, pretend the PUT succeeded, then confirm — the whole happy path."""
    signed = _upload(client).get_json()
    fake_s3["stored"][signed["storage_key"]] = 12_345_678
    body = {
        "session_instance_id": UP_INSTANCE,
        "storage_key": signed["storage_key"],
        "duration_ms": 5_400_000,
    }
    body.update(overrides)
    return client.post("/api/recordings", json=body)


# --------------------------------------------------------------------------- #
# 1. signing
# --------------------------------------------------------------------------- #


def test_upload_url_signs_a_key_the_app_minted(client, admin_user, committed_instance, fake_s3):
    with admin_user:
        resp = _upload(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["storage_key"].startswith("recordings/")
    assert body["storage_key"].endswith("session.mp3")
    # The extension decides the type, and the client is told which one to send:
    # Content-Type is signed into the URL, so a mismatch is a failed upload.
    assert body["content_type"] == "audio/mpeg"
    assert fake_s3["signed"] == [(body["storage_key"], "audio/mpeg")]


def test_two_uploads_of_the_same_filename_get_different_keys(client, admin_user, committed_instance, fake_s3):
    with admin_user:
        first = _upload(client).get_json()["storage_key"]
        second = _upload(client).get_json()["storage_key"]
    assert first != second


def test_upload_url_refuses_to_sign_a_non_audio_file(client, admin_user, committed_instance, fake_s3):
    with admin_user:
        resp = _upload(client, filename="notes.pdf")
    assert resp.status_code == 400
    assert not fake_s3["signed"]


def test_upload_url_404s_for_an_unknown_instance(client, admin_user, committed_instance, fake_s3):
    with admin_user:
        resp = _upload(client, instance=987654321)
    assert resp.status_code == 404
    assert not fake_s3["signed"]


def test_upload_url_says_so_when_storage_is_unconfigured(client, admin_user, committed_instance, monkeypatch):
    import recording as rec

    monkeypatch.setattr(rec, "check_configured", lambda: "object storage is not configured (AWS_S3_BUCKET unset)")
    with admin_user:
        resp = _upload(client)
    assert resp.status_code == 503
    assert "AWS_S3_BUCKET" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# 2. confirming the upload
# --------------------------------------------------------------------------- #


def test_create_refuses_a_key_with_nothing_behind_it(client, admin_user, committed_instance, fake_s3, no_ingest):
    """A cancelled PUT must not leave a row pointing at an object that isn't
    there — that surfaces much later as a segmenter page that plays silence."""
    with admin_user:
        signed = _upload(client).get_json()
        # Note: nothing added to fake_s3["stored"].
        resp = client.post(
            "/api/recordings",
            json={"session_instance_id": UP_INSTANCE, "storage_key": signed["storage_key"]},
        )
    assert resp.status_code == 400
    assert "didn't finish" in resp.get_json()["error"]
    assert not no_ingest


def test_create_refuses_a_key_this_app_never_minted(client, admin_user, committed_instance, fake_s3, no_ingest):
    with admin_user:
        resp = client.post(
            "/api/recordings",
            json={"session_instance_id": UP_INSTANCE, "storage_key": "someone-elses/object.mp3"},
        )
    assert resp.status_code == 400
    assert not no_ingest


def test_create_writes_a_processing_row_and_starts_ingest(
    client, admin_user, committed_instance, fake_s3, no_ingest, db_cursor
):
    with admin_user:
        resp = _create(client, fake_s3)

    assert resp.status_code == 201
    body = resp.get_json()
    recording_id = body["recording_id"]
    assert body["status"] == "processing"
    assert no_ingest == [recording_id]

    db_cursor.execute(
        "SELECT status, status_detail, duration_ms, peaks, is_clock_anchor, label, file_size_bytes "
        "FROM recording WHERE recording_id = %s",
        (recording_id,),
    )
    status, detail, duration_ms, peaks, is_anchor, label, size = db_cursor.fetchone()
    assert status == "processing"
    assert detail  # something for the page to show while it waits
    # The browser's guess, carried so the row reads sensibly until ingest
    # replaces it with the container's own duration.
    assert duration_ms == 5_400_000
    assert peaks is None
    # First recording on an instance is the clock anchor whether or not asked for.
    assert is_anchor is True
    # Label defaults to the night it belongs to.
    assert label == "Upload050 2026-04-09"
    assert size == 12_345_678


def test_create_leaves_an_insert_history_row(client, admin_user, committed_instance, fake_s3, no_ingest, db_cursor):
    with admin_user:
        recording_id = _create(client, fake_s3).get_json()["recording_id"]

    db_cursor.execute(
        "SELECT operation FROM recording_history WHERE recording_id = %s", (recording_id,)
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["INSERT"]


def test_only_the_first_recording_on_an_instance_is_the_anchor(
    client, admin_user, committed_instance, fake_s3, no_ingest
):
    with admin_user:
        assert _create(client, fake_s3).get_json()["is_clock_anchor"] is True
        assert _create(client, fake_s3).get_json()["is_clock_anchor"] is False


def test_create_requires_an_offset_on_started_at(client, admin_user, committed_instance, fake_s3, no_ingest):
    """Without an offset the anchor is ambiguous, and being a timezone out
    silently misaligns every absolute timestamp in the export."""
    with admin_user:
        naive = _create(client, fake_s3, started_at="2026-04-09T19:30:00")
        assert naive.status_code == 400
        assert "offset" in naive.get_json()["error"]

        aware = _create(client, fake_s3, started_at="2026-04-09T19:30:00-05:00")
        assert aware.status_code == 201


def test_create_takes_an_explicit_label(client, admin_user, committed_instance, fake_s3, no_ingest, db_cursor):
    with admin_user:
        recording_id = _create(client, fake_s3, label="Back room, second set").get_json()["recording_id"]
    db_cursor.execute("SELECT label FROM recording WHERE recording_id = %s", (recording_id,))
    assert db_cursor.fetchone()[0] == "Back room, second set"


# --------------------------------------------------------------------------- #
# 3. living with a half-built row
# --------------------------------------------------------------------------- #


def test_status_reports_what_ingest_is_doing(client, admin_user, committed_instance, fake_s3, no_ingest):
    with admin_user:
        recording_id = _create(client, fake_s3).get_json()["recording_id"]
        resp = client.get(f"/api/recordings/{recording_id}/status")

    body = resp.get_json()
    assert body["status"] == "processing"
    assert body["has_peaks"] is False
    assert body["has_proxy"] is False
    # Freshly created, so nothing to presume dead yet.
    assert body["stalled"] is False


def test_segments_cannot_be_placed_while_the_duration_is_still_a_guess(
    client, admin_user, committed_instance, fake_s3, no_ingest, db_cursor
):
    db_cursor.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES (95210, 'Upload Reel', 'Reel')"
    )
    db_cursor.execute(
        "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) "
        "VALUES (%s, 95210, 'a0', 'tune') RETURNING session_instance_tune_id",
        (UP_INSTANCE,),
    )
    sit = db_cursor.fetchone()[0]
    db_cursor.connection.commit()

    try:
        with admin_user:
            recording_id = _create(client, fake_s3).get_json()["recording_id"]
            resp = client.put(f"/api/recordings/{recording_id}/segments/{sit}", json={"start_ms": 1000})
        assert resp.status_code == 409
        assert "still being processed" in resp.get_json()["error"]
    finally:
        db_cursor.execute("DELETE FROM session_instance_tune WHERE session_instance_tune_id = %s", (sit,))
        db_cursor.execute("DELETE FROM tune WHERE tune_id = 95210")
        db_cursor.connection.commit()


def test_segmenter_page_sends_a_processing_recording_back_to_the_list(
    client, admin_user, committed_instance, fake_s3, no_ingest
):
    with admin_user:
        recording_id = _create(client, fake_s3).get_json()["recording_id"]
        resp = client.get(f"/admin/recordings/{recording_id}/segment")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/recordings")


def test_reprocess_wont_stack_a_second_run_on_a_live_one(
    client, admin_user, committed_instance, fake_s3, no_ingest
):
    with admin_user:
        recording_id = _create(client, fake_s3).get_json()["recording_id"]
        resp = client.post(f"/api/recordings/{recording_id}/reprocess")

    assert resp.status_code == 409
    assert no_ingest == [recording_id]  # still just the original


def test_reprocess_restarts_a_failed_recording(
    client, admin_user, committed_instance, fake_s3, no_ingest, db_cursor
):
    with admin_user:
        recording_id = _create(client, fake_s3).get_json()["recording_id"]
    db_cursor.execute(
        "UPDATE recording SET status = 'failed', status_detail = 'ffmpeg fell over' WHERE recording_id = %s",
        (recording_id,),
    )
    db_cursor.connection.commit()

    with admin_user:
        resp = client.post(f"/api/recordings/{recording_id}/reprocess")

    assert resp.status_code == 200
    assert no_ingest == [recording_id, recording_id]
    db_cursor.execute("SELECT status FROM recording WHERE recording_id = %s", (recording_id,))
    assert db_cursor.fetchone()[0] == "processing"


# --------------------------------------------------------------------------- #
# 4. the instance picker
# --------------------------------------------------------------------------- #


def test_instance_list_carries_the_tune_count(client, admin_user, committed_instance):
    """The tune count is what decides whether a night is worth uploading: with
    nothing logged there is nothing to segment the audio against."""
    with admin_user:
        resp = client.get(f"/api/admin/sessions/{UP_SESSION}/instances")

    body = resp.get_json()
    assert [i["date"] for i in body["instances"]] == ["2026-04-16", "2026-04-09"]
    assert all(i["tune_count"] == 0 for i in body["instances"])
