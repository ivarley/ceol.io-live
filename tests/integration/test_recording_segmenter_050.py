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
    # Logging from the segmenter goes through the live referee, which writes the
    # feed, per-row history and repertoire enrollment for this instance too.
    cur.execute("DELETE FROM session_event WHERE session_instance_id = %s", (REC_INSTANCE,))
    cur.execute(
        "DELETE FROM session_instance_tune_history WHERE session_instance_tune_id IN "
        "(SELECT session_instance_tune_id FROM session_instance_tune WHERE session_instance_id = %s)",
        (REC_INSTANCE,),
    )
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (REC_SESSION,))
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


def test_payload_offers_both_encodes_proxy_first(db_conn, db_cursor):
    _build(db_cursor)
    db_cursor.execute(
        "UPDATE recording SET stream_key = %s, stream_mime_type = 'audio/mp4', stream_size_bytes = 1234 "
        "WHERE recording_id = %s",
        ("recordings/test/seg050.m4a.stream.m4a", REC_ID),
    )
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    assert payload["recording"]["has_proxy"] is True


def test_payload_offers_only_the_master_without_a_proxy(db_conn, db_cursor):
    _build(db_cursor)
    from serializers import build_recording_segmenter_payload

    payload = build_recording_segmenter_payload(db_conn, REC_ID, include_audio_url=False)
    assert payload["recording"]["has_proxy"] is False


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


def test_payload_lists_both_urls_proxy_first(db_conn, db_cursor, monkeypatch):
    """Both encodes reach the client so the operator can switch on the fly --
    the right one depends on the connection they are on, which import time
    cannot know."""
    _build(db_cursor)
    db_cursor.execute(
        "UPDATE recording SET stream_key = 'k.stream.m4a', stream_mime_type = 'audio/mp4', "
        "stream_size_bytes = 44716235, file_size_bytes = 348303266 WHERE recording_id = %s",
        (REC_ID,),
    )
    import recording as rec_module

    monkeypatch.setattr(rec_module, "generate_presigned_url", lambda key, **kw: f"https://signed/{key}")
    from serializers import build_recording_segmenter_payload

    sources = build_recording_segmenter_payload(db_conn, REC_ID)["recording"]["audio_sources"]
    assert [s["id"] for s in sources] == ["proxy", "master"]
    assert sources[0]["url"].endswith("k.stream.m4a")
    assert sources[1]["url"].endswith("recordings/test/seg050.m4a")
    assert sources[0]["size_bytes"] < sources[1]["size_bytes"]


# --------------------------------------------------------------------------- #
# 4. Logging while segmenting (spec 050): a log written from the audio
# --------------------------------------------------------------------------- #


def _log_at(client, start_ms, end_ms=None):
    resp = client.post(f"/api/recordings/{REC_ID}/segments", json={"start_ms": start_ms, "end_ms": end_ms})
    return resp, resp.get_json()


def _names(tunes):
    return [(t["name"], t["set_number"]) for t in tunes]


