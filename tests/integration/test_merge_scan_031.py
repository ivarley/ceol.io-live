"""
Integration tests for the thesession.org merge sync (spec 031).

Four groups:

1. check_tune() classification — pure HTTP-mock tests of the live detection
   matrix (200 / 3xx chains / 404 / retryable errors / alias fetch), no DB.

2. _fetch_dump() / _trace_via_settings() — dump parsing and the site owner's
   settings-diff recipe, against small fake CSV bodies.

3. run_sync() — the full weekly-run pipeline against the real DB with all HTTP
   mocked: dump diff -> settings-trace/live resolve -> live verify ->
   AUTO-APPLY via merge_tune_ids -> record rows. Committed fixtures in the
   999-million tune-id block (far above real thesession ids), deleted in
   teardown.

4. HTTP endpoints (Run Now / record GET / cancel) and merge_tune's
   auto-import of a missing target. Committed fixtures in the 95xx block.
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
    def __init__(self, status, location=None, json_data=None, text=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self._json = json_data
        self._text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def iter_lines(self, decode_unicode=False):
        return iter((self._text or "").splitlines())


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
    """No polite delays, no retry backoff sleeps, and accept tiny fake dumps."""
    monkeypatch.setenv("THESESSION_SCAN_DELAY_MS", "0")
    monkeypatch.setattr(scan_svc, "RETRY_DELAY", 0)
    monkeypatch.setattr(scan_svc, "MIN_DUMP_TUNES", 0)


def tune_url(tid):
    return f"https://thesession.org/tunes/{tid}"


def dump_routes(tunes_rows, aliases_rows=()):
    """Fake dump responses. tunes_rows: (tune_id, setting_id, name) triples;
    aliases_rows: (tune_id, alias) pairs."""
    tunes_csv = "tune_id,setting_id,name,type,meter,mode,abc,date,username,composer\n"
    tunes_csv += "".join(
        f'{t},{s},"{n}",reel,4/4,Gmajor,"|:abc:|","2020-01-01 00:00:00",someone,\n'
        for t, s, n in tunes_rows)
    aliases_csv = "tune_id,alias,name\n"
    aliases_csv += "".join(f'{t},"{a}",""\n' for t, a in aliases_rows)
    return {
        ("GET", scan_svc.DUMP_TUNES_URL): FakeResp(200, text=tunes_csv),
        ("GET", scan_svc.DUMP_ALIASES_URL): FakeResp(200, text=aliases_csv),
    }


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
    throttle.wait()   # first request: no prior request to space from
    throttle.wait()   # second must wait ~the full delay
    assert sleeps and sleeps[-1] > 0.9


# --------------------------------------------------------------------------- #
# 2. Dump parsing + settings-trace (no HTTP beyond the fakes)
# --------------------------------------------------------------------------- #

def test_fetch_dump_parses_ids_settings_and_aliases():
    routes = dump_routes(
        [(1, 10, "Cooley's"), (1, 11, "Cooley's"), (2, 20, "The Kesh")],
        [(1, "The Tulla Reel"), (1, "Joe Cooley's"), (2, "Kesh Jig")])
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        live_ids, setting_map, aliases_map = scan_svc._fetch_dump(scan_svc._Throttle())
    assert live_ids == {1, 2}
    assert setting_map[11] == (1, "Cooley's")
    assert setting_map[20] == (2, "The Kesh")
    assert aliases_map[1] == ["The Tulla Reel", "Joe Cooley's"]


def test_fetch_dump_rejects_truncated_dump(monkeypatch):
    monkeypatch.setattr(scan_svc, "MIN_DUMP_TUNES", 50)
    routes = dump_routes([(1, 10, "Only Tune")])
    with patch.object(scan_svc.requests, "request", fake_requests(routes)):
        with pytest.raises(RuntimeError, match="truncated"):
            scan_svc._fetch_dump(scan_svc._Throttle())


def test_trace_via_settings_single_target(db_cursor):
    db_cursor.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (9451, 'Traced', 'Reel')")
    db_cursor.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (94511, 9451, 'D', 'abc')")
    setting_map = {94511: (777, "The Target")}
    result = scan_svc._trace_via_settings(db_cursor, 9451, setting_map, {777: ["Alt"]})
    assert result["result_type"] == "merged"
    assert result["target_tune_id"] == 777
    assert result["target_name"] == "The Target"
    assert json.loads(result["target_aliases"]) == ["Alt"]
    assert "settings-trace" in result["detail"]


def test_trace_via_settings_ambiguous_or_absent_returns_none(db_cursor):
    db_cursor.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (9452, 'Split', 'Reel')")
    db_cursor.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES "
        "(94521, 9452, 'D', 'abc'), (94522, 9452, 'G', 'abc')")
    # Settings split across two different targets -> ambiguous.
    setting_map = {94521: (777, "A"), 94522: (888, "B")}
    assert scan_svc._trace_via_settings(db_cursor, 9452, setting_map, {}) is None
    # Settings absent from the dump entirely -> nothing to trace.
    assert scan_svc._trace_via_settings(db_cursor, 9452, {}, {}) is None


# --------------------------------------------------------------------------- #
# 3. run_sync against the DB (committed fixtures in the 999M block)
# --------------------------------------------------------------------------- #

BLOCK = 999000000
S_ALIVE = BLOCK + 1     # in dump: untouched, no requests
S_TRACED = BLOCK + 2    # absent; cached setting found under S_TARGET -> auto-applied
S_UNTRACED = BLOCK + 3  # absent, no settings; live 301 -> S_NEW (not local) -> import+apply
S_GONE = BLOCK + 4      # absent; live 404 -> recorded deleted
S_FRESH = BLOCK + 5     # absent from dump (imported "after Sunday"); live 200 -> untouched
S_ERR = BLOCK + 6       # absent; live HEAD errors -> recorded error
S_TARGET = BLOCK + 100  # local, in dump; traced merge target
S_NEW = BLOCK + 200     # NOT local, in dump; live-resolved merge target (imported)
SET_TRACED = BLOCK + 900001   # S_TRACED's cached setting id, in dump under S_TARGET
SYNC_SID = 9501
SYNC_INST = 9591


@pytest.fixture
def sync_env():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type) VALUES "
        "(%s, 'Alive', 'Reel'), (%s, 'Traced Away', 'Reel'), (%s, 'Untraced Away', 'Reel'), "
        "(%s, 'Gone Upstream', 'Reel'), (%s, 'Fresh Import', 'Reel'), (%s, 'Flaky', 'Reel'), "
        "(%s, 'The Target', 'Reel')",
        (S_ALIVE, S_TRACED, S_UNTRACED, S_GONE, S_FRESH, S_ERR, S_TARGET),
    )
    cur.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'D', 'abc')",
        (SET_TRACED, S_TRACED),
    )
    # Usage that the applied merge must carry to the target.
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Sync031', 'sync031-test')", (SYNC_SID,))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')",
                (SYNC_INST, SYNC_SID))
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SYNC_SID, S_TRACED))
    cur.execute(
        "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) "
        "VALUES (%s, %s, 'a0', 'tune')",
        (SYNC_INST, S_UNTRACED),
    )
    conn.commit()

    yield {"conn": conn}

    cur.execute("DELETE FROM tune_merge_scan")
    cur.execute("DELETE FROM session_instance_tune_history WHERE tune_id > %s", (BLOCK,))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (SYNC_INST,))
    cur.execute("DELETE FROM session_tune_alias_history WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM session_tune_alias WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (SYNC_INST,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SYNC_SID,))
    cur.execute("DELETE FROM tune_setting WHERE tune_id > %s OR setting_id > %s", (BLOCK, BLOCK))
    cur.execute("DELETE FROM tune_history WHERE tune_id > %s", (BLOCK,))
    cur.execute("UPDATE tune SET redirect_to_tune_id = NULL WHERE tune_id > %s", (BLOCK,))
    cur.execute("DELETE FROM tune WHERE tune_id > %s", (BLOCK,))
    conn.commit()
    cur.close()
    conn.close()


def _sync_routes():
    """The full mocked upstream for a run: dump + live responses."""
    routes = dump_routes(
        # Everything still alive upstream, including both merge targets; the
        # traced setting now lives under S_TARGET.
        [(S_ALIVE, BLOCK + 900010, "Alive"),
         (S_TARGET, SET_TRACED, "The Target"),
         (S_TARGET, BLOCK + 900011, "The Target"),
         (S_NEW, BLOCK + 900012, "The New Target"),
         (S_FRESH + 90, BLOCK + 900013, "Padding Tune")],
        [(S_TARGET, "Target Alias")])
    routes.update({
        # Verification GET for the traced pair.
        ("GET", tune_url(S_TRACED) + "?format=json"): FakeResp(301, location=f"/tunes/{S_TARGET}"),
        # Live resolution for the untraced tune.
        ("HEAD", tune_url(S_UNTRACED)): FakeResp(301, location=f"/tunes/{S_NEW}"),
        ("HEAD", tune_url(S_NEW)): FakeResp(200),
        ("GET", tune_url(S_NEW) + "?format=json"): FakeResp(
            200, json_data={"id": S_NEW, "name": "The New Target", "aliases": ["New Alias"]}),
        ("HEAD", tune_url(S_GONE)): FakeResp(404),
        ("HEAD", tune_url(S_FRESH)): FakeResp(200),
        ("HEAD", tune_url(S_ERR)): __import__("requests").ConnectionError("boom"),
    })
    return routes


def _run_once(routes, calls=None):
    scan_id = scan_svc.create_run()
    assert scan_id is not None
    with patch.object(scan_svc.requests, "request", fake_requests(routes, calls)), \
         patch("live_logging_routes._fetch_thesession_tune",
               return_value={"name": "The New Target", "type": "reel", "tunebooks": 5, "settings": []}):
        scan_svc.run_sync(scan_id)
    return scan_id


def _scan_row(scan_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status, total_count, checked_count, merged_count, applied_count,
               deleted_count, error_count
        FROM tune_merge_scan WHERE scan_id = %s
        """,
        (scan_id,),
    )
    row = cur.fetchone()
    cur.execute(
        "SELECT tune_id, result_type, target_tune_id, target_name, detail, applied_at "
        "FROM tune_merge_scan_result WHERE scan_id = %s ORDER BY tune_id",
        (scan_id,),
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return row, results


def test_run_sync_applies_merges_and_records(sync_env):
    calls = []
    scan_id = _run_once(_sync_routes(), calls)

    (status, total, checked, merged, applied, deleted, errors), results = _scan_row(scan_id)
    assert status == "completed"
    assert checked == total
    assert (merged, applied, deleted, errors) == (2, 2, 1, 1)

    by_id = {r[0]: r for r in results}
    # Traced merge: applied, dump-sourced target name, settings-trace detail.
    _, rtype, target, name, detail, applied_at = by_id[S_TRACED]
    assert (rtype, target, name) == ("merged", S_TARGET, "The Target")
    assert "settings-trace" in detail and "applied" in detail
    assert applied_at is not None
    # Untraced merge: live-resolved, target imported.
    _, rtype, target, name, detail, applied_at = by_id[S_UNTRACED]
    assert (rtype, target, name) == ("merged", S_NEW, "The New Target")
    assert "target imported" in detail and applied_at is not None
    assert by_id[S_GONE][1] == "deleted"
    assert by_id[S_ERR][1] == "error"
    assert S_FRESH not in by_id and S_ALIVE not in by_id

    # The merges actually happened.
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (S_TRACED,))
    assert cur.fetchone()[0] == S_TARGET
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (S_UNTRACED,))
    assert cur.fetchone()[0] == S_NEW
    cur.execute("SELECT name FROM tune WHERE tune_id = %s", (S_NEW,))
    assert cur.fetchone() == ("The New Target",)  # imported
    cur.execute("SELECT tune_id FROM session_tune WHERE session_id = %s", (SYNC_SID,))
    assert cur.fetchone()[0] == S_TARGET  # usage moved
    cur.execute("SELECT tune_id FROM session_instance_tune WHERE session_instance_id = %s", (SYNC_INST,))
    assert cur.fetchone()[0] == S_NEW
    cur.close()
    conn.close()

    # Tunes present in the dump were never requested live.
    requested = {url for _, url in calls}
    assert tune_url(S_ALIVE) not in requested
    assert tune_url(S_TARGET) not in requested


