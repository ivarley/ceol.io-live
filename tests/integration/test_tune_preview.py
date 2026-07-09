"""
Integration tests for the deep-search tune-preview endpoints (look before you log):

    GET  /api/my-tunes/tune-preview/<tune_id>                  (+ live / session-path homes)
    GET  /api/my-tunes/setting-image/<setting_id>?kind=
    GET  /api/my-tunes/thesession-preview/<thesession_id>
    POST /api/my-tunes/render-abc

The preview returns the tune's settings (abc + incipit abc + any cached incipit
image), session aliases where a session scope exists, and stats. The thesession
preview is exercised with the fetch monkeypatched (no external network); actual
PNG rendering is not exercised (no renderer service in tests — endpoints return a
null image gracefully).

Isolation note: the endpoints open their own connection via get_db_connection() and
read committed rows, so the fixture commits throwaway rows on its own connection and
deletes them in teardown (same pattern as test_my_tunes_search).
"""

import pytest

from database import get_db_connection

pytestmark = pytest.mark.integration

# High, unlikely-to-collide ids for throwaway rows.
TUNE = 9421          # "Glorp Preview Reel" — two settings, one with a cached incipit image
TUNE_BARE = 9422     # "Glorp Preview Bare" — no settings at all
TUNE_MERGED = 9423   # redirects to TUNE (merged away)
SETTING_A = 94211
SETTING_B = 94212
SID = 9420           # throwaway session (aliases + played-here stats)
SPATH = "glorp-preview-test"
SI = 94201           # throwaway session instance
REMOTE_ID = 94299    # not in the local catalog (thesession preview fetches)

FAKE_TS_TUNE = {
    "id": REMOTE_ID,
    "name": "The Remote Preview",
    "type": "reel",
    "tunebooks": 7,
    "aliases": ["The Faraway", "An Cian"],
    "settings": [
        {"id": 942991, "key": "Ador", "abc": "eA~A2 eAdB!eA~A2 gedB|"},
        {"id": 942992, "key": "Gmaj", "abc": ""},  # empty abc is skipped
    ],
}


@pytest.fixture
def preview_rows():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, 'Glorp Preview Reel', 'Reel', 321)",
        (TUNE,),
    )
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, 'Glorp Preview Bare', 'Jig', 1)",
        (TUNE_BARE,),
    )
    cur.execute(
        "INSERT INTO tune (tune_id, name, tune_type, redirect_to_tune_id) VALUES (%s, 'Glorp Preview Old Name', 'Reel', %s)",
        (TUNE_MERGED, TUNE),
    )
    cur.execute(
        """INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, incipit_image)
           VALUES (%s, %s, 'Gmaj', 'GE~E2 GEDE|GE~E2 GABd|', 'GE~E2 GEDE', %s)""",
        (SETTING_A, TUNE, b"\x89PNG-fake-incipit"),
    )
    cur.execute(
        """INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, incipit_image)
           VALUES (%s, %s, 'Ador', 'eA~A2 eAdB|', 'eA~A2 eAdB', %s)""",
        (SETTING_B, TUNE, b"\x89PNG-fake-incipit-b"),
    )
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, 'Glorp Preview Test', %s)", (SID, SPATH))
    # The session prefers SETTING_B — the preview opens/badges it and the session-scoped
    # deep-search card shows ITS incipit instead of the default (lowest-id) one.
    cur.execute(
        "INSERT INTO session_tune (session_id, tune_id, alias, setting_id) VALUES (%s, %s, 'The Glorp', %s)",
        (SID, TUNE, SETTING_B),
    )
    cur.execute(
        "INSERT INTO session_tune_alias (session_id, tune_id, alias) VALUES (%s, %s, 'Glorpy McGlorp')",
        (SID, TUNE),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES (%s, %s, '2026-06-24')",
        (SI, SID),
    )
    cur.execute(
        """INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type)
           VALUES (%s, %s, 'a0', 'tune')""",
        (SI, TUNE),
    )
    conn.commit()

    yield {"session_path": SPATH}

    cur.execute("DELETE FROM session_instance_tune_history WHERE session_instance_id = %s", (SI,))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (SI,))
    cur.execute("DELETE FROM session_instance_history WHERE session_instance_id = %s", (SI,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (SI,))
    cur.execute("DELETE FROM session_tune_alias WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session_history WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM tune_setting_history WHERE setting_id = ANY(%s)", ([SETTING_A, SETTING_B],))
    cur.execute("DELETE FROM tune_setting WHERE setting_id = ANY(%s)", ([SETTING_A, SETTING_B],))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", ([TUNE, TUNE_BARE, TUNE_MERGED],))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", ([TUNE, TUNE_BARE, TUNE_MERGED],))
    conn.commit()
    cur.close()
    conn.close()


