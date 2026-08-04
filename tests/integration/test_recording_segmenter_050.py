"""
Integration tests for the recording segmenter (spec 050).

Three groups:

1. `build_recording_segmenter_payload` — the set grouping derived from the
   interleaved 'break' marker rows, the is_set_end flag the UI keys its "needs
   an explicit end" hint off, and segment attachment.

2. The PUT/DELETE segment vocabulary — the upsert, the ownership checks that
   stop a tune from another night being attached, and the audit rows.

3. End resolution — that the export (via recording_tune_segment_resolved) turns
   implicit ends into the next tune's start and a trailing implicit end into the
   end of the file. This is the property the training corpus depends on, and the
   one place the DB and the client each implement the same rule, so it is worth
   pinning down.

Fixtures are transaction-local (db_conn auto-rollback) where they can be, and
committed in the 951xx block for the HTTP tests, which open their own
connections. Teardown deletes them.
"""

import base64

import pytest

REC_SESSION = 95100
REC_INSTANCE = 95101
REC_ID = 95102


def _build(cur, *, with_peaks=False):
    """A session instance whose log is: [A, B] break [C] break [D].

    Two sets of unequal length plus a leading tune, which is what makes the
    set-numbering and is_set_end assertions meaningful.
    """
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Segmenter050', 'segmenter050-test')",
        (REC_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-03-05')",
        (REC_INSTANCE, REC_SESSION),
    )
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES "
        "(95110, 'Alpha Reel', 'Reel'), (95111, 'Bravo Jig', 'Jig'), "
        "(95112, 'Charlie Polka', 'Polka'), (95113, 'Delta Hornpipe', 'Hornpipe')"
    )

    ids = {}
    layout = [
        ("a0", "tune", 95110, "A"),
        ("a1", "tune", 95111, "B"),
        ("a2", "break", None, None),
        ("a3", "tune", 95112, "C"),
        ("a4", "break", None, None),
        ("a5", "tune", 95113, "D"),
    ]
    for order_position, record_type, tune_id, key in layout:
        cur.execute(
            "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) "
            "VALUES (%s, %s, %s, %s) RETURNING session_instance_tune_id",
            (REC_INSTANCE, tune_id, order_position, record_type),
        )
        if key:
            ids[key] = cur.fetchone()[0]

    peaks = base64.b64encode(bytes(range(0, 200))).decode("ascii") if with_peaks else None
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, storage_key, duration_ms, "
        "is_clock_anchor, peaks, peaks_hz) VALUES (%s, %s, 'recordings/test/seg050.m4a', 600000, TRUE, %s, 20) ",
        (REC_ID, REC_INSTANCE, peaks),
    )
    return ids


def _teardown(cur):
    # History has no FK to the live rows, so it survives the cascade and would
    # otherwise accumulate across tests that reuse REC_ID.
    cur.execute("DELETE FROM recording_tune_segment_history WHERE recording_id = %s", (REC_ID,))
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (REC_ID,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (REC_ID,))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (REC_INSTANCE,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (REC_INSTANCE,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (REC_SESSION,))
    cur.execute("DELETE FROM tune WHERE tune_id BETWEEN 95110 AND 95113")


# --------------------------------------------------------------------------- #
# 1. payload shape
# --------------------------------------------------------------------------- #


def test_payload_groups_tunes_into_sets_and_drops_breaks(db_conn, db_cursor):
    _build(db_cursor)
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)

    names = [t["name"] for t in payload["tunes"]]
    assert names == ["Alpha Reel", "Bravo Jig", "Charlie Polka", "Delta Hornpipe"]
    # Break rows are consumed into set numbering, never shown.
    assert [t["set_number"] for t in payload["tunes"]] == [1, 1, 2, 3]
    assert [t["position_in_set"] for t in payload["tunes"]] == [1, 2, 1, 1]


def test_payload_flags_last_tune_of_each_set(db_conn, db_cursor):
    _build(db_cursor)
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    # Only the last tune of a set needs an explicit end typed; everything else
    # gets its end from the next tune's start.
    assert [t["is_set_end"] for t in payload["tunes"]] == [False, True, True, True]


def test_payload_attaches_existing_segments(db_conn, db_cursor):
    ids = _build(db_cursor)
    db_cursor.execute(
        "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms, end_ms) "
        "VALUES (%s, %s, 1000, 5000)",
        (REC_ID, ids["A"]),
    )
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    by_name = {t["name"]: t for t in payload["tunes"]}
    assert by_name["Alpha Reel"]["segment"]["start_ms"] == 1000
    assert by_name["Alpha Reel"]["segment"]["end_ms"] == 5000
    assert by_name["Bravo Jig"]["segment"] is None


