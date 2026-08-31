"""The /admin/recordings work queue and the partial-recording escape hatch (schema/055).

Two things are being pinned down here.

**The ordering is the feature.** The page used to be one date-sorted table, which
is the wrong sort for a page whose only purpose is finding the next thing to
timestamp: a failed ingest from March sits below thirty finished nights and is
never seen again. So a recording is placed by what it is waiting for, and the
tests state that placement rather than the SQL that produces it.

**Progress cannot always reach 100%.** "38 of 52 tunes placed" quietly assumes
the audio covers the whole night, and plenty of it doesn't — a phone started an
hour in, a battery that died before the last set. Those recordings can never
reach their denominator, so without a way to say "that's all there is in this
one" they advertise work that does not exist, forever. Nothing about that is
derivable, so it is written down and these tests cover writing it.
"""

import pytest

from serializers import recording_work_state

WL_SESSION = 95500
WL_INSTANCE = 95501
WL_EMPTY_INSTANCE = 95502
WL_RECORDING = 95503


# --------------------------------------------------------------------------- #
# Which pile a recording lands in
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "status,segments,tunes,complete,expected_group",
    [
        # A broken ingest is the most urgent thing on the page even though it is
        # the rarest, so it leads regardless of anything else about the row.
        ("failed", 0, 20, False, "failed"),
        ("failed", 20, 20, False, "failed"),
        # Ready, logged, unplaced: the actual work.
        ("ready", 0, 20, False, "todo"),
        ("ready", 7, 20, False, "todo"),
        # A machine is still on it. Nothing for a person to do.
        ("queued", 0, 20, False, "processing"),
        ("processing", 0, 20, False, "processing"),
        # Audio with no logged tunes behind it: real, but the next step is the
        # log, not the segmenter.
        ("ready", 0, 0, False, "blocked"),
        # Both ways of being finished.
        ("ready", 20, 20, False, "done"),
        ("ready", 3, 20, True, "done"),
        # A recording of a night nobody logged, marked done by hand, is still
        # done -- the claim is about the audio, not about the log.
        ("ready", 0, 0, True, "done"),
    ],
)
def test_a_recording_is_filed_by_what_it_is_waiting_for(
    status, segments, tunes, complete, expected_group
):
    assert recording_work_state(status, segments, tunes, complete)["group"] == expected_group


def test_the_hand_set_flag_outranks_the_count():
    """The flag says "there is nothing else IN THIS AUDIO", which stays true when
    more of the night gets logged later. Deriving doneness from the count alone
    would quietly undo the operator's decision the next time a tune was added."""
    state = recording_work_state("ready", 3, 99, True)
    assert state["group"] == "done"
    assert state["complete"] is True
    assert state["state_label"] == "Marked done"


def test_part_placed_and_not_started_are_the_same_pile_but_not_the_same_row():
    """Both are work; only one has been started. The distinction earns its keep
    when choosing which to pick up, so it survives into the badge."""
    started = recording_work_state("ready", 4, 20, False)
    untouched = recording_work_state("ready", 0, 20, False)
    assert started["group"] == untouched["group"] == "todo"
    assert started["state_label"] != untouched["state_label"]