def test_tune_preview_requires_login(client, preview_rows):
    resp = client.get(f"/api/my-tunes/tune-preview/{TUNE}")
    assert resp.status_code == 401


def test_tune_preview_personal_settings_and_no_session_fields(client, authenticated_user, preview_rows):
    """My Tunes home: all settings in setting_id order (abc + incipit abc, cached
    incipit inline), no session aliases/stats."""
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/tune-preview/{TUNE}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["name"] == "Glorp Preview Reel"
    assert body["tunebook_count"] == 321
    assert body["aliases"] == []
    assert body["played_here"] == 0 and body["dates"] == []
    assert [s["setting_id"] for s in body["settings"]] == [SETTING_A, SETTING_B]
    assert body["settings"][0]["incipit_image"] is not None  # cached inline
    assert body["settings"][1]["abc"] == "eA~A2 eAdB|"
    assert body["settings"][1]["incipit_abc"]  # stored (or derived) incipit text
    assert body["session_setting_id"] is None  # personal scope: no session preference


def test_tune_preview_session_scope_aliases_and_stats(client, authenticated_user, preview_rows):
    """Session-path home: session_tune.alias + session_tune_alias surface as
    aliases; played-here count and dates are scoped to the session."""
    with authenticated_user:
        resp = client.get(f"/api/sessions/{SPATH}/tunes/tune-preview/{TUNE}")
    body = resp.get_json()
    assert body["success"] is True
    assert body["aliases"] == ["The Glorp", "Glorpy McGlorp"]
    assert body["played_here"] == 1
    assert body["dates"] == ["2026-06-24"]
    assert body["session_setting_id"] == SETTING_B  # the pager opens/badges this one


def test_tune_preview_follows_merge_redirect(client, authenticated_user, preview_rows):
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/tune-preview/{TUNE_MERGED}")
    body = resp.get_json()
    assert body["success"] is True
    assert body["tune_id"] == TUNE
    assert body["name"] == "Glorp Preview Reel"


def test_tune_preview_no_settings_and_unknown(client, authenticated_user, preview_rows):
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/tune-preview/{TUNE_BARE}")
        missing = client.get("/api/my-tunes/tune-preview/98765432")
    assert resp.get_json()["settings"] == []
    assert missing.status_code == 404


def test_deep_search_card_prefers_session_setting_incipit(client, authenticated_user, preview_rows):
    """With a session scope, the card's incipit is the SESSION'S preferred setting
    (among cached images); without one, the lowest cached setting wins as before."""
    with authenticated_user:
        personal = client.get("/api/my-tunes/deep-search?q=glorp preview reel")
        scoped = client.get(f"/api/sessions/{SPATH}/tunes/deep-search?q=glorp preview reel")
        pv = client.get(f"/api/sessions/{SPATH}/tunes/tune-preview/{TUNE}")
    settings = {s["setting_id"]: s for s in pv.get_json()["settings"]}
    assert settings[SETTING_A]["incipit_image"] != settings[SETTING_B]["incipit_image"]
    personal_card = {r["tune_id"]: r for r in personal.get_json()["results"]}[TUNE]
    scoped_card = {r["tune_id"]: r for r in scoped.get_json()["results"]}[TUNE]
    assert personal_card["incipit_image"] == settings[SETTING_A]["incipit_image"]
    assert scoped_card["incipit_image"] == settings[SETTING_B]["incipit_image"]