def test_run_sync_second_run_dedupes_deleted_and_replaces_error(sync_env):
    first = _run_once(_sync_routes())
    second = _run_once(_sync_routes())

    (status, _, _, merged, applied, deleted, errors), results = _scan_row(second)
    assert status == "completed"
    # The applied merges are gone from the worklist; the deleted tune is not
    # re-recorded; the error retried and failed again.
    assert (merged, applied, deleted, errors) == (0, 0, 0, 1)
    assert [r[1] for r in results] == ["error"]

    # First run's record rows persist (retention), except the superseded error.
    _, first_results = _scan_row(first)
    types = sorted(r[1] for r in first_results)
    assert types == ["deleted", "merged", "merged"]

    # Across ALL runs there is exactly one deleted row and one error row.
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tune_merge_scan_result WHERE tune_id = %s AND result_type = 'deleted'", (S_GONE,))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT scan_id FROM tune_merge_scan_result WHERE tune_id = %s", (S_ERR,))
    rows = cur.fetchall()
    assert rows == [(second,)]
    cur.close()
    conn.close()


def test_run_sync_stale_trace_falls_back_to_live(sync_env):
    """Dump says S_TRACED's setting moved to S_TARGET, but live verification
    disagrees (tune still live upstream) -> no merge applied."""
    routes = _sync_routes()
    # Verification: still a live tune (200 with its own id).
    routes[("GET", tune_url(S_TRACED) + "?format=json")] = FakeResp(
        200, json_data={"id": S_TRACED, "name": "Traced Away"})
    # Fallback live check: alive.
    routes[("HEAD", tune_url(S_TRACED))] = FakeResp(200)
    scan_id = _run_once(routes)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (S_TRACED,))
    assert cur.fetchone()[0] is None  # untouched
    cur.execute(
        "SELECT COUNT(*) FROM tune_merge_scan_result WHERE scan_id = %s AND tune_id = %s",
        (scan_id, S_TRACED))
    assert cur.fetchone()[0] == 0
    cur.close()
    conn.close()