def test_payload_is_none_for_unknown_recording(db_conn):
    from serializers import build_recording_segmenter_payload

    assert build_recording_segmenter_payload(db_conn, 987654321, include_audio_url=False) is None


# --------------------------------------------------------------------------- #
# 2. end resolution (the property the training corpus rests on)
# --------------------------------------------------------------------------- #


def test_implicit_end_resolves_to_next_start_and_trailing_to_file_end(db_conn, db_cursor):
    ids = _build(db_cursor)
    # A and B implicit, C explicit, D implicit and last.
    for key, start, end in (("A", 1000, None), ("B", 40000, None), ("C", 90000, 120000), ("D", 300000, None)):
        db_cursor.execute(
            "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms, end_ms) "
            "VALUES (%s, %s, %s, %s)",
            (REC_ID, ids[key], start, end),
        )

    db_cursor.execute(
        "SELECT display_name, start_ms, resolved_end_ms, end_is_explicit "
        "FROM recording_tune_segment_resolved WHERE recording_id = %s ORDER BY start_ms",
        (REC_ID,),
    )
    rows = db_cursor.fetchall()
    assert rows[0] == ("Alpha Reel", 1000, 40000, False)      # runs to B's start
    assert rows[1] == ("Bravo Jig", 40000, 90000, False)      # runs to C's start
    assert rows[2] == ("Charlie Polka", 90000, 120000, True)  # its own explicit end
    assert rows[3] == ("Delta Hornpipe", 300000, 600000, False)  # runs to end of file


def test_resolution_ignores_log_order_and_follows_the_clock(db_conn, db_cursor):
    """A tune placed out of log order still ends where the next tune in TIME
    starts — the timeline is the audio, not the list."""
    ids = _build(db_cursor)
    db_cursor.execute(
        "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms) VALUES (%s, %s, 200000)",
        (REC_ID, ids["A"]),
    )
    db_cursor.execute(
        "INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms) VALUES (%s, %s, 100000)",
        (REC_ID, ids["D"]),
    )
    db_cursor.execute(
        "SELECT display_name, resolved_end_ms FROM recording_tune_segment_resolved "
        "WHERE recording_id = %s ORDER BY start_ms",
        (REC_ID,),
    )
    assert db_cursor.fetchall() == [("Delta Hornpipe", 200000), ("Alpha Reel", 600000)]


# --------------------------------------------------------------------------- #
# 3. HTTP vocabulary (committed fixtures; endpoints open their own connections)
# --------------------------------------------------------------------------- #


@pytest.fixture
def committed_recording(db_setup):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    ids = _build(cur, with_peaks=True)
    conn.commit()
    yield ids
    _teardown(cur)
    conn.commit()
    conn.close()


def test_put_creates_then_updates_the_same_segment(client, admin_user, committed_recording):
    sit = committed_recording["A"]
    with admin_user:
        first = client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 1000})
        assert first.status_code == 201
        assert first.get_json()["segment"]["end_ms"] is None

        # Same call again is an update, not a duplicate — the client never has to
        # know whether a mark already exists.
        again = client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 2000, "end_ms": 9000})
        assert again.status_code == 200
        body = again.get_json()
        assert (body["segment"]["start_ms"], body["segment"]["end_ms"]) == (2000, 9000)
        assert body["segment"]["recording_tune_segment_id"] == first.get_json()["segment"]["recording_tune_segment_id"]


def test_put_rejects_bad_ranges_and_foreign_tunes(client, admin_user, committed_recording):
    sit = committed_recording["A"]
    with admin_user:
        assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={}).status_code == 400
        assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": -5}).status_code == 400
        assert client.put(
            f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 5000, "end_ms": 5000}
        ).status_code == 400
        # Past the end of the audio.
        assert client.put(
            f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 999999999}
        ).status_code == 400
        # A tune id that exists but belongs to a different night.
        assert client.put(f"/api/recordings/{REC_ID}/segments/1", json={"start_ms": 1000}).status_code == 400


def test_put_rejects_set_break_rows(client, admin_user, committed_recording, db_cursor):
    db_cursor.execute(
        "SELECT session_instance_tune_id FROM session_instance_tune "
        "WHERE session_instance_id = %s AND record_type = 'break' LIMIT 1",
        (REC_INSTANCE,),
    )
    break_id = db_cursor.fetchone()[0]
    with admin_user:
        resp = client.put(f"/api/recordings/{REC_ID}/segments/{break_id}", json={"start_ms": 1000})
    assert resp.status_code == 400
    assert "set break" in resp.get_json()["error"]


