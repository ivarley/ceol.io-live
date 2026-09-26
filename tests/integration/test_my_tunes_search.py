"""
Integration tests for the add-pane search endpoints — the live logger's deep search
in its two pane flavors, told apart by scope (spec 052 A6):

    GET /api/tunes/deep-search                          (personal: on_list sorts last)
    GET /api/tunes/<tune_id>/incipit-image
    GET /api/tunes/deep-search?session=<path>           (session: in_session sorts last)

Same name/ABC matching and ranking as the live screen (_deep_search_core). The
thesession-search proxies are exercised with a mocked outbound request only
(no external network).

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
    resp = client.get("/api/tunes/deep-search?q=glorp")
    assert resp.status_code == 401


def test_deep_search_finds_and_flags_on_list(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/tunes/deep-search?q=glorp fandango")
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
        resp = client.get("/api/tunes/deep-search?q=glorp fandango")
    results = resp.get_json()["results"]
    ids = [r["tune_id"] for r in results]
    assert ids.index(search_tunes["offlist"]) < ids.index(search_tunes["onlist"])


def test_deep_search_type_filter(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/tunes/deep-search?q=glorp fandango&type=Jig")
    ids = [r["tune_id"] for r in resp.get_json()["results"]]
    assert search_tunes["onlist"] not in ids and search_tunes["offlist"] not in ids


def test_incipit_endpoint_no_notation(client, authenticated_user, search_tunes):
    """A tune with no tune_setting rows: success with a null image (nothing to render)."""
    with authenticated_user:
        resp = client.get(f"/api/tunes/{search_tunes['offlist']}/incipit-image")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["image"] is None


def test_session_deep_search_flags_and_sorts_in_session_last(client, authenticated_user, search_tunes):
    """Session flavor: in_session flagged, and the in-session tune sorts LAST even
    though it is far more popular (the add-to-session pane dims it)."""
    with authenticated_user:
        resp = client.get(f"/api/tunes/deep-search?session={search_tunes['session_path']}&q=glorp fandango")
    assert resp.status_code == 200
    results = resp.get_json()["results"]
    by_id = {r["tune_id"]: r for r in results}
    assert by_id[search_tunes["onlist"]]["in_session"] is True
    assert by_id[search_tunes["offlist"]]["in_session"] is False
    ids = [r["tune_id"] for r in results]
    assert ids.index(search_tunes["offlist"]) < ids.index(search_tunes["onlist"])


def test_session_deep_search_unknown_session_404(client, authenticated_user, search_tunes):
    with authenticated_user:
        resp = client.get("/api/tunes/deep-search?session=no-such-session-xyz&q=glorp")
    assert resp.status_code == 404


def test_thesession_search_dedupes_repeated_hits(client, authenticated_user, monkeypatch):
    """thesession matches per-setting, so one tune can appear several times in a single
    search response (common for ABC queries). The proxy must return each tune once —
    duplicates crash the client's keyed result list."""
    import types

    import requests as real_requests

    import live_logging_routes

    def fake_get(url, timeout=None):
        resp = types.SimpleNamespace()
        resp.status_code = 200
        resp.json = lambda: {"tunes": [
            {"id": 4717, "name": "Kings Of Kerry", "type": "slide", "url": "https://thesession.org/tunes/4717"},
            {"id": 2188, "name": "The Kerry Jig", "type": "slide", "url": "https://thesession.org/tunes/2188"},
            {"id": 4717, "name": "Kings Of Kerry", "type": "slide", "url": "https://thesession.org/tunes/4717"},
        ]}
        return resp

    monkeypatch.setattr(
        live_logging_routes, "requests",
        types.SimpleNamespace(get=fake_get, exceptions=real_requests.exceptions),
    )
    with authenticated_user:
        resp = client.get("/api/tunes/thesession-search?q=A3ABc&type=Slide")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    ids = [r["tune_id"] for r in body["results"]]
    assert ids == [4717, 2188]


# --- /api/tunes/search link resolution ------------------------------------------------
# The plain tune-search endpoint (hamburger "Find a tune", logged-out included) treats a
# thesession.org URL or bare tune id as a POINTER to one tune rather than a name to LIKE.


