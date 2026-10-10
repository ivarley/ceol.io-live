"""
Background work for the listening service (spec 053, "053 files/find-tunes-on-
the-server.md"): an admin queues "find the tunes" for an unlogged night, the
listening service claims it, reports progress (and pauses for live listening),
and posts the tunes it found, which go into the night as the segmenter's own
logging does, with their confidence.

Fixtures are committed in the 952xx block, since the HTTP calls open their own
connections; teardown deletes them.
"""

import pytest

SESSION = 95200
EARLIER = 95201  # a night with a tune logged: what the session knows
NIGHT = 95202  # the night with a recording and nothing logged
REC = 95203
KNOWN, OTHER = 95210, 95211
TOKEN = "test-listen-job-token"


def _build(cur):
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Jobs053', 'jobs053-test')",
        (SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-03-01'), "
        "(%s, %s, '2026-03-08')",
        (EARLIER, SESSION, NIGHT, SESSION),
    )
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'Known Reel', 'Reel'), (%s, 'Other Jig', 'Jig')",
        (KNOWN, OTHER),
    )
    cur.execute(
        "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) "
        "VALUES (%s, %s, 'a0', 'tune')",
        (EARLIER, KNOWN),
    )
    cur.execute(
        "INSERT INTO session_tune (session_id, tune_id, key) VALUES (%s, %s, 'Dmajor')",
        (SESSION, KNOWN),
    )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, storage_key, duration_ms, is_clock_anchor) "
        "VALUES (%s, %s, 'recordings/test/jobs053.m4a', 600000, TRUE)",
        (REC, NIGHT),
    )


def _teardown(cur):
    cur.execute("DELETE FROM listen_job WHERE recording_id = %s", (REC,))
    cur.execute(
        "DELETE FROM recording_tune_segment_history WHERE recording_id = %s", (REC,)
    )
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (REC,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (REC,))
    cur.execute(
        "DELETE FROM session_event WHERE session_instance_id IN (%s, %s)",
        (EARLIER, NIGHT),
    )
    cur.execute(
        "DELETE FROM corroboration WHERE record_id IN (SELECT session_instance_tune_id FROM session_instance_tune "
        "WHERE session_instance_id IN (%s, %s))",
        (EARLIER, NIGHT),
    )
    cur.execute(
        "DELETE FROM session_instance_tune_history WHERE session_instance_tune_id IN "
        "(SELECT session_instance_tune_id FROM session_instance_tune WHERE session_instance_id IN (%s, %s))",
        (EARLIER, NIGHT),
    )
    cur.execute(
        "DELETE FROM session_instance_tune WHERE session_instance_id IN (%s, %s)",
        (EARLIER, NIGHT),
    )
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SESSION,))
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SESSION,))
    cur.execute("DELETE FROM tune WHERE tune_id IN (%s, %s)", (KNOWN, OTHER))


@pytest.fixture
def night(db_setup, monkeypatch):
    from database import get_db_connection

    monkeypatch.setenv("LISTEN_JOB_TOKEN", TOKEN)
    import recording

    monkeypatch.setattr(
        recording, "generate_presigned_url", lambda key, **kw: f"https://signed/{key}"
    )
    conn = get_db_connection()
    cur = conn.cursor()
    _teardown(cur)
    _build(cur)
    conn.commit()
    yield cur
    conn.rollback()
    _teardown(cur)
    conn.commit()
    conn.close()


def _worker(client, path, body=None, token=TOKEN):
    return client.post(
        path, json=body or {}, headers={"Authorization": f"Bearer {token}"}
    )


def test_an_admin_queues_a_job_and_sees_it_waiting(client, admin_user, night):
    with admin_user:
        resp = client.post(f"/api/recordings/{REC}/find-tunes")
        assert resp.status_code == 201, resp.get_json()
        job = resp.get_json()["job"]
        assert (job["status"], job["total_ms"], job["recording_id"]) == (
            "queued",
            600000,
            REC,
        )
        assert job["jobs_ahead"] is not None and job["waited_s"] is not None
        # one at a time for a recording
        assert client.post(f"/api/recordings/{REC}/find-tunes").status_code == 409
        got = client.get(f"/api/recordings/{REC}/find-tunes").get_json()["job"]
        assert got["listen_job_id"] == job["listen_job_id"]
        listed = client.get("/api/admin/listen-jobs").get_json()["jobs"]
        assert any(
            j["listen_job_id"] == job["listen_job_id"]
            and j["session_name"] == "Jobs053"
            for j in listed
        )