def test_run_sync_apply_failure_records_error(sync_env):
    """Import of the missing target blows up -> transaction rolled back,
    error row recorded, nothing half-applied."""
    from api_routes import TuneImportError
    routes = _sync_routes()
    scan_id = scan_svc.create_run()
    with patch.object(scan_svc.requests, "request", fake_requests(routes)), \
         patch("live_logging_routes._fetch_thesession_tune",
               side_effect=TuneImportError("thesession down", 502)):
        scan_svc.run_sync(scan_id)

    (status, _, _, merged, applied, _, errors), results = _scan_row(scan_id)
    assert status == "completed"
    assert applied == 1        # the traced merge (target already local) still applied
    assert errors >= 1
    by_id = {r[0]: r for r in results}
    assert by_id[S_UNTRACED][1] == "error"
    assert "apply failed" in by_id[S_UNTRACED][4]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tune WHERE tune_id = %s", (S_NEW,))
    assert cur.fetchone()[0] == 0  # import rolled back
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (S_UNTRACED,))
    assert cur.fetchone()[0] is None
    cur.close()
    conn.close()


def test_run_sync_truncated_dump_aborts_without_recording(sync_env, monkeypatch):
    monkeypatch.setattr(scan_svc, "MIN_DUMP_TUNES", 50)
    scan_id = scan_svc.create_run()
    with patch.object(scan_svc.requests, "request", fake_requests(_sync_routes())):
        scan_svc.run_sync(scan_id)

    (status, _, checked, *_), results = _scan_row(scan_id)
    # Thread-death semantics: left 'running' (stale heartbeat is the signal).
    assert status == "running"
    assert checked == 0
    assert results == []
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (S_TRACED,))
    assert cur.fetchone()[0] is None
    cur.close()
    conn.close()


