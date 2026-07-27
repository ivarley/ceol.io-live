"""
Integration tests for GET /api/tunes/<tune_id>/history — the lazily-fetched play
history behind the tune-detail modal's History tab.

The endpoint's whole job is the humane position math: order rows by the fractional
order_position, split sets on record_type='break' rows (spec 023), number only the
tune rows, and skip soft-deleted rows entirely. These tests seed two sessions with
known layouts and assert the (set_number, position_in_set) coordinates directly.

Isolation note: the endpoint opens its OWN db connection via get_db_connection(), so
seed rows are committed on a throwaway connection and explicitly deleted in teardown
(same pattern as test_live_logging_ops.py). Ids live in the 9700s — no other test
file uses that range.
"""

import pytest

from database import get_db_connection

pytestmark = pytest.mark.integration

SID_A = 9710        # "History Test Session A"
SID_B = 9720        # "History Test Session B"
INST_A = 9711       # instance of A (2026-03-01)
INST_B = 9721       # instance of B (2026-03-05, more recent)
TGT = 9712          # the tune whose history we ask for
OTHER1 = 9713       # filler tunes around it
OTHER2 = 9714


@pytest.fixture
def history_data():
    """Commit two sessions with known set layouts; cascade-delete after.

    Instance A (session A, 2026-03-01), in order_position order:
        set 1:  TGT, OTHER1
        break
        set 2:  OTHER2, TGT
        (then a soft-deleted TGT row that must not appear or shift numbering)
    Instance B (session B, 2026-03-05), in order_position order:
        set 1:  [deleted OTHER1], OTHER2, TGT   -> TGT is Set 1, Tune 2
    """
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                (SID_A, "History Test Session A", "history-test-a"))
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                (SID_B, "History Test Session B", "history-test-b"))
    for tid, name in [(TGT, "The History Target"), (OTHER1, "Filler One"), (OTHER2, "Filler Two")]:
        cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel')", (tid, name))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, %s)",
                (INST_A, SID_A, "2026-03-01"))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, %s)",
                (INST_B, SID_B, "2026-03-05"))

    def sit(inst, tune_id, pos, record_type="tune", deleted=False):
        cur.execute(
            """INSERT INTO session_instance_tune
               (session_instance_id, tune_id, record_type, order_position, deleted)
               VALUES (%s, %s, %s, %s, %s) RETURNING session_instance_tune_id""",
            (inst, tune_id, record_type, pos, deleted),
        )
        return cur.fetchone()[0]

    ids = {}
    ids["a_set1_tgt"] = sit(INST_A, TGT, "a1")
    sit(INST_A, OTHER1, "a2")
    sit(INST_A, None, "a3", record_type="break")
    sit(INST_A, OTHER2, "a4")
    ids["a_set2_tgt"] = sit(INST_A, TGT, "a5")
    sit(INST_A, TGT, "a6", deleted=True)

    sit(INST_B, OTHER1, "b1", deleted=True)
    sit(INST_B, OTHER2, "b2")
    ids["b_tgt"] = sit(INST_B, TGT, "b3")
    conn.commit()

    yield ids

    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id IN (%s, %s)", (INST_A, INST_B))
    cur.execute("DELETE FROM session_instance_tune_history WHERE session_instance_id IN (%s, %s)", (INST_A, INST_B))
    cur.execute("DELETE FROM session_instance_history WHERE session_instance_id IN (%s, %s)", (INST_A, INST_B))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id IN (%s, %s)", (INST_A, INST_B))
    cur.execute("DELETE FROM session_history WHERE session_id IN (%s, %s)", (SID_A, SID_B))
    cur.execute("DELETE FROM session WHERE session_id IN (%s, %s)", (SID_A, SID_B))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([TGT, OTHER1, OTHER2],))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", ([TGT, OTHER1, OTHER2],))
    conn.commit()
    cur.close()
    conn.close()