def test_log_appends_gan_ainm_to_the_open_set_when_the_last_tune_runs_into_it(
    client, admin_user, committed_recording, db_cursor
):
    """[A, B] break [C] break [D]: place D with an implicit end, then mark later
    -> the new tune shares D's set. Unlinked, named "Gan Ainm", source 'segmenter',
    placed at the mark, and announced on the live feed like any other add."""
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['D']}", json={"start_ms": 100000})
        resp, body = _log_at(client, 130000)
        assert resp.status_code == 201, body
        new = body["tune"]
        assert new["name"] == "Gan Ainm"
        assert new["tune_id"] is None
        assert new["source"] == "segmenter"
        assert new["segment"]["start_ms"] == 130000 and new["segment"]["end_ms"] is None
        assert _names(body["tunes"]) == [("Alpha Reel", 1), ("Bravo Jig", 1), ("Charlie Polka", 2), ("Delta Hornpipe", 3), ("Gan Ainm", 3)]

    db_cursor.execute(
        "SELECT op_type FROM session_event WHERE session_instance_id = %s ORDER BY event_id", (REC_INSTANCE,)
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["add_tune"]


def test_log_opens_a_new_set_after_an_explicit_end(client, admin_user, committed_recording, db_cursor):
    """An End-set mark on D closes its set on purpose, so the next tune starts set 4
    -- a break is written into the log between them."""
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['D']}", json={"start_ms": 100000, "end_ms": 120000})
        resp, body = _log_at(client, 130000)
        assert resp.status_code == 201, body
        assert _names(body["tunes"])[-2:] == [("Delta Hornpipe", 3), ("Gan Ainm", 4)]

    db_cursor.execute(
        "SELECT op_type FROM session_event WHERE session_instance_id = %s ORDER BY event_id", (REC_INSTANCE,)
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["add_tune", "set_break"]


def test_log_reuses_the_break_that_already_follows_an_ended_tune(client, admin_user, committed_recording):
    """C is placed and ended explicitly; a break already sits between C and D in
    the log, so a tune marked between them joins D's set rather than minting a
    second break."""
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['C']}", json={"start_ms": 50000, "end_ms": 60000})
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['D']}", json={"start_ms": 100000})
        resp, body = _log_at(client, 70000)
        assert resp.status_code == 201, body
        assert _names(body["tunes"]) == [("Alpha Reel", 1), ("Bravo Jig", 1), ("Charlie Polka", 2), ("Gan Ainm", 3), ("Delta Hornpipe", 3)]


def test_log_goes_in_front_when_nothing_placed_precedes_it(client, admin_user, committed_recording):
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['A']}", json={"start_ms": 50000})
        resp, body = _log_at(client, 10000)
        assert resp.status_code == 201, body
        assert _names(body["tunes"])[:2] == [("Gan Ainm", 1), ("Alpha Reel", 1)]


def test_log_is_built_from_nothing_on_an_empty_night(client, admin_user, committed_recording, db_cursor):
    db_cursor.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (REC_INSTANCE,))
    db_cursor.connection.commit()
    with admin_user:
        _, first = _log_at(client, 1000)
        _, second = _log_at(client, 20000)
        # End the first set at the second tune, then mark a third.
        client.put(f"/api/recordings/{REC_ID}/segments/{second['tune']['session_instance_tune_id']}", json={"start_ms": 20000, "end_ms": 40000})
        _, third = _log_at(client, 60000)
        assert _names(third["tunes"]) == [("Gan Ainm", 1), ("Gan Ainm", 1), ("Gan Ainm", 2)]
        assert [t["is_set_end"] for t in third["tunes"]] == [False, True, True]


def test_log_refuses_a_duplicate_moment_and_the_usual_bad_input(client, admin_user, committed_recording):
    with admin_user:
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['A']}", json={"start_ms": 5000})
        assert _log_at(client, 5000)[0].status_code == 409
        assert client.post(f"/api/recordings/{REC_ID}/segments", json={}).status_code == 400
        assert _log_at(client, 999999999)[0].status_code == 400
        assert _log_at(client, 8000, 7000)[0].status_code == 400


def test_set_tune_links_renames_and_logs_as_is(client, admin_user, committed_recording, db_cursor):
    with admin_user:
        _, body = _log_at(client, 130000)
        sit = body["tune"]["session_instance_tune_id"]

        # Pick a catalog tune: linked, the display name follows the catalog.
        resp = client.put(f"/api/recordings/{REC_ID}/segments/{sit}/tune", json={"tune_id": 95110, "name": "Alpha Reel"})
        assert resp.status_code == 200, resp.get_json()
        assert (resp.get_json()["tune"]["tune_id"], resp.get_json()["tune"]["name"]) == (95110, "Alpha Reel")
        assert resp.get_json()["tune"]["tune_type"] == "Reel"
        # ...and the segment placed on it survived the relink.
        assert resp.get_json()["tune"]["segment"]["start_ms"] == 130000

        # "Log as is": the typed name, unlinked.
        resp = client.put(f"/api/recordings/{REC_ID}/segments/{sit}/tune", json={"name": "The Squirrely Hobbit"})
        assert resp.status_code == 200
        assert (resp.get_json()["tune"]["tune_id"], resp.get_json()["tune"]["name"]) == (None, "The Squirrely Hobbit")

        assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}/tune", json={}).status_code == 400
        assert client.put(f"/api/recordings/{REC_ID}/segments/1/tune", json={"name": "x"}).status_code == 404

    db_cursor.execute(
        "SELECT op_type FROM session_event WHERE session_instance_id = %s ORDER BY event_id", (REC_INSTANCE,)
    )
    assert [r[0] for r in db_cursor.fetchall()] == ["add_tune", "change_tune", "change_tune"]