def test_delete_removes_the_segment_and_404s_when_absent(client, admin_user, committed_recording):
    sit = committed_recording["B"]
    with admin_user:
        assert client.delete(f"/api/recordings/{REC_ID}/segments/{sit}").status_code == 404
        client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 3000})
        assert client.delete(f"/api/recordings/{REC_ID}/segments/{sit}").status_code == 200
        assert client.delete(f"/api/recordings/{REC_ID}/segments/{sit}").status_code == 404


def test_writes_leave_history_rows(client, admin_user, committed_recording, db_cursor):
    sit = committed_recording["C"]
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 1000})
        client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 2000})
        client.delete(f"/api/recordings/{REC_ID}/segments/{sit}")

    db_cursor.execute(
        "SELECT operation FROM recording_tune_segment_history h "
        "WHERE h.recording_id = %s ORDER BY h.history_id",
        (REC_ID,),
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["INSERT", "UPDATE", "DELETE"]


def test_peaks_endpoint_serves_raw_bytes(client, admin_user, committed_recording):
    with admin_user:
        resp = client.get(f"/api/recordings/{REC_ID}/peaks")
    assert resp.status_code == 200
    assert resp.mimetype == "application/octet-stream"
    assert resp.headers["X-Peaks-Hz"] == "20.00"
    assert resp.data == bytes(range(0, 200))


def test_export_reports_resolved_ends(client, admin_user, committed_recording):
    a, b = committed_recording["A"], committed_recording["B"]
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{a}", json={"start_ms": 1000})
        client.put(f"/api/recordings/{REC_ID}/segments/{b}", json={"start_ms": 30000, "end_ms": 45000})
        body = client.get(f"/api/recordings/{REC_ID}/export").get_json()

    assert body["segment_count"] == 2
    first, second = body["segments"]
    assert (first["name"], first["end_ms"], first["end_is_explicit"]) == ("Alpha Reel", 30000, False)
    assert (second["name"], second["end_ms"], second["end_is_explicit"]) == ("Bravo Jig", 45000, True)


def test_endpoints_require_authentication(client, committed_recording):
    sit = committed_recording["A"]
    assert client.get(f"/api/recordings/{REC_ID}/segmenter").status_code == 401
    assert client.get(f"/api/recordings/{REC_ID}/peaks").status_code == 401
    assert client.get(f"/api/recordings/{REC_ID}/export").status_code == 401
    assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 1}).status_code == 401
    assert client.delete(f"/api/recordings/{REC_ID}/segments/{sit}").status_code == 401


def test_endpoints_require_admin(client, authenticated_user, committed_recording):
    sit = committed_recording["A"]
    with authenticated_user:
        assert client.get(f"/api/recordings/{REC_ID}/segmenter").status_code == 403
        assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}", json={"start_ms": 1}).status_code == 403


# --------------------------------------------------------------------------- #
# 4. playback proxy (spec 051)
# --------------------------------------------------------------------------- #


def test_payload_plays_the_proxy_when_there_is_one(db_conn, db_cursor):
    _build(db_cursor)
    db_cursor.execute(
        "UPDATE recording SET stream_key = %s, stream_mime_type = 'audio/mp4', stream_size_bytes = 1234 "
        "WHERE recording_id = %s",
        ("recordings/test/seg050.m4a.stream.m4a", REC_ID),
    )
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    assert payload["recording"]["is_proxy"] is True
    assert payload["recording"]["audio_mime_type"] == "audio/mp4"
    assert payload["recording"]["stream_size_bytes"] == 1234


def test_payload_falls_back_to_the_master_without_a_proxy(db_conn, db_cursor):
    _build(db_cursor)
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    assert payload["recording"]["is_proxy"] is False
    assert payload["recording"]["stream_size_bytes"] is None


def test_export_cuts_from_the_master_never_the_proxy(client, admin_user, committed_recording, db_cursor):
    """The invariant the whole two-key split exists to protect.

    A proxy is a lossy 48kbps mono encode. Training a tune-recognition model on
    its artefacts instead of the real audio would be a quiet, expensive mistake,
    so the export must keep naming storage_key however playback is served.
    """
    db_cursor.execute(
        "UPDATE recording SET stream_key = 'recordings/test/proxy.stream.m4a' WHERE recording_id = %s",
        (REC_ID,),
    )
    db_cursor.connection.commit()
    try:
        with admin_user:
            client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['A']}", json={"start_ms": 1000})
            body = client.get(f"/api/recordings/{REC_ID}/export").get_json()
        assert body["storage_key"] == "recordings/test/seg050.m4a"
        assert ".stream." not in body["storage_key"]
    finally:
        db_cursor.execute("UPDATE recording SET stream_key = NULL WHERE recording_id = %s", (REC_ID,))
        db_cursor.connection.commit()