def _get(client, tune_id, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    resp = client.get(f"/api/tunes/{tune_id}/history" + (f"?{qs}" if qs else ""))
    return resp, resp.get_json()


class TestTuneHistory:
    def test_global_history_set_and_position(self, client, history_data):
        resp, data = _get(client, TGT)
        assert resp.status_code == 200 and data["success"]
        plays = data["play_instances"]
        # Most recent instance first (B), then A's two plays in log order.
        assert [(p["session_instance_id"], p["set_number"], p["position_in_set"]) for p in plays] == [
            (INST_B, 1, 2),   # deleted row before it doesn't shift the count
            (INST_A, 1, 1),
            (INST_A, 2, 2),   # break starts set 2; OTHER2 is tune 1, TGT tune 2
        ]
        assert plays[0]["session_instance_tune_id"] == history_data["b_tgt"]
        assert plays[1]["session_instance_tune_id"] == history_data["a_set1_tgt"]
        assert plays[2]["session_instance_tune_id"] == history_data["a_set2_tgt"]

    def test_deleted_rows_never_appear(self, client, history_data):
        resp, data = _get(client, TGT)
        sit_ids = {p["session_instance_tune_id"] for p in data["play_instances"]}
        assert sit_ids == set(history_data.values())  # exactly the 3 live TGT rows

    def test_session_scope_filters_to_that_session(self, client, history_data):
        resp, data = _get(client, TGT, session_path="history-test-a")
        assert resp.status_code == 200 and data["success"]
        assert {p["session_instance_id"] for p in data["play_instances"]} == {INST_A}
        assert len(data["play_instances"]) == 2

    def test_link_carries_highlight_and_tune(self, client, history_data):
        resp, data = _get(client, TGT, session_path="history-test-b")
        (play,) = data["play_instances"]
        assert play["link"] == (
            f"/sessions/history-test-b/{INST_B}?highlight={history_data['b_tgt']}&tune={TGT}"
        )
        assert play["full_name"] == "History Test Session B - 2026-03-05"

    def test_person_scopes_require_login(self, client, history_data):
        for params in ({"person": "me"}, {"scope": "member"}, {"scope": "attended"}):
            resp, data = _get(client, TGT, **params)
            assert resp.status_code == 401
            assert data["success"] is False

    def test_invalid_scope_rejected(self, client, history_data):
        resp, data = _get(client, TGT, scope="bogus")
        assert resp.status_code == 400
        assert data["success"] is False


@pytest.fixture
def scoped_person(authenticated_user):
    """The logged-in user's person_id, with helpers to relate them to the seeded
    sessions/instances (spec 033 predicate tests). Cleans up every row it added."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT person_id FROM user_account WHERE user_id = %s",
                (authenticated_user.user_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        cur.close()
        conn.close()
        pytest.skip("seeded user has no person record")
    person_id = row[0]

    class Rel:
        def __init__(self):
            self.person_id = person_id

        def join(self, session_id, relationship):
            cur.execute(
                """INSERT INTO session_person (session_id, person_id, relationship)
                   VALUES (%s, %s, %s)""",
                (session_id, person_id, relationship),
            )
            conn.commit()

        def check_in(self, instance_id, attendance="yes"):
            cur.execute(
                """INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
                   VALUES (%s, %s, %s)""",
                (instance_id, person_id, attendance),
            )
            conn.commit()

    yield Rel()

    cur.execute("DELETE FROM session_instance_person WHERE person_id = %s AND session_instance_id IN (%s, %s)",
                (person_id, INST_A, INST_B))
    cur.execute("DELETE FROM session_instance_person_history WHERE person_id = %s AND session_instance_id IN (%s, %s)",
                (person_id, INST_A, INST_B))
    cur.execute("DELETE FROM session_person WHERE person_id = %s AND session_id IN (%s, %s)",
                (person_id, SID_A, SID_B))
    cur.execute("DELETE FROM session_person_history WHERE person_id = %s AND session_id IN (%s, %s)",
                (person_id, SID_A, SID_B))
    conn.commit()
    cur.close()
    conn.close()


SID_F = 9730        # "History Test Festival" — session_type='festival'
INST_F1 = 9731      # 2026-06-06, "Advanced Session @ Jim Bowie"
INST_F2 = 9732      # 2026-06-06 as well — the whole point
INST_F3 = 9733      # 2026-06-07, no location_override (falls back to the venue)


@pytest.fixture
def festival_data():
    """A festival day running three sessions, two of them on the same date.

    This is the case a date-only label cannot describe: F1 and F2 share 2026-06-06 and
    would otherwise both read "History Test Festival - 2026-06-06". F3 has no
    location_override, so it exercises the fallback to the session's own venue.
    """
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO session (session_id, name, path, session_type, location_name) "
        "VALUES (%s, %s, %s, 'festival', %s)",
        (SID_F, "History Test Festival", "history-test-fest", "Scholz Garten"),
    )
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel')",
                (TGT, "The History Target"))
    for inst, date, override in (
        (INST_F1, "2026-06-06", "Advanced Session @ Jim Bowie"),
        (INST_F2, "2026-06-06", "After-Hours Session @ Hotel"),
        (INST_F3, "2026-06-07", None),
    ):
        cur.execute(
            "INSERT INTO session_instance (session_instance_id, session_id, date, location_override) "
            "VALUES (%s, %s, %s, %s)",
            (inst, SID_F, date, override),
        )
        cur.execute(
            """INSERT INTO session_instance_tune
               (session_instance_id, tune_id, record_type, order_position)
               VALUES (%s, %s, 'tune', 'a1')""",
            (inst, TGT),
        )
    conn.commit()

    yield

    insts = (INST_F1, INST_F2, INST_F3)
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id IN %s", (insts,))
    cur.execute("DELETE FROM session_instance_tune_history WHERE session_instance_id IN %s", (insts,))
    cur.execute("DELETE FROM session_instance_history WHERE session_instance_id IN %s", (insts,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id IN %s", (insts,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID_F,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID_F,))
    cur.execute("DELETE FROM tune_history WHERE tune_id = %s", (TGT,))
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (TGT,))
    conn.commit()
    cur.close()
    conn.close()


class TestFestivalInstanceLabels:
    """Spec 006: a festival instance is named by date AND place, because the date on its
    own names several of them. Regular sessions keep the bare date they always had."""

    def test_same_day_instances_get_distinct_labels(self, client, festival_data):
        resp, data = _get(client, TGT, session_path="history-test-fest")
        assert resp.status_code == 200 and data["success"]
        by_id = {p["session_instance_id"]: p for p in data["play_instances"]}
        assert by_id[INST_F1]["full_name"] == (
            "History Test Festival - 2026-06-06 - Advanced Session @ Jim Bowie")
        assert by_id[INST_F2]["full_name"] == (
            "History Test Festival - 2026-06-06 - After-Hours Session @ Hotel")
        # Same date, different label — which is the whole reason the place is appended.
        assert by_id[INST_F1]["full_name"] != by_id[INST_F2]["full_name"]

    def test_unnamed_instance_falls_back_to_the_session_venue(self, client, festival_data):
        resp, data = _get(client, TGT, session_path="history-test-fest")
        by_id = {p["session_instance_id"]: p for p in data["play_instances"]}
        assert by_id[INST_F3]["full_name"] == "History Test Festival - 2026-06-07 - Scholz Garten"

    def test_instance_label_drops_the_session_name(self, client, festival_data):
        """The in-session list already knows which session it is (spec 037 drawer)."""
        resp, data = _get(client, TGT, session_path="history-test-fest")
        by_id = {p["session_instance_id"]: p for p in data["play_instances"]}
        assert by_id[INST_F1]["instance_label"] == "2026-06-06 - Advanced Session @ Jim Bowie"

    def test_regular_sessions_are_unchanged(self, client, history_data):
        resp, data = _get(client, TGT, session_path="history-test-b")
        (play,) = data["play_instances"]
        assert play["full_name"] == "History Test Session B - 2026-03-05"
        assert play["instance_label"] == "2026-03-05"


class TestTuneHistoryScopes:
    """The spec 033 lenses on ?scope=: member (R3) vs attended (R4)."""

    def test_member_scope_includes_nights_not_checked_in(self, authenticated_user, history_data, scoped_person):
        # The Piper's Picnic regression: member of session A, never checked in
        # anywhere -> A's plays are "at my sessions" even with no attendance row.
        scoped_person.join(SID_A, "member")
        with authenticated_user:
            resp, data = _get(authenticated_user.client, TGT, scope="member")
            assert resp.status_code == 200 and data["success"]
            assert {p["session_instance_id"] for p in data["play_instances"]} == {INST_A}
            # ?person=me is the deprecated alias of scope=member
            resp, alias = _get(authenticated_user.client, TGT, person="me")
            assert {p["session_instance_id"] for p in alias["play_instances"]} == {INST_A}
            # ...and none of it counts as attended
            resp, att = _get(authenticated_user.client, TGT, scope="attended")
            assert att["play_instances"] == []

    def test_visitor_attendance_counts_only_as_attended(self, authenticated_user, history_data, scoped_person):
        # Visitor row (e.g. auto-created by check-in, spec 034) is NOT membership.
        scoped_person.join(SID_B, "visitor")
        scoped_person.check_in(INST_B, "yes")
        with authenticated_user:
            resp, member = _get(authenticated_user.client, TGT, scope="member")
            assert member["play_instances"] == []
            resp, att = _get(authenticated_user.client, TGT, scope="attended")
            assert {p["session_instance_id"] for p in att["play_instances"]} == {INST_B}

    def test_no_and_maybe_rsvps_never_count(self, authenticated_user, history_data, scoped_person):
        scoped_person.check_in(INST_A, "no")
        scoped_person.check_in(INST_B, "maybe")
        with authenticated_user:
            resp, att = _get(authenticated_user.client, TGT, scope="attended")
            assert att["play_instances"] == []


def _get_played_with(client, tune_id, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    resp = client.get(f"/api/tunes/{tune_id}/played-with" + (f"?{qs}" if qs else ""))
    return resp, resp.get_json()


class TestPlayedWithScopes:
    """The same lenses on /played-with (companions counted within scoped sets)."""

    def test_member_scope(self, authenticated_user, history_data, scoped_person):
        scoped_person.join(SID_A, "member")
        with authenticated_user:
            resp, data = _get_played_with(authenticated_user.client, TGT, scope="member")
        assert resp.status_code == 200 and data["success"]
        # Instance A only: set 1 pairs TGT with OTHER1, set 2 with OTHER2.
        assert {(t["tune_id"], t["count"]) for t in data["tunes"]} == {(OTHER1, 1), (OTHER2, 1)}

    def test_attended_scope(self, authenticated_user, history_data, scoped_person):
        scoped_person.check_in(INST_B, "yes")
        with authenticated_user:
            resp, data = _get_played_with(authenticated_user.client, TGT, scope="attended")
        assert resp.status_code == 200 and data["success"]
        # Instance B's single set pairs TGT with OTHER2 (OTHER1's row is deleted).
        assert {(t["tune_id"], t["count"]) for t in data["tunes"]} == {(OTHER2, 1)}

    def test_scope_requires_login(self, client, history_data):
        resp, data = _get_played_with(client, TGT, scope="member")
        assert resp.status_code == 401