def test_run_sync_cancel_mid_run(sync_env):
    scan_id = scan_svc.create_run()

    real_router = fake_requests(_sync_routes())

    def cancelling_request(method, url, **kwargs):
        # First live request cancels the run from "another worker".
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tune_merge_scan SET status = 'cancelled' WHERE scan_id = %s", (scan_id,))
        conn.commit()
        cur.close()
        conn.close()
        return real_router(method, url, **kwargs)

    with patch.object(scan_svc.requests, "request", cancelling_request):
        scan_svc.run_sync(scan_id)

    (status, *_), _ = _scan_row(scan_id)
    assert status == "cancelled"


def test_create_run_blocks_while_fresh_running(sync_env):
    first = scan_svc.create_run()
    assert first is not None
    assert scan_svc.create_run() is None  # fresh heartbeat -> blocked
    # Stale heartbeat -> a new run may start.
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tune_merge_scan SET heartbeat_at = heartbeat_at - INTERVAL '10 minutes' WHERE scan_id = %s",
        (first,))
    conn.commit()
    cur.close()
    conn.close()
    assert scan_svc.create_run() is not None


# --------------------------------------------------------------------------- #
# 4. HTTP endpoints + merge_tune auto-import (committed fixtures, 95xx block)
# --------------------------------------------------------------------------- #