def test_set_tune_imports_a_thesession_pick_sent_with_both_ids(client, admin_user, committed_recording, db_cursor, monkeypatch):
    """A thesession.org search result arrives with thesession_id AND tune_id (the
    search sets both to the thesession id). The tune isn't in our catalogue yet, so
    the pick must import it before linking -- it used to skip the import when
    tune_id was present and 500 on the session_instance_tune FK."""
    import live_logging_routes

    ts_id = 4952
    monkeypatch.setattr(
        live_logging_routes, "_fetch_thesession_tune",
        lambda tid: {"name": "Loch Lomond", "type": "waltz", "tunebooks": 7,
                     "settings": [{"id": 4952001, "key": "Gmaj", "abc": "G2 B2 d2|"}]},
    )
    with admin_user:
        _, body = _log_at(client, 130000)
        sit = body["tune"]["session_instance_tune_id"]
        resp = client.put(
            f"/api/recordings/{REC_ID}/segments/{sit}/tune",
            json={"thesession_id": ts_id, "tune_id": ts_id, "name": "Loch Lomond", "tune_type": "waltz"},
        )
        assert resp.status_code == 200, resp.get_json()
        tune = resp.get_json()["tune"]
        assert (tune["tune_id"], tune["name"], tune["tune_type"]) == (ts_id, "Loch Lomond", "Waltz")
        assert tune["segment"]["start_ms"] == 130000

    db_cursor.execute("SELECT name FROM tune WHERE tune_id = %s", (ts_id,))
    assert db_cursor.fetchone()[0] == "Loch Lomond"


def _insert(client, **body):
    resp = client.post(f"/api/recordings/{REC_ID}/segments", json=body)
    return resp, resp.get_json()


def test_insert_after_and_before_a_row_stay_in_its_set(client, admin_user, committed_recording):
    """The log's own "add before / add after": [A, B] break [C] break [D]. After A
    lands between A and B; before C lands at the front of set 2, after the break.
    Neither is placed -- the mark key does that next."""
    with admin_user:
        resp, body = _insert(client, after_record_id=committed_recording["A"], tune_id=95113, name="Delta Hornpipe")
        assert resp.status_code == 201, body
        assert body["tune"]["tune_id"] == 95113 and body["tune"]["segment"] is None
        assert body["tune"]["source"] == "segmenter"
        assert _names(body["tunes"]) == [
            ("Alpha Reel", 1), ("Delta Hornpipe", 1), ("Bravo Jig", 1), ("Charlie Polka", 2), ("Delta Hornpipe", 3),
        ]
        resp, body = _insert(client, before_record_id=committed_recording["C"], name="The Squirrely Hobbit")
        assert resp.status_code == 201, body
        assert body["tune"]["tune_id"] is None  # a bare name is "as-is": unlinked
        assert _names(body["tunes"])[3:] == [("The Squirrely Hobbit", 2), ("Charlie Polka", 2), ("Delta Hornpipe", 3)]
        # No identity at all: the tool's placeholder, placed where asked.
        resp, body = _insert(client, before_record_id=committed_recording["A"])
        assert resp.status_code == 201, body
        assert _names(body["tunes"])[:2] == [("Gan Ainm", 1), ("Alpha Reel", 1)]