def test_a_night_already_logged_is_refused(client, admin_user, night):
    night.execute(
        "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) "
        "VALUES (%s, %s, 'a0', 'tune')",
        (NIGHT, OTHER),
    )
    night.connection.commit()
    with admin_user:
        resp = client.post(f"/api/recordings/{REC}/find-tunes")
        assert resp.status_code == 409, resp.get_json()


def test_only_admins_and_only_the_service(client, authenticated_user, night):
    with authenticated_user:
        assert client.post(f"/api/recordings/{REC}/find-tunes").status_code == 403
        assert client.get("/api/admin/listen-jobs").status_code == 403
        assert client.get("/admin/listen-jobs").status_code == 302
    assert _worker(client, "/api/listen-jobs/claim", token="wrong").status_code == 401
    assert client.post("/api/listen-jobs/claim", json={}).status_code == 401


def test_the_service_claims_reports_pauses_and_puts_the_tunes_in(
    client, admin_user, night
):
    with admin_user:
        job_id = client.post(f"/api/recordings/{REC}/find-tunes").get_json()["job"][
            "listen_job_id"
        ]
    claimed = _worker(client, "/api/listen-jobs/claim", {"worker": "w1"}).get_json()[
        "job"
    ]
    assert claimed["listen_job_id"] == job_id
    assert claimed["session_tunes"] == [KNOWN] and claimed["keys"] == {
        str(KNOWN): "Dmajor"
    }
    assert (
        claimed["audio_url"].startswith("https://signed/")
        and claimed["duration_ms"] == 600000
    )
    # nothing else waiting
    assert (
        _worker(client, "/api/listen-jobs/claim", {"worker": "w2"}).get_json()["job"]
        is None
    )

    body = {
        "worker": "w1",
        "status": "paused",
        "phase": "listening",
        "progress": 0.4,
        "heard_ms": 240000,
        "running_s": 50,
        "paused_s": 12,
    }
    assert (
        _worker(client, f"/api/listen-jobs/{job_id}/progress", body).get_json()["stop"]
        is False
    )
    with admin_user:
        job = client.get(f"/api/recordings/{REC}/find-tunes").get_json()["job"]
        assert (job["status"], job["phase"], job["heard_ms"], job["paused_s"]) == (
            "paused",
            "listening",
            240000,
            12,
        )
    # another worker's report is not this job's
    assert (
        _worker(
            client, f"/api/listen-jobs/{job_id}/progress", {"worker": "w2"}
        ).get_json()["stop"]
        is True
    )

    drafts = [
        {
            "tune_id": OTHER,
            "name": "Other Jig",
            "start_ms": 10000,
            "end_ms": None,
            "p_right": 62,
        },
        {
            "tune_id": KNOWN,
            "name": "Known Reel",
            "start_ms": 100000,
            "end_ms": 200000,
            "p_right": 99,
        },
    ]
    resp = _worker(
        client,
        f"/api/listen-jobs/{job_id}/result",
        {
            "worker": "w1",
            "drafts": drafts,
            "confidence_model": "listen-1",
            "running_s": 300,
            "paused_s": 12,
            "summary": {"tunes": 2, "sets": 1, "need_check": 1},
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["logged"] == 2

    night.execute(
        "SELECT sit.tune_id, sit.source, sit.confidence, sit.confidence_model, sit.created_by_user_id, rts.start_ms "
        "FROM session_instance_tune sit JOIN recording_tune_segment rts "
        "ON rts.session_instance_tune_id = sit.session_instance_tune_id "
        "WHERE sit.session_instance_id = %s AND sit.record_type = 'tune' ORDER BY rts.start_ms",
        (NIGHT,),
    )
    rows = night.fetchall()
    assert [(r[0], r[1], r[2], r[3], r[5]) for r in rows] == [
        (OTHER, "listen", 62, "listen-1", 10000),
        (KNOWN, "listen", 99, "listen-1", 100000),
    ]
    assert all(r[4] == 1 for r in rows)  # as the admin who asked
    with admin_user:
        job = client.get(f"/api/recordings/{REC}/find-tunes").get_json()["job"]
        assert (
            job["status"] == "done"
            and job["result"]["logged"] == 2
            and job["running_s"] == 300
        )


def test_a_cancelled_job_tells_its_worker_to_stop_and_can_be_tried_again(
    client, admin_user, night
):
    with admin_user:
        job_id = client.post(f"/api/recordings/{REC}/find-tunes").get_json()["job"][
            "listen_job_id"
        ]
    _worker(client, "/api/listen-jobs/claim", {"worker": "w1"})
    with admin_user:
        assert (
            client.post(f"/api/listen-jobs/{job_id}/cancel").get_json()["job"]["status"]
            == "cancelled"
        )
    assert (
        _worker(
            client, f"/api/listen-jobs/{job_id}/progress", {"worker": "w1"}
        ).get_json()["stop"]
        is True
    )
    with admin_user:
        again = client.post(f"/api/listen-jobs/{job_id}/retry")
        assert (
            again.status_code == 201 and again.get_json()["job"]["status"] == "queued"
        )


def test_a_worker_gone_silent_loses_the_job_back_to_the_queue(
    client, admin_user, night
):
    with admin_user:
        job_id = client.post(f"/api/recordings/{REC}/find-tunes").get_json()["job"][
            "listen_job_id"
        ]
    _worker(client, "/api/listen-jobs/claim", {"worker": "w1"})
    night.execute(
        "UPDATE listen_job SET heartbeat_at = NOW() - interval '10 minutes' WHERE listen_job_id = %s",
        (job_id,),
    )
    night.connection.commit()
    with admin_user:
        assert (
            client.get(f"/api/recordings/{REC}/find-tunes").get_json()["job"]["status"]
            == "queued"
        )
    # and a failure the service says can be retried goes back too
    _worker(client, "/api/listen-jobs/claim", {"worker": "w2"})
    resp = _worker(
        client,
        f"/api/listen-jobs/{job_id}/fail",
        {"worker": "w2", "error": "fetch failed", "retry": True},
    )
    assert resp.get_json()["status"] == "queued"


def test_live_listening_gets_the_sessions_own_tunes(client, admin_user, night):
    with admin_user:
        got = client.get(f"/api/session-instances/{NIGHT}/known-tunes").get_json()
        assert got["tune_ids"] == [KNOWN] and got["keys"] == {str(KNOWN): "Dmajor"}
        # the earlier night knows nothing from before it
        assert (
            client.get(f"/api/session-instances/{EARLIER}/known-tunes").get_json()[
                "tune_ids"
            ]
            == []
        )


def test_the_admin_page_lists_jobs_and_the_undo_takes_back_only_whats_unchecked(
    client, admin_user, night
):
    with admin_user:
        job_id = client.post(f"/api/recordings/{REC}/find-tunes").get_json()["job"][
            "listen_job_id"
        ]
        page = client.get("/admin/listen-jobs")
        assert page.status_code == 200 and b"Jobs053" in page.data
    _worker(client, "/api/listen-jobs/claim", {"worker": "w1"})
    drafts = [
        {
            "tune_id": OTHER,
            "name": "Other Jig",
            "start_ms": 10000,
            "end_ms": None,
            "p_right": 62,
        },
        {
            "tune_id": KNOWN,
            "name": "Known Reel",
            "start_ms": 100000,
            "end_ms": 200000,
            "p_right": 99,
        },
    ]
    _worker(
        client,
        f"/api/listen-jobs/{job_id}/result",
        {"worker": "w1", "drafts": drafts, "confidence_model": "listen-1"},
    )
    with admin_user:
        tunes = client.get(f"/api/recordings/{REC}/segmenter").get_json()["tunes"]
        confirmed = next(t for t in tunes if t["tune_id"] == KNOWN)[
            "session_instance_tune_id"
        ]
        client.post(f"/api/recordings/{REC}/segments/{confirmed}/confirm")
        undone = client.post(f"/api/recordings/{REC}/find-tunes/undo").get_json()
        assert undone["removed"] == 1
        assert [t["tune_id"] for t in undone["tunes"]] == [KNOWN]