T_MERGED = 9501    # merged upstream -> T_REMOTE (not local)
T_REMOTE = 9601    # upstream target that does NOT exist locally
SID = 9500
INST = 9590


@pytest.fixture
def merge_env():
    """Committed fixture for the manual merge endpoint + record endpoints."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'High Impact', 'Reel')", (T_MERGED,))
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Scan031', 'scan031-test')", (SID,))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-07-01')",
                (INST, SID))
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, T_MERGED))
    conn.commit()

    yield {"conn": conn}

    cur.execute("DELETE FROM tune_merge_scan")
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


def _insert_run(conn, status="completed", results=(), started_by=None, heartbeat_age=0):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tune_merge_scan (status, total_count, checked_count, started_by_user_id, heartbeat_at)
        VALUES (%s, 10, 10, %s, (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s))
        RETURNING scan_id
        """,
        (status, started_by, heartbeat_age),
    )
    scan_id = cur.fetchone()[0]
    for r in results:
        cur.execute(
            """
            INSERT INTO tune_merge_scan_result
                (scan_id, tune_id, result_type, target_tune_id, target_name, target_aliases, detail, applied_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (scan_id, r["tune_id"], r["result_type"], r.get("target_tune_id"),
             r.get("target_name"), r.get("target_aliases"), r.get("detail"),
             r.get("applied_at")),
        )
    conn.commit()
    cur.close()
    return scan_id


def test_run_now_endpoint_starts_and_409s(client, admin_user, merge_env):
    with admin_user:
        with patch.object(scan_svc, "start_scan_thread") as spawn:
            resp = client.post("/api/admin/tunes/merge-scan", json={})
        assert resp.status_code == 200
        scan_id = resp.get_json()["scan_id"]
        spawn.assert_called_once_with(scan_id)

        # Row is 'running' with a fresh heartbeat (thread was mocked away).
        resp = client.post("/api/admin/tunes/merge-scan", json={})
        assert resp.status_code == 409


def test_record_endpoint_returns_runs_with_results(client, admin_user, merge_env):
    conn = merge_env["conn"]
    older = _insert_run(conn, results=[
        {"tune_id": T_MERGED, "result_type": "merged", "target_tune_id": T_REMOTE,
         "target_name": "The Remote Target", "target_aliases": json.dumps(["Sonny Riordan's"]),
         "detail": "settings-trace (dump); target imported; applied",
         "applied_at": "2026-07-06 01:00:00+00"},
        {"tune_id": 9502, "result_type": "deleted", "detail": "404"},
    ])
    newer = _insert_run(conn, results=[
        {"tune_id": 9503, "result_type": "error", "detail": "HTTP 500 (after 3 attempts)"},
    ])

    with admin_user:
        resp = client.get("/api/admin/tunes/merge-scan")
    body = resp.get_json()
    assert body["success"] is True
    runs = body["runs"]
    assert [r["scan_id"] for r in runs[:2]] == [newer, older]

    older_run = runs[1]
    assert older_run["triggered_by"] == "weekly job"
    merged = [r for r in older_run["results"] if r["result_type"] == "merged"][0]
    assert merged["tune_name"] == "High Impact"
    assert merged["target_name"] == "The Remote Target"
    assert merged["applied"] is True
    assert merged["imported"] is True
    assert merged["target_aliases"] == ["Sonny Riordan's"]
    assert [r["result_type"] for r in runs[0]["results"]] == ["error"]


def test_cancel_endpoint(client, admin_user, merge_env):
    _insert_run(merge_env["conn"], status="running")
    with admin_user:
        resp = client.delete("/api/admin/tunes/merge-scan")
        assert resp.get_json()["success"] is True
        body = client.get("/api/admin/tunes/merge-scan").get_json()
        assert body["runs"][0]["status"] == "cancelled"
        assert client.delete("/api/admin/tunes/merge-scan").status_code == 404


def test_scan_endpoints_require_admin(client, authenticated_regular_user, merge_env):
    with authenticated_regular_user:
        assert client.get("/api/admin/tunes/merge-scan").status_code == 403
        assert client.post("/api/admin/tunes/merge-scan", json={}).status_code == 403
        assert client.delete("/api/admin/tunes/merge-scan").status_code == 403


# --------------------------------------------------------------------------- #
# merge_tune auto-import of a missing target (manual endpoint; spec 031 #10)
# --------------------------------------------------------------------------- #

def test_merge_preview_announces_import(client, admin_user, merge_env):
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


def test_merge_confirm_imports_and_merges_atomically(client, admin_user, merge_env):
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
    cur.execute("SELECT COUNT(*) FROM session_tune WHERE session_id = %s AND tune_id = %s", (SID, T_REMOTE))
    assert cur.fetchone()[0] == 1
    cur.close()
    conn.close()


def test_merge_confirm_failed_import_rolls_back_everything(client, admin_user, merge_env):
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


# --------------------------------------------------------------------------- #
# 5. the weekly schedule gate
# --------------------------------------------------------------------------- #
# There is no ceol-io-thesession-merge-sync cron service. One was declared in
# render.yaml and never created, so this never ran. It now rides on the
# active-sessions cron, which fires at 14,29,44,59 past every hour -- so the gate
# has to do two things: pick the weekly window, and stop all four invocations
# inside that window from each kicking off a run.

import importlib.util  # noqa: E402
import os  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


def _job_module():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "jobs",
        "sync_thesession_merges.py",
    )
    spec = importlib.util.spec_from_file_location("sync_thesession_merges_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MONDAY_0614 = datetime(2026, 8, 24, 6, 14, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "label,now,last_run,expected",
    [
        ("first ever run", MONDAY_0614, None, True),
        ("a week since the last", MONDAY_0614, datetime(2026, 8, 17, 6, 14, tzinfo=timezone.utc), True),
        ("later that same hour", MONDAY_0614.replace(minute=29),
         datetime(2026, 8, 24, 6, 14, tzinfo=timezone.utc), False),
        ("wrong hour", MONDAY_0614.replace(hour=7), None, False),
        ("wrong day", MONDAY_0614.replace(day=25), None, False),
        ("a missed week is picked up", MONDAY_0614,
         datetime(2026, 8, 3, 6, 14, tzinfo=timezone.utc), True),
        # started_at comes back naive from some drivers; UTC is what it means.
        ("naive timestamp from the DB", MONDAY_0614, datetime(2026, 8, 10, 6, 14), True),
    ],
)
def test_is_due(label, now, last_run, expected, monkeypatch):
    job = _job_module()
    monkeypatch.setattr(job, "_last_run_started_at", lambda: last_run)
    assert job.is_due(now) is expected, label


def test_run_weekly_if_due_does_not_run_outside_the_window(monkeypatch):
    job = _job_module()
    ran = []
    monkeypatch.setattr(job, "_last_run_started_at", lambda: None)
    monkeypatch.setattr(job, "run_sync_job", lambda: ran.append(1))

    assert job.run_weekly_if_due(MONDAY_0614.replace(hour=7)) is False
    assert ran == []


def test_run_weekly_if_due_runs_inside_the_window(monkeypatch):
    job = _job_module()
    ran = []
    monkeypatch.setattr(job, "_last_run_started_at", lambda: None)
    monkeypatch.setattr(job, "run_sync_job", lambda: ran.append(1))

    assert job.run_weekly_if_due(MONDAY_0614) is True
    assert ran == [1]


def test_the_gate_reads_the_real_scan_table(merge_env):
    """is_due's DB half, against a real tune_merge_scan row.

    The window is faked; what is exercised is that a run recorded moments ago
    makes the next invocation say no.
    """
    job = _job_module()
    assert job.is_due(MONDAY_0614) is True

    scan_id = scan_svc.create_run(started_by_user_id=None)
    assert scan_id is not None
    try:
        assert job.is_due(MONDAY_0614) is False, "a run that just started means not due"
    finally:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM tune_merge_scan_result WHERE scan_id = %s", (scan_id,))
        cur.execute("DELETE FROM tune_merge_scan WHERE scan_id = %s", (scan_id,))
        conn.commit()
        conn.close()