def test_tune_search_resolves_thesession_url(client, search_tunes):
    resp = client.get(
        "/api/tunes/search?q=https://thesession.org/tunes/%d?setting=44656#setting44656"
        % search_tunes["offlist"]
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [t["tune_id"] for t in body["tunes"]] == [search_tunes["offlist"]]
    assert body["query_tune_id"] == search_tunes["offlist"]


def test_tune_search_resolves_bare_tune_id(client, search_tunes):
    resp = client.get("/api/tunes/search?q=%d" % search_tunes["onlist"])
    assert resp.status_code == 200
    body = resp.get_json()
    assert [t["tune_id"] for t in body["tunes"]] == [search_tunes["onlist"]]


def test_tune_search_link_follows_a_merge(client, search_tunes):
    """A pasted permalink for a tune that was merged away lands on the survivor."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tune SET redirect_to_tune_id = %s WHERE tune_id = %s",
        (search_tunes["onlist"], search_tunes["offlist"]),
    )
    conn.commit()
    try:
        resp = client.get(
            "/api/tunes/search?q=https://thesession.org/tunes/%d" % search_tunes["offlist"]
        )
        body = resp.get_json()
        assert [t["tune_id"] for t in body["tunes"]] == [search_tunes["onlist"]]
        assert body["query_tune_id"] == search_tunes["onlist"]
    finally:
        cur.execute(
            "UPDATE tune SET redirect_to_tune_id = NULL WHERE tune_id = %s",
            (search_tunes["offlist"],),
        )
        conn.commit()
        cur.close()
        conn.close()


def test_tune_search_link_to_unimported_tune_is_empty_not_an_error(client):
    """Not a typo — that tune simply isn't in the catalog yet, which is what the
    clients turn into an "add it from thesession.org" offer."""
    resp = client.get("/api/tunes/search?q=https://thesession.org/tunes/99999401")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["tunes"] == []
    assert body["query_tune_id"] == 99999401


def test_tune_search_short_name_query_still_rejected(client):
    resp = client.get("/api/tunes/search?q=z")
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Ranking with a session: the composer's order, not a dictionary's
# --------------------------------------------------------------------------- #

RANK_SID = 9420
RANK_INSTANCE = 9421
RANK_POPULAR = 9422   # "Glorp Maggie Alpha": the world's favourite, never played here
RANK_LOCAL = 9423     # "Glorp Maggie Beta": obscure, but played at this session three times
RANK_PREFIX = 9424    # "Maggie Glorp Gamma": a PREFIX hit for "maggie", never played here


@pytest.fixture
def ranking_world():
    """A session with a night's log: the obscure tune was played three times, the
    popular one never; the session calls the obscure one 'Glorpy'."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES "
        "(%s, 'Glorp Maggie Alpha', 'Reel', 900), (%s, 'Glorp Maggie Beta', 'Reel', 3), "
        "(%s, 'Maggie Glorp Gamma', 'Jig', 400)",
        (RANK_POPULAR, RANK_LOCAL, RANK_PREFIX),
    )
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Glorp Rank', 'glorp-rank-test')", (RANK_SID,))
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-05-01')",
        (RANK_INSTANCE, RANK_SID),
    )
    cur.execute("INSERT INTO session_tune (session_id, tune_id, alias) VALUES (%s, %s, 'Glorpy')", (RANK_SID, RANK_LOCAL))
    for pos in ("a0", "a1", "a2"):
        cur.execute(
            "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type) VALUES (%s, %s, %s, 'tune')",
            (RANK_INSTANCE, RANK_LOCAL, pos),
        )
    conn.commit()
    yield
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (RANK_INSTANCE,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (RANK_INSTANCE,))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (RANK_SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (RANK_SID,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (RANK_SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (RANK_SID,))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([RANK_POPULAR, RANK_LOCAL, RANK_PREFIX],))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", ([RANK_POPULAR, RANK_LOCAL, RANK_PREFIX],))
    conn.commit()
    cur.close()
    conn.close()


def _live_ids(client, q, **extra):
    from urllib.parse import urlencode

    resp = client.get(f"/api/tunes/deep-search?instance={RANK_INSTANCE}&" + urlencode({"q": q, **extra}))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return [r["tune_id"] for r in resp.get_json()["results"] if r["tune_id"] in (RANK_POPULAR, RANK_LOCAL, RANK_PREFIX)]


def test_live_deep_search_ranks_what_this_session_plays_above_popularity(client, authenticated_user, ranking_world):
    """"maggie" at a session that plays Beta every week is Beta -- above the
    world's favourite AND above a prefix hit. The quick type-ahead already did
    this; the panel used to sort by how the name matched, then popularity."""
    with authenticated_user:
        ids = _live_ids(client, "maggie", prefer_type="Reel")
    assert ids == [RANK_LOCAL, RANK_POPULAR, RANK_PREFIX]


def test_live_deep_search_prefers_the_sets_type_first(client, authenticated_user, ranking_world):
    with authenticated_user:
        ids = _live_ids(client, "maggie", prefer_type="Jig")
    assert ids[0] == RANK_PREFIX


def test_live_deep_search_puts_an_exact_hit_first(client, authenticated_user, ranking_world):
    with authenticated_user:
        ids = _live_ids(client, "Glorp Maggie Alpha")
    assert ids[0] == RANK_POPULAR


def test_live_deep_search_matches_the_sessions_own_name_for_a_tune(client, authenticated_user, ranking_world):
    with authenticated_user:
        ids = _live_ids(client, "glorpy")
    assert ids == [RANK_LOCAL]


def test_my_tunes_deep_search_ranking_is_unchanged_without_a_session(client, authenticated_user, ranking_world):
    """No session: no plays to rank on, so it stays type, name match, popularity."""
    with authenticated_user:
        resp = client.get("/api/tunes/deep-search?q=glorp")
    ids = [r["tune_id"] for r in resp.get_json()["results"] if r["tune_id"] in (RANK_POPULAR, RANK_LOCAL, RANK_PREFIX)]
    # Two prefix hits by popularity, then the substring hit.
    assert ids == [RANK_POPULAR, RANK_LOCAL, RANK_PREFIX]
