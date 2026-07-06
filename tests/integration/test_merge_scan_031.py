"""
Integration tests for the merged-tune scan (spec 031).

Three groups:

1. check_tune() classification — pure HTTP-mock tests of the detection matrix
   (200 / 3xx chains / 404 / retryable errors / alias fetch), no DB.

2. run_scan() — the thread body against the real DB, with requests mocked.
   run_scan opens its own connection, so these use COMMITTED fixture tunes in
   the 999-million id block with the scan cursor parked just below them: the
   worklist is exactly the fixture tunes (which also exercises resume-from-
   cursor for free).

3. HTTP endpoints — start/409/resume/cancel/wipe lifecycle, the punchlist
   payload (ordering, break exclusion, done-detection, tombstoned-target
   resolution, ignore semantics), and merge_tune's auto-import of a missing
   target. Committed fixtures in the 95xx block, deleted in teardown
   (mirroring test_tune_merge_030.py's isolation pattern).
"""

import json
from unittest.mock import patch

import pytest

import services.tune_merge_scan_service as scan_svc
from database import get_db_connection

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------- #
# HTTP fakes
# --------------------------------------------------------------------------- #

class FakeResp:
    def __init__(self, status, location=None, json_data=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def fake_requests(routes, calls=None):
    """Build a requests.request replacement from {(method, url): resp-or-list}.
    A list value is consumed one response per call (for retry sequences).
    Unrouted URLs 200. `calls` (if given) collects (method, url)."""
    state = {k: list(v) if isinstance(v, list) else v for k, v in routes.items()}

    def _request(method, url, **kwargs):
        if calls is not None:
            calls.append((method, url))
        resp = state.get((method, url), FakeResp(200))
        if isinstance(resp, list):
            resp = resp.pop(0) if len(resp) > 1 else resp[0]
        if isinstance(resp, Exception):
            raise resp
        return resp

    return _request


@pytest.fixture(autouse=True)
def fast_scan(monkeypatch):
    """No polite delays or retry backoff sleeps inside tests."""
    monkeypatch.setenv("THESESSION_SCAN_DELAY_MS", "0")
    monkeypatch.setattr(scan_svc, "RETRY_DELAY", 0)


def tune_url(tid):
    return f"https://thesession.org/tunes/{tid}"


# --------------------------------------------------------------------------- #
# 1. check_tune classification (no DB)
# --------------------------------------------------------------------------- #

def test_check_tune_200_is_not_stored():
    with patch.object(scan_svc.requests, "request", fake_requests({})):
        assert scan_svc.check_tune(101) is None


def test_check_tune_merged_parses_target_and_fetches_aliases():
    calls = []
    routes = {
        ("HEAD", tune_url(101)): FakeResp(301, location="/tunes/202"),
        ("HEAD", tune_url(202)): FakeResp(200),
        ("GET", tune_url(202) + "?format=json"): FakeResp(
            200, json_data={"id": 202, "name": "The Blue Ribbon",
                            "aliases": ["Sonny Riordan's"]}),
    }
    with patch.object(scan_svc.requests, "request", fake_requests(routes, calls)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "merged"
    assert result["target_tune_id"] == 202
    assert result["target_name"] == "The Blue Ribbon"
    assert json.loads(result["target_aliases"]) == ["Sonny Riordan's"]
    assert ("GET", tune_url(202) + "?format=json") in calls


def test_check_tune_follows_chained_redirects():
    routes = {
        ("HEAD", tune_url(101)): FakeResp(301, location="/tunes/202"),
        ("HEAD", tune_url(202)): FakeResp(301, location="https://thesession.org/tunes/303"),
        ("HEAD", tune_url(303)): FakeResp(200),
        ("GET", tune_url(303) + "?format=json"): FakeResp(200, json_data={"name": "Final", "aliases": []}),
    }
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "merged"
    assert result["target_tune_id"] == 303


def test_check_tune_chain_too_long_is_error():
    routes = {
        ("HEAD", tune_url(101)): FakeResp(301, location="/tunes/102"),
        ("HEAD", tune_url(102)): FakeResp(301, location="/tunes/103"),
        ("HEAD", tune_url(103)): FakeResp(301, location="/tunes/104"),
        ("HEAD", tune_url(104)): FakeResp(301, location="/tunes/105"),
    }
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "error"
    assert "chain" in result["detail"]


def test_check_tune_404_is_deleted():
    routes = {("HEAD", tune_url(101)): FakeResp(404)}
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "deleted"


def test_check_tune_network_error_retried_then_stored():
    import requests as real_requests
    calls = []
    routes = {("HEAD", tune_url(101)): real_requests.ConnectionError("boom")}
    with patch.object(scan_svc.requests, "request", fake_requests(routes, calls)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "error"
    assert "attempts" in result["detail"]
    assert len(calls) == scan_svc.MAX_RETRIES


def test_check_tune_5xx_retried_then_recovers():
    routes = {("HEAD", tune_url(101)): [FakeResp(503), FakeResp(200)]}
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        assert scan_svc.check_tune(101) is None


def test_check_tune_alias_fetch_failure_does_not_fail_row():
    import requests as real_requests
    routes = {
        ("HEAD", tune_url(101)): FakeResp(301, location="/tunes/202"),
        ("HEAD", tune_url(202)): FakeResp(200),
        ("GET", tune_url(202) + "?format=json"): real_requests.ConnectionError("boom"),
    }
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        result = scan_svc.check_tune(101)
    assert result["result_type"] == "merged"
    assert result["target_tune_id"] == 202
    assert result["target_name"] is None
    assert result["target_aliases"] is None


def test_scan_delay_env_override(monkeypatch):
    monkeypatch.setenv("THESESSION_SCAN_DELAY_MS", "250")
    assert scan_svc.scan_delay_seconds() == 0.25
    monkeypatch.delenv("THESESSION_SCAN_DELAY_MS")
    assert scan_svc.scan_delay_seconds() == 1.0


def test_throttle_spaces_requests(monkeypatch):
    monkeypatch.setenv("THESESSION_SCAN_DELAY_MS", "1000")
    sleeps = []
    monkeypatch.setattr(scan_svc.time, "sleep", sleeps.append)
    throttle = scan_svc._Throttle()
    throttle.wait()   # first request: no prior request to space from... (t0=0 epoch)
    throttle.wait()   # second must wait ~the full delay
    assert sleeps and sleeps[-1] > 0.9


# --------------------------------------------------------------------------- #
# 2. run_scan against the DB (committed fixtures; cursor parks the worklist
#    on the 999-million block so seeded tunes are never touched)
# --------------------------------------------------------------------------- #

BLOCK = 999000000
S_MERGED, S_OK, S_GONE = BLOCK + 1, BLOCK + 2, BLOCK + 3
S_TARGET = BLOCK + 100


@pytest.fixture
def scan_run_fixture():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES "
        "(%s, 'Scan Merged', 'Reel'), (%s, 'Scan Fine', 'Reel'), (%s, 'Scan Gone', 'Reel')",
        (S_MERGED, S_OK, S_GONE),
    )
    cur.execute(
        """
        INSERT INTO tune_merge_scan (status, cursor_tune_id, total_count, checked_count)
        VALUES ('running', %s, 3, 0) RETURNING scan_id
        """,
        (BLOCK,),
    )
    scan_id = cur.fetchone()[0]
    conn.commit()

    yield scan_id

    cur.execute("DELETE FROM tune_merge_scan")  # cascades results
    cur.execute("DELETE FROM tune WHERE tune_id > %s", (BLOCK,))
    conn.commit()
    cur.close()
    conn.close()


RUN_ROUTES = {
    ("HEAD", tune_url(S_MERGED)): FakeResp(301, location=f"/tunes/{S_TARGET}"),
    ("HEAD", tune_url(S_TARGET)): FakeResp(200),
    ("GET", tune_url(S_TARGET) + "?format=json"): FakeResp(
        200, json_data={"name": "Scan Target", "aliases": ["Alt Title"]}),
    ("HEAD", tune_url(S_GONE)): FakeResp(404),
}


def _fetch_scan_row(scan_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status, cursor_tune_id, checked_count, merged_count, deleted_count,
               error_count, finished_at
        FROM tune_merge_scan WHERE scan_id = %s
        """,
        (scan_id,),
    )
    row = cur.fetchone()
    cur.execute(
        "SELECT tune_id, result_type, target_tune_id, target_name FROM tune_merge_scan_result "
        "WHERE scan_id = %s ORDER BY tune_id",
        (scan_id,),
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return row, results


def test_run_scan_completes_and_stores_only_interesting_results(scan_run_fixture):
    calls = []
    with patch.object(scan_svc.requests, "request", fake_requests(RUN_ROUTES, calls)):
        scan_svc.run_scan(scan_run_fixture)

    (status, cursor, checked, merged, deleted, errors, finished), results = _fetch_scan_row(scan_run_fixture)
    assert status == "completed"
    assert finished is not None
    assert (checked, merged, deleted, errors) == (3, 1, 1, 0)
    assert cursor == S_GONE  # last checked id
    # 200s not stored; merged + deleted are.
    assert results == [
        (S_MERGED, "merged", S_TARGET, "Scan Target"),
        (S_GONE, "deleted", None, None),
    ]


def test_run_scan_resumes_from_cursor_without_refetching(scan_run_fixture):
    # Park the cursor past S_MERGED: only S_OK and S_GONE may be requested.
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tune_merge_scan SET cursor_tune_id = %s, checked_count = 1 WHERE scan_id = %s",
                (S_MERGED, scan_run_fixture))
    conn.commit()
    cur.close()
    conn.close()

    calls = []
    with patch.object(scan_svc.requests, "request", fake_requests(RUN_ROUTES, calls)):
        scan_svc.run_scan(scan_run_fixture)

    requested = {url for _, url in calls}
    assert tune_url(S_MERGED) not in requested
    (status, _, checked, _, deleted, _, _), _ = _fetch_scan_row(scan_run_fixture)
    assert status == "completed"
    assert checked == 3  # 1 from before the interruption + 2 now


def test_run_scan_cancel_exits_promptly(scan_run_fixture):
    def cancelling_request(method, url, **kwargs):
        # First request cancels the scan from "another worker": the loop must
        # notice on its next iteration and stop without finishing the worklist.
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tune_merge_scan SET status = 'cancelled' WHERE scan_id = %s",
                    (scan_run_fixture,))
        conn.commit()
        cur.close()
        conn.close()
        return FakeResp(200)

    with patch.object(scan_svc.requests, "request", cancelling_request):
        scan_svc.run_scan(scan_run_fixture)

    (status, _, checked, *_), _ = _fetch_scan_row(scan_run_fixture)
    assert status == "cancelled"
    assert checked == 1


def test_run_scan_noops_when_not_running(scan_run_fixture):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tune_merge_scan SET status = 'cancelled' WHERE scan_id = %s", (scan_run_fixture,))
    conn.commit()
    cur.close()
    conn.close()

    calls = []
    with patch.object(scan_svc.requests, "request", fake_requests(RUN_ROUTES, calls)):
        scan_svc.run_scan(scan_run_fixture)
    assert calls == []


# --------------------------------------------------------------------------- #
# 3. HTTP endpoints (committed fixtures, 95xx block)
# --------------------------------------------------------------------------- #

T_MERGED = 9501    # merged upstream -> T_REMOTE (not local)
T_DONE = 9502      # merged upstream -> T_CANON; already merged locally (done)
T_TOMB = 9503      # merged upstream -> T_LOCAL_OLD, which is tombstoned into T_CANON
T_GONE = 9504      # deleted upstream
T_CANON = 9510     # local canonical survivor
T_LOCAL_OLD = 9511 # local redirect -> T_CANON
T_REMOTE = 9601    # upstream target that does NOT exist locally
SID = 9500
INST = 9590


@pytest.fixture
def scan_env():
    """Committed scan + results + usage rows; wiped in teardown."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES "
        "(%s, 'High Impact', 'Reel'), (%s, 'Already Done', 'Reel'), "
        "(%s, 'Tomb Target Case', 'Reel'), (%s, 'Gone Upstream', 'Reel'), "
        "(%s, 'The Canonical', 'Reel')",
        (T_MERGED, T_DONE, T_TOMB, T_GONE, T_CANON),
    )
    cur.execute("INSERT INTO tune (tune_id, name, tune_type, redirect_to_tune_id) VALUES (%s, 'Local Old', 'Reel', %s)",
                (T_LOCAL_OLD, T_CANON))
    cur.execute("UPDATE tune SET redirect_to_tune_id = %s WHERE tune_id = %s", (T_CANON, T_DONE))

    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Scan031', 'scan031-test')", (SID,))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')",
                (INST, SID))
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, T_MERGED))
    # T_MERGED: 3 plays + 1 break row (break must NOT count); T_TOMB: 1 play.
    cur.execute(
        """
        INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) VALUES
        (%s, %s, 'a0', 'tune'), (%s, %s, 'a1', 'tune'), (%s, %s, 'a2', 'tune'),
        (%s, %s, 'a3', 'break'),
        (%s, %s, 'a4', 'tune')
        """,
        (INST, T_MERGED, INST, T_MERGED, INST, T_MERGED, INST, T_MERGED, INST, T_TOMB),
    )

    cur.execute(
        "INSERT INTO tune_merge_scan (status, total_count, checked_count, merged_count, deleted_count) "
        "VALUES ('completed', 4, 4, 3, 1) RETURNING scan_id"
    )
    scan_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO tune_merge_scan_result (scan_id, tune_id, result_type, target_tune_id, target_name, target_aliases, detail) VALUES
        (%s, %s, 'merged', %s, 'The Remote Target', '["Sonny Riordan''s"]'::jsonb, 'HTTP 301'),
        (%s, %s, 'merged', %s, 'The Canonical', NULL, 'HTTP 301'),
        (%s, %s, 'merged', %s, 'Local Old', NULL, 'HTTP 301'),
        (%s, %s, 'deleted', NULL, NULL, NULL, '404')
        """,
        (scan_id, T_MERGED, T_REMOTE,
         scan_id, T_DONE, T_CANON,
         scan_id, T_TOMB, T_LOCAL_OLD,
         scan_id, T_GONE),
    )
    conn.commit()

    yield {"scan_id": scan_id, "conn": conn}

    cur.execute("DELETE FROM tune_merge_scan")
    cur.execute("DELETE FROM tune_merge_ignore WHERE tune_id BETWEEN 9500 AND 9699")
    cur.execute("DELETE FROM session_instance_tune_history WHERE tune_id BETWEEN 9500 AND 9699")
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_tune_alias_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune_alias WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM tune_setting WHERE tune_id BETWEEN 9500 AND 9699")
    cur.execute("DELETE FROM tune_history WHERE tune_id BETWEEN 9500 AND 9699")
    cur.execute("UPDATE tune SET redirect_to_tune_id = NULL WHERE tune_id BETWEEN 9500 AND 9699")
    cur.execute("DELETE FROM tune WHERE tune_id BETWEEN 9500 AND 9699")
    conn.commit()
    cur.close()
    conn.close()


def _get_scan(client):
    resp = client.get("/api/admin/tunes/merge-scan")
    assert resp.status_code == 200
    return resp.get_json()


def test_get_punchlist_payload(client, admin_user, scan_env):
    with admin_user:
        body = _get_scan(client)

    assert body["success"] is True
    assert body["scan"]["status"] == "completed"
    assert body["scan"]["stale"] is False

    punch = body["punchlist"]
    ids = [p["tune_id"] for p in punch]
    # Ordered by plays desc: T_MERGED (3 plays; break excluded) before T_TOMB (1).
    assert ids.index(T_MERGED) < ids.index(T_TOMB)
    by_id = {p["tune_id"]: p for p in punch}

    high = by_id[T_MERGED]
    assert high["plays_count"] == 3          # break row excluded
    assert high["sessions_count"] == 1
    assert high["target_is_local"] is False  # will be imported
    assert high["target_name"] == "The Remote Target"
    assert high["target_aliases"] == ["Sonny Riordan's"]
    assert high["done"] is False

    # Completed merge renders done via join, not result mutation.
    assert by_id[T_DONE]["done"] is True

    # Locally-tombstoned target resolves to the canonical tune with a note.
    tomb = by_id[T_TOMB]
    assert tomb["target_tune_id"] == T_LOCAL_OLD
    assert tomb["resolved_target_tune_id"] == T_CANON
    assert tomb["resolved_target_name"] == "The Canonical"
    assert "merged locally" in tomb["resolved_note"]

    # 404s are informational, in their own section.
    assert [d["tune_id"] for d in body["deleted"]] == [T_GONE]
    assert body["has_unactioned"] is True


def test_ignore_hides_row_and_unignore_restores(client, admin_user, scan_env):
    with admin_user:
        resp = client.post("/api/admin/tunes/merge-scan/ignore",
                           json={"tune_id": T_MERGED, "target_tune_id": T_REMOTE})
        assert resp.get_json()["success"] is True
        # Idempotent re-ignore.
        resp = client.post("/api/admin/tunes/merge-scan/ignore",
                           json={"tune_id": T_MERGED, "target_tune_id": T_REMOTE})
        assert resp.get_json()["success"] is True

        body = _get_scan(client)
        assert T_MERGED not in [p["tune_id"] for p in body["punchlist"]]
        assert T_MERGED in [i["tune_id"] for i in body["ignored"]]

        resp = client.delete("/api/admin/tunes/merge-scan/ignore",
                             json={"tune_id": T_MERGED, "target_tune_id": T_REMOTE})
        assert resp.get_json()["success"] is True
        body = _get_scan(client)
        assert T_MERGED in [p["tune_id"] for p in body["punchlist"]]


def test_null_target_ignore_hides_deleted_row(client, admin_user, scan_env):
    with admin_user:
        client.post("/api/admin/tunes/merge-scan/ignore", json={"tune_id": T_GONE})
        body = _get_scan(client)
        assert body["deleted"] == []
        assert T_GONE in [i["tune_id"] for i in body["ignored"]]


def test_changed_upstream_target_reappears_despite_ignore(client, admin_user, scan_env):
    with admin_user:
        client.post("/api/admin/tunes/merge-scan/ignore",
                    json={"tune_id": T_MERGED, "target_tune_id": T_REMOTE})
    # Next scan finds a DIFFERENT upstream target for the same tune.
    cur = scan_env["conn"].cursor()
    cur.execute(
        "UPDATE tune_merge_scan_result SET target_tune_id = %s WHERE scan_id = %s AND tune_id = %s",
        (T_REMOTE + 1, scan_env["scan_id"], T_MERGED),
    )
    scan_env["conn"].commit()
    cur.close()

    with admin_user:
        body = _get_scan(client)
    assert T_MERGED in [p["tune_id"] for p in body["punchlist"]]


def test_scan_endpoints_require_admin(client, authenticated_regular_user, scan_env):
    with authenticated_regular_user:
        assert client.get("/api/admin/tunes/merge-scan").status_code == 403
        assert client.post("/api/admin/tunes/merge-scan", json={}).status_code == 403
        assert client.delete("/api/admin/tunes/merge-scan").status_code == 403
        assert client.post("/api/admin/tunes/merge-scan/ignore", json={"tune_id": 1}).status_code == 403


def _set_scan_running(scan_env, heartbeat_age_seconds):
    cur = scan_env["conn"].cursor()
    cur.execute(
        """
        UPDATE tune_merge_scan
        SET status = 'running', finished_at = NULL,
            heartbeat_at = (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s)
        WHERE scan_id = %s
        """,
        (heartbeat_age_seconds, scan_env["scan_id"]),
    )
    scan_env["conn"].commit()
    cur.close()


def test_double_start_blocked_while_heartbeat_fresh(client, admin_user, scan_env):
    _set_scan_running(scan_env, 0)
    with admin_user:
        resp = client.post("/api/admin/tunes/merge-scan", json={})
        assert resp.status_code == 409
        resp = client.post("/api/admin/tunes/merge-scan", json={"resume": True})
        assert resp.status_code == 409


def test_resume_stale_scan_refreshes_heartbeat_and_spawns(client, admin_user, scan_env):
    _set_scan_running(scan_env, 600)
    with admin_user:
        body = _get_scan(client)
        assert body["scan"]["stale"] is True

        with patch.object(scan_svc, "start_scan_thread") as spawn:
            resp = client.post("/api/admin/tunes/merge-scan", json={"resume": True})
        assert resp.status_code == 200
        assert resp.get_json()["resumed"] is True
        spawn.assert_called_once_with(scan_env["scan_id"])

        body = _get_scan(client)
        assert body["scan"]["stale"] is False
        # Results from before the interruption are still there.
        assert len(body["punchlist"]) == 3


def test_resume_without_interrupted_scan_400(client, admin_user, scan_env):
    with admin_user:
        resp = client.post("/api/admin/tunes/merge-scan", json={"resume": True})
    assert resp.status_code == 400


def test_new_scan_wipes_old_results(client, admin_user, scan_env):
    with admin_user:
        with patch.object(scan_svc, "start_scan_thread") as spawn:
            resp = client.post("/api/admin/tunes/merge-scan", json={})
        assert resp.status_code == 200
        new_scan_id = resp.get_json()["scan_id"]
        assert new_scan_id != scan_env["scan_id"]
        spawn.assert_called_once_with(new_scan_id)

        body = _get_scan(client)
        assert body["scan"]["scan_id"] == new_scan_id
        assert body["scan"]["status"] == "running"
        assert body["punchlist"] == [] and body["deleted"] == []
        assert body["scan"]["total_count"] > 0


def test_cancel_running_scan(client, admin_user, scan_env):
    _set_scan_running(scan_env, 0)
    with admin_user:
        resp = client.delete("/api/admin/tunes/merge-scan")
        assert resp.get_json()["success"] is True
        body = _get_scan(client)
        assert body["scan"]["status"] == "cancelled"
        # Nothing left to cancel.
        assert client.delete("/api/admin/tunes/merge-scan").status_code == 404


# --------------------------------------------------------------------------- #
# merge_tune auto-import of a missing target (spec 031 #10)
# --------------------------------------------------------------------------- #

def test_merge_preview_announces_import(client, admin_user, scan_env):
    with admin_user:
        with patch("api_routes._fetch_thesession_tune",
                   return_value={"name": "The Imported Reel", "type": "reel"}), \
             patch("api_routes._verify_thesession_redirect",
                   return_value={"status": "confirmed", "message": "Confirmed."}):
            resp = client.post("/api/admin/tunes/merge",
                               json={"old_tune_id": T_MERGED, "new_tune_id": T_REMOTE})
    body = resp.get_json()
    assert body["success"] is True and body["preview"] is True
    assert body["will_import"] is True
    assert body["new_tune"] == {"tune_id": T_REMOTE, "name": "The Imported Reel", "type": "Reel"}
    assert any("will be imported" in w for w in body["warnings"])


def test_merge_confirm_imports_and_merges_atomically(client, admin_user, scan_env):
    with admin_user:
        with patch("live_logging_routes._fetch_thesession_tune",
                   return_value={"name": "The Imported Reel", "type": "reel",
                                 "tunebooks": 7, "settings": []}):
            resp = client.post("/api/admin/tunes/merge",
                               json={"old_tune_id": T_MERGED, "new_tune_id": T_REMOTE,
                                     "confirm": True})
    body = resp.get_json()
    assert body["success"] is True
    assert body["imported_target"] is True

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, redirect_to_tune_id FROM tune WHERE tune_id = %s", (T_REMOTE,))
    assert cur.fetchone() == ("The Imported Reel", None)
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (T_MERGED,))
    assert cur.fetchone()[0] == T_REMOTE
    # Usage rows moved to the imported tune.
    cur.execute("SELECT COUNT(*) FROM session_tune WHERE session_id = %s AND tune_id = %s", (SID, T_REMOTE))
    assert cur.fetchone()[0] == 1
    cur.close()
    conn.close()


def test_merge_confirm_failed_import_rolls_back_everything(client, admin_user, scan_env):
    from api_routes import TuneImportError

    with admin_user:
        with patch("live_logging_routes._fetch_thesession_tune",
                   side_effect=TuneImportError("Tune not found on thesession.org", 404)):
            resp = client.post("/api/admin/tunes/merge",
                               json={"old_tune_id": T_MERGED, "new_tune_id": T_REMOTE,
                                     "confirm": True})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tune WHERE tune_id = %s", (T_REMOTE,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (T_MERGED,))
    assert cur.fetchone()[0] is None
    cur.close()
    conn.close()