# --------------------------------------------------------------------------- #
# The queue as the page sees it
# --------------------------------------------------------------------------- #
@pytest.fixture
def worklist_world(db_setup):
    """A session with one logged night, one unlogged night, and one recording."""
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES (%s, 'Worklist055', 'worklist055-test')",
        (WL_SESSION,),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES "
        "(%s, %s, '2026-07-02'), (%s, %s, '2026-07-09')",
        (WL_INSTANCE, WL_SESSION, WL_EMPTY_INSTANCE, WL_SESSION),
    )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, storage_key, duration_ms, "
        "is_clock_anchor, status) VALUES (%s, %s, 'recordings/worklist055.mp3', 600000, TRUE, 'ready')",
        (WL_RECORDING, WL_INSTANCE),
    )
    conn.commit()
    yield conn
    cur.execute("DELETE FROM recording_history WHERE recording_id = %s", (WL_RECORDING,))
    cur.execute("DELETE FROM recording WHERE recording_id = %s", (WL_RECORDING,))
    cur.execute("DELETE FROM session_instance WHERE session_id = %s", (WL_SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (WL_SESSION,))
    conn.commit()
    conn.close()


def _ours(payload):
    return next(r for r in payload["recordings"] if r["recording_id"] == WL_RECORDING)


def _outstanding_ids(payload):
    """The recordings the page says are waiting on someone. Read as a set of ids
    rather than as `payload["outstanding"]`, because the payload covers every
    recording in the database and the seed data has its own."""
    return {
        r["recording_id"]
        for g in payload["groups"]
        if g["slug"] in ("failed", "todo")
        for r in g["recordings"]
    }


def test_the_payload_is_grouped_in_the_order_the_page_prints(worklist_world):
    from serializers import RECORDING_WORK_GROUPS, build_admin_recordings_payload

    payload = build_admin_recordings_payload(worklist_world)
    printed = [g["slug"] for g in payload["groups"]]
    wanted = [g["slug"] for g in RECORDING_WORK_GROUPS]
    # Empty groups are dropped, but the ones that remain keep their order --
    # urgent first is the whole point of grouping at all.
    assert printed == [slug for slug in wanted if slug in printed]
    # Nothing is lost on the way into the groups.
    assert sum(len(g["recordings"]) for g in payload["groups"]) == len(payload["recordings"])


def test_a_night_with_no_logged_tunes_is_not_counted_as_work(worklist_world):
    """It is a real recording and it isn't finished, but the segmenter has
    nothing to place against it, so putting it in the work pile would be a
    standing lie about how much there is to do."""
    from serializers import build_admin_recordings_payload

    cur = worklist_world.cursor()
    cur.execute(
        "UPDATE recording SET session_instance_id = %s WHERE recording_id = %s",
        (WL_EMPTY_INSTANCE, WL_RECORDING),
    )
    worklist_world.commit()

    payload = build_admin_recordings_payload(worklist_world)
    assert _ours(payload)["group"] == "blocked"
    assert WL_RECORDING not in _outstanding_ids(payload)

    cur.execute(
        "UPDATE recording SET session_instance_id = %s WHERE recording_id = %s",
        (WL_INSTANCE, WL_RECORDING),
    )
    worklist_world.commit()


def test_marking_a_partial_recording_done_takes_it_out_of_the_queue(
    client, authenticated_admin_user, worklist_world
):
    from serializers import build_admin_recordings_payload

    with authenticated_admin_user:
        response = client.put(
            f"/api/recordings/{WL_RECORDING}/segmenting-complete",
            json={"complete": True},
        )
    assert response.status_code == 200
    assert response.get_json()["segmenting_complete"] is True

    payload = build_admin_recordings_payload(worklist_world)
    assert _ours(payload)["group"] == "done"
    assert WL_RECORDING not in _outstanding_ids(payload)
    # The summary line counts exactly the recordings in those two groups.
    assert payload["outstanding"] == len(_outstanding_ids(payload))


def test_it_can_be_taken_back(client, authenticated_admin_user, worklist_world):
    """A night that turns out to have more in it than it seemed should not need a
    database session to reopen."""
    from database import get_db_connection

    with authenticated_admin_user:
        client.put(f"/api/recordings/{WL_RECORDING}/segmenting-complete", json={"complete": True})
        response = client.put(
            f"/api/recordings/{WL_RECORDING}/segmenting-complete", json={"complete": False}
        )
    assert response.status_code == 200

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT segmenting_complete, segmenting_complete_at FROM recording WHERE recording_id = %s",
        (WL_RECORDING,),
    )
    complete, completed_at = cur.fetchone()
    conn.close()
    assert complete is False
    # Cleared rather than left behind: "when was this declared finished" has no
    # answer for something that is not.
    assert completed_at is None


def test_the_decision_is_written_to_history(client, authenticated_admin_user, worklist_world):
    """A corpus that later turns out to have a gap in it gets asked when someone
    decided the audio was complete. recording_history is where that is answered."""
    from database import get_db_connection

    with authenticated_admin_user:
        client.put(f"/api/recordings/{WL_RECORDING}/segmenting-complete", json={"complete": True})

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT operation, segmenting_complete FROM recording_history "
        "WHERE recording_id = %s ORDER BY history_id DESC LIMIT 1",
        (WL_RECORDING,),
    )
    row = cur.fetchone()
    conn.close()
    # History holds the state BEFORE the change, as everywhere else in this app.
    assert row == ("UPDATE", False)


def test_a_non_boolean_is_refused(client, authenticated_admin_user, worklist_world):
    """The string "false" is truthy, and a flag that silently means the opposite
    of what was sent is worse than an error."""
    with authenticated_admin_user:
        response = client.put(
            f"/api/recordings/{WL_RECORDING}/segmenting-complete", json={"complete": "false"}
        )
    assert response.status_code == 400


def test_it_needs_the_same_permission_as_timestamping(client, worklist_world):
    """Saying a recording is finished IS part of timestamping it, so it is gated
    the same way rather than more loosely."""
    response = client.put(
        f"/api/recordings/{WL_RECORDING}/segmenting-complete", json={"complete": True}
    )
    assert response.status_code == 401