def test_insert_new_set_opens_a_set_of_its_own(client, admin_user, committed_recording, db_cursor):
    """The + between sets: after A's set (anchor = its last tune, B) the new tune
    gets a break on each side, so it is set 2 and C's set becomes 3. After the
    very last tune it opens a set at the end; on an empty night there is nothing
    to break from, so no break is written."""
    with admin_user:
        resp, body = _insert(client, after_record_id=committed_recording["B"], new_set=True, tune_id=95110, name="Alpha Reel")
        assert resp.status_code == 201, body
        assert _names(body["tunes"]) == [
            ("Alpha Reel", 1), ("Bravo Jig", 1), ("Alpha Reel", 2), ("Charlie Polka", 3), ("Delta Hornpipe", 4),
        ]
        resp, body = _insert(client, after_record_id=committed_recording["D"], new_set=True)
        assert resp.status_code == 201, body
        assert _names(body["tunes"])[-2:] == [("Delta Hornpipe", 4), ("Gan Ainm", 5)]
        # An anchor that has since been removed is an error, not a silent append.
        assert _insert(client, after_record_id=999999, new_set=True)[0].status_code == 404

    db_cursor.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (REC_INSTANCE,))
    db_cursor.connection.commit()
    with admin_user:
        resp, body = _insert(client, new_set=True)
        assert resp.status_code == 201, body
        assert _names(body["tunes"]) == [("Gan Ainm", 1)]
    db_cursor.execute(
        "SELECT COUNT(*) FROM session_instance_tune WHERE session_instance_id = %s AND record_type = 'break'", (REC_INSTANCE,)
    )
    assert db_cursor.fetchone()[0] == 0


def test_unlog_removes_any_tune_from_the_log(client, admin_user, committed_recording, db_cursor):
    with admin_user:
        _, body = _log_at(client, 130000)
        sit = body["tune"]["session_instance_tune_id"]
        resp = client.post(f"/api/recordings/{REC_ID}/segments/{sit}/unlog")
        assert resp.status_code == 200
        assert "Gan Ainm" not in [t["name"] for t in resp.get_json()["tunes"]]
        assert client.post(f"/api/recordings/{REC_ID}/segments/{sit}/unlog").status_code == 404
        # A tune written down on the night goes too: the log's own Remove.
        client.put(f"/api/recordings/{REC_ID}/segments/{committed_recording['A']}", json={"start_ms": 1000})
        resp = client.post(f"/api/recordings/{REC_ID}/segments/{committed_recording['A']}/unlog")
        assert resp.status_code == 200
        assert [t["name"] for t in resp.get_json()["tunes"]] == ["Bravo Jig", "Charlie Polka", "Delta Hornpipe"]
    db_cursor.execute("SELECT COUNT(*) FROM recording_tune_segment WHERE session_instance_tune_id = %s", (committed_recording["A"],))
    assert db_cursor.fetchone()[0] == 0

    db_cursor.execute("SELECT deleted FROM session_instance_tune WHERE session_instance_tune_id = %s", (sit,))
    assert db_cursor.fetchone()[0] is True  # tombstoned, like any live removal
    db_cursor.execute("SELECT COUNT(*) FROM recording_tune_segment WHERE session_instance_tune_id = %s", (sit,))
    assert db_cursor.fetchone()[0] == 0


def test_logging_endpoints_require_authentication(client, committed_recording):
    sit = committed_recording["A"]
    assert client.post(f"/api/recordings/{REC_ID}/segments", json={"start_ms": 1}).status_code == 401
    assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}/tune", json={"name": "x"}).status_code == 401
    assert client.post(f"/api/recordings/{REC_ID}/segments/{sit}/unlog").status_code == 401


def test_logging_endpoints_require_the_recording_grant(client, authenticated_user, committed_recording):
    sit = committed_recording["A"]
    with authenticated_user:
        assert client.post(f"/api/recordings/{REC_ID}/segments", json={"start_ms": 1}).status_code == 403
        assert client.put(f"/api/recordings/{REC_ID}/segments/{sit}/tune", json={"name": "x"}).status_code == 403
        assert client.post(f"/api/recordings/{REC_ID}/segments/{sit}/unlog").status_code == 403