def test_setting_image_cached_full_and_missing(client, authenticated_user, preview_rows):
    """A cached incipit returns inline. kind=full renders on demand when the
    abc-renderer service is reachable (and caches the PNG on the setting row) or
    degrades to a null image when it isn't — success either way. An unknown
    setting is a graceful null."""
    with authenticated_user:
        cached = client.get(f"/api/my-tunes/setting-image/{SETTING_A}?kind=incipit")
        full = client.get(f"/api/my-tunes/setting-image/{SETTING_B}?kind=full")
        missing = client.get("/api/my-tunes/setting-image/87654321")
    assert cached.get_json()["image"] is not None
    body = full.get_json()
    assert body["success"] is True
    assert missing.get_json() == {"success": True, "image": None}
    if body["image"] is not None:  # renderer was up: the render must now be cached
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT image IS NOT NULL FROM tune_setting WHERE setting_id = %s", (SETTING_B,))
            assert cur.fetchone()[0] is True
        finally:
            conn.close()


def test_thesession_preview_local_id_shortcuts(client, authenticated_user, preview_rows, monkeypatch):
    """An id we already have (or a merged alias of it) reports is_local + the
    canonical id — and never touches the network."""
    import live_logging_routes

    def _boom(tid):
        raise AssertionError("must not fetch for a local id")

    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", _boom)
    with authenticated_user:
        local = client.get(f"/api/my-tunes/thesession-preview/{TUNE}")
        merged = client.get(f"/api/my-tunes/thesession-preview/{TUNE_MERGED}")
    assert local.get_json() == {"success": True, "is_local": True, "tune_id": TUNE}
    assert merged.get_json() == {"success": True, "is_local": True, "tune_id": TUNE}


def test_thesession_preview_remote_fetches_and_shapes(client, authenticated_user, preview_rows, monkeypatch):
    """A remote id returns name/type/aliases/settings with '!' line breaks unfolded
    and incipit abc derived; empty-abc settings are dropped."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", lambda tid: dict(FAKE_TS_TUNE))
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/thesession-preview/{REMOTE_ID}")
    body = resp.get_json()
    assert body["success"] is True and body["is_local"] is False
    assert body["name"] == "The Remote Preview"
    assert body["tune_type"] == "Reel"
    assert body["tunebook_count"] == 7
    assert body["aliases"] == ["The Faraway", "An Cian"]
    assert len(body["settings"]) == 1  # the empty-abc setting is dropped
    s = body["settings"][0]
    assert s["setting_id"] == 942991
    assert "!" not in s["abc"] and "\n" in s["abc"]
    assert s["incipit_abc"]


def test_thesession_preview_full_fetches_for_local_id(client, authenticated_user, preview_rows, monkeypatch):
    """?full=1 skips the local short-circuit: an already-imported tune still gets the
    complete thesession settings list (the preview backfills settings beyond the one
    the import brought over), flagged is_local."""
    import live_logging_routes
    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune",
                        lambda tid: {**FAKE_TS_TUNE, "id": tid})
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/thesession-preview/{TUNE}?full=1")
    body = resp.get_json()
    assert body["success"] is True and body["is_local"] is True
    assert body["tune_id"] == TUNE
    assert len(body["settings"]) == 1 and body["settings"][0]["setting_id"] == 942991


def test_thesession_preview_fetch_error_passthrough(client, authenticated_user, preview_rows, monkeypatch):
    import live_logging_routes
    from api_routes import TuneImportError

    def _gone(tid):
        raise TuneImportError(f"Tune #{tid} not found on thesession.org", 404)

    monkeypatch.setattr(live_logging_routes, "_fetch_thesession_tune", _gone)
    with authenticated_user:
        resp = client.get(f"/api/my-tunes/thesession-preview/{REMOTE_ID}")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_render_abc_validates_and_degrades(client, authenticated_user, preview_rows):
    """No abc -> 400; with abc but no renderer configured -> success, null image."""
    with authenticated_user:
        empty = client.post("/api/my-tunes/render-abc", json={})
        ok = client.post("/api/my-tunes/render-abc",
                         json={"abc": "GE~E2 GEDE|", "key": "Gmaj", "tune_type": "Reel", "kind": "incipit"})
    assert empty.status_code == 400
    assert ok.status_code == 200
    assert ok.get_json()["success"] is True


def test_live_home_registered(client, authenticated_user, preview_rows):
    """The live-instance home resolves its session scope from the instance."""
    with authenticated_user:
        resp = client.get(f"/api/live/instances/{SI}/tune-preview/{TUNE}")
    body = resp.get_json()
    assert body["success"] is True
    assert body["played_here"] == 1
    assert body["aliases"] == ["The Glorp", "Glorpy McGlorp"]
