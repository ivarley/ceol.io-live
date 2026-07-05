"""
Integration tests for the add-pane search endpoints — the live logger's deep search
re-homed for the two pane flavors:

    GET /api/my-tunes/deep-search                       (personal: on_list sorts last)
    GET /api/my-tunes/incipit/<tune_id>
    GET /api/sessions/<path>/tunes/deep-search          (session: in_session sorts last)

Same name/ABC matching and ranking as the live screen (_deep_search_core). The
thesession-search proxies are not exercised here (external network).

Isolation note: the endpoints open their own connection via get_db_connection() and
read committed rows, so the fixture commits throwaway rows on its own connection and
deletes them in teardown (same pattern as test_live_logging_ops).
"""

import pytest

from database import get_db_connection

pytestmark = pytest.mark.integration

# High, unlikely-to-collide ids for throwaway rows.
ONLIST = 9411   # "Glorp Fandango Alpha" — on person 2's list + in the session, MORE popular
OFFLIST = 9412  # "Glorp Fandango Beta"  — on neither, less popular
PERSON_ID = 2   # matches sample_user_data's person_id
SID = 9410      # throwaway session
SPATH = "glorp-search-test"


@pytest.fixture
def search_tunes():
    """Commit two distinctly-named throwaway tunes; the popular one is both on
    person 2's list and in the throwaway session's repertoire."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, %s, 'Reel', %s)",
        (ONLIST, "Glorp Fandango Alpha", 500),
    )
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, %s, 'Reel', %s)",
        (OFFLIST, "Glorp Fandango Beta", 5),
    )
    cur.execute(
        "INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, 'learning')",
        (PERSON_ID, ONLIST),
    )
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                (SID, "Glorp Search Test", SPATH))
    cur.execute("INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)", (SID, ONLIST))
    conn.commit()

    yield {"onlist": ONLIST, "offlist": OFFLIST, "session_path": SPATH}

    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM person_tune_history WHERE tune_id = ANY(%s)", ([ONLIST, OFFLIST],))
    cur.execute("DELETE FROM person_tune WHERE tune_id = ANY(%s)", ([ONLIST, OFFLIST],))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([ONLIST, OFFLIST],))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", ([ONLIST, OFFLIST],))
    conn.commit()
    cur.close()
    conn.close()


def test_deep_search_requires_login(client):
    resp = client.get("/api/my-tunes/deep-search?q=glorp")
    assert resp.status_code == 401


def test_deep_search_finds_and_flags_on_list(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/my-tunes/deep-search?q=glorp fandango")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    by_id = {r["tune_id"]: r for r in body["results"]}
    assert search_tunes["onlist"] in by_id and search_tunes["offlist"] in by_id
    assert by_id[search_tunes["onlist"]]["on_list"] is True
    assert by_id[search_tunes["offlist"]]["on_list"] is False
    # No session scope: the session-only fields are constant.
    assert by_id[search_tunes["onlist"]]["in_session"] is False
    assert by_id[search_tunes["onlist"]]["played_here"] == 0


def test_deep_search_sorts_on_list_last(client, authenticated_user, search_tunes):
    """The on-list tune is far more popular, but on_list is the FIRST sort key —
    the pane treats already-added tunes as dimmed noise, not add targets."""
    with authenticated_user:
        resp = client.get("/api/my-tunes/deep-search?q=glorp fandango")
    results = resp.get_json()["results"]
    ids = [r["tune_id"] for r in results]
    assert ids.index(search_tunes["offlist"]) < ids.index(search_tunes["onlist"])


def test_deep_search_type_filter(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/my-tunes/deep-search?q=glorp fandango&type=Jig")
    ids = [r["tune_id"] for r in resp.get_json()["results"]]
    assert search_tunes["onlist"] not in ids and search_tunes["offlist"] not in ids


def test_incipit_endpoint_no_notation(client, authenticated_user, search_tunes):
    """A tune with no tune_setting rows: success with a null image (nothing to render)."""
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/incipit/{search_tunes['offlist']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["image"] is None


def test_session_deep_search_flags_and_sorts_in_session_last(client, authenticated_user, search_tunes):
    """Session flavor: in_session flagged, and the in-session tune sorts LAST even
    though it is far more popular (the add-to-session pane dims it)."""
    with authenticated_user:
        resp = client.get(f"/api/sessions/{search_tunes['session_path']}/tunes/deep-search?q=glorp fandango")
    assert resp.status_code == 200
    results = resp.get_json()["results"]
    by_id = {r["tune_id"]: r for r in results}
    assert by_id[search_tunes["onlist"]]["in_session"] is True
    assert by_id[search_tunes["offlist"]]["in_session"] is False
    ids = [r["tune_id"] for r in results]
    assert ids.index(search_tunes["offlist"]) < ids.index(search_tunes["onlist"])


def test_session_deep_search_unknown_session_404(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/sessions/no-such-session-xyz/tunes/deep-search?q=glorp")
    assert resp.status_code == 404
