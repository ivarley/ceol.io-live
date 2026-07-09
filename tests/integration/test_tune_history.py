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

    def test_person_scope_requires_login(self, client, history_data):
        resp, data = _get(client, TGT, person="me")
        assert resp.status_code == 401
        assert data["success"] is False

    def test_person_scope_filters_to_attended_instances(self, authenticated_user, history_data):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # The endpoint resolves person_id from the DB row for the logged-in
            # user_id (1 = the seeded admin), not from the mocked session user.
            cur.execute("SELECT person_id FROM user_account WHERE user_id = %s",
                        (authenticated_user.user_id,))
            row = cur.fetchone()
            if not row or row[0] is None:
                pytest.skip("seeded user has no person record")
            # Attach that person to instance A only.
            cur.execute(
                "INSERT INTO session_instance_person (session_instance_id, person_id) VALUES (%s, %s)",
                (INST_A, row[0]),
            )
            conn.commit()
            with authenticated_user:
                resp, data = _get(authenticated_user.client, TGT, person="me")
            assert resp.status_code == 200 and data["success"]
            assert {p["session_instance_id"] for p in data["play_instances"]} == {INST_A}
        finally:
            cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = %s", (INST_A,))
            conn.commit()
            cur.close()
            conn.close()
