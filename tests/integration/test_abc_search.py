"""Integration tests for notation (ABC) search on the app-wide tune-search surfaces:

    GET  /api/tunes/search      (the hamburger "Find a tune" overlay — public)
    POST /api/tunes/abc-filter  (notation match over a list the client already shows)

Both blend notation through the same database.abc_search_terms rules the deep search
uses, so a note-shaped query behaves identically wherever it is typed.

Isolation note: the endpoints open their own connection via get_db_connection(), so the
fixture commits throwaway rows on its own connection and deletes them in teardown (same
pattern as test_my_tunes_search).
"""

import pytest

from database import get_db_connection

pytestmark = pytest.mark.integration

# High, unlikely-to-collide ids for throwaway rows.
PLAIN = 9421     # "Zorble Reel" — notation stored plainly
ORNATE = 9422    # "Zorble Jig"  — same phrase, buried in grace notes and a chord symbol
NAMED = 9423     # "Bead Cabbage" — a NAME made only of note letters, no notation at all

# The phrase both settings contain, written the way a player would type it.
PHRASE = "GED BED"


@pytest.fixture
def abc_tunes():
    conn = get_db_connection()
    cur = conn.cursor()
    for tid, name, ttype, count in (
        (PLAIN, "Zorble Reel", "Reel", 500),
        (ORNATE, "Zorble Jig", "Jig", 5),
        (NAMED, "Bead Cabbage", "Reel", 50),
    ):
        cur.execute(
            "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, %s, %s, %s)",
            (tid, name, ttype, count),
        )
    cur.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Edor', %s)",
        (PLAIN, PLAIN, "|:G E D B E D|cAA fdd:|"),
    )
    # Same notes, ornamented — findable only because abc_search_key strips {...} and "...".
    cur.execute(
        "INSERT INTO tune_setting (setting_id, tune_id, key, abc) VALUES (%s, %s, 'Edor', %s)",
        (ORNATE, ORNATE, '|:"Em"{a}G E D {c}B E D|cAA fdd:|'),
    )
    conn.commit()

    yield {"plain": PLAIN, "ornate": ORNATE, "named": NAMED}

    ids = [PLAIN, ORNATE, NAMED]
    cur.execute("DELETE FROM tune_setting_history WHERE tune_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM tune_setting WHERE tune_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM tune_history WHERE tune_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM tune WHERE tune_id = ANY(%s)", (ids,))
    conn.commit()
    cur.close()
    conn.close()


def _ids(resp):
    return [t["tune_id"] for t in resp.get_json()["tunes"]]


# --- GET /api/tunes/search -------------------------------------------------------

def test_search_blends_notation_and_flags_it(client, abc_tunes):
    """A note-shaped query finds tunes whose notation contains it, badged abc_only."""
    resp = client.get(f"/api/tunes/search?q={PHRASE.replace(' ', '+')}")
    assert resp.status_code == 200
    tunes = {t["tune_id"]: t for t in resp.get_json()["tunes"]}
    assert PLAIN in tunes and tunes[PLAIN]["abc_only"] is True


def test_search_matches_through_ornaments(client, abc_tunes):
    """Grace notes and chord symbols are stripped from both sides, so a player who types
    the notes finds the ornamented setting too."""
    assert ORNATE in _ids(client.get(f"/api/tunes/search?q={PHRASE.replace(' ', '+')}"))


def test_search_works_logged_out(client, abc_tunes):
    """The overlay is offered to logged-out users on every page."""
    assert client.get(f"/api/tunes/search?q={PHRASE.replace(' ', '+')}").status_code == 200


def test_name_matches_outrank_notation_only_matches(client, abc_tunes):
    """"Bead Cabbage" is all note letters, so it is both a name match and a candidate for
    notation blending. The name match must come first."""
    ids = _ids(client.get("/api/tunes/search?q=bead"))
    assert ids and ids[0] == NAMED


def test_name_query_sets_abc_only_false(client, abc_tunes):
    tunes = client.get("/api/tunes/search?q=Zorble").get_json()["tunes"]
    assert tunes and all(t["abc_only"] is False for t in tunes)


def test_short_note_query_does_not_blend(client, abc_tunes):
    """Below the minimum, notation would match nearly the whole catalog — so it doesn't."""
    assert PLAIN not in _ids(client.get("/api/tunes/search?q=ge"))


def test_mode_name_suppresses_notation(client, abc_tunes):
    assert PLAIN not in _ids(client.get(f"/api/tunes/search?q={PHRASE.replace(' ', '+')}&mode=name"))


def test_mode_abc_suppresses_name_matches(client, abc_tunes):
    ids = _ids(client.get("/api/tunes/search?q=Zorble&mode=abc"))
    assert PLAIN not in ids and ORNATE not in ids


def test_thesession_link_is_a_pointer_not_a_query(client, abc_tunes):
    """A pasted permalink resolves to exactly one tune; notation must never be blended
    into it, or a link would drag in unrelated tunes."""
    resp = client.get(f"/api/tunes/search?q=https://thesession.org/tunes/{PLAIN}")
    body = resp.get_json()
    assert body["query_tune_id"] == PLAIN
    assert _ids(resp) == [PLAIN]
    assert body["tunes"][0]["abc_only"] is False


# --- POST /api/tunes/abc-filter --------------------------------------------------

def _filter(client, q, tune_ids):
    return client.post("/api/tunes/abc-filter", json={"q": q, "tune_ids": tune_ids})


def test_abc_filter_returns_matching_subset(client, abc_tunes):
    resp = _filter(client, PHRASE, [PLAIN, ORNATE, NAMED])
    assert resp.status_code == 200
    assert sorted(resp.get_json()["tune_ids"]) == sorted([PLAIN, ORNATE])


def test_abc_filter_never_returns_ids_it_was_not_given(client, abc_tunes):
    """It filters the caller's list — it is not a catalog search."""
    assert _filter(client, PHRASE, [NAMED]).get_json()["tune_ids"] == []


def test_abc_filter_works_logged_out(client, abc_tunes):
    """Session pages are publicly viewable, so their Tunes tab must filter logged out."""
    assert _filter(client, PHRASE, [PLAIN]).status_code == 200


def test_abc_filter_ignores_name_queries(client, abc_tunes):
    """Ordinary name typing must cost nothing — no notation match, no rows."""
    assert _filter(client, "Drowsy Maggie", [PLAIN, ORNATE]).get_json()["tune_ids"] == []


def test_abc_filter_ignores_too_short_queries(client, abc_tunes):
    assert _filter(client, "ge", [PLAIN, ORNATE]).get_json()["tune_ids"] == []


def test_abc_filter_empty_list(client, abc_tunes):
    assert _filter(client, PHRASE, []).get_json()["tune_ids"] == []


def test_abc_filter_rejects_oversized_id_list(client):
    """Reject rather than truncate: a silently truncated filter would hide real matches."""
    assert _filter(client, PHRASE, list(range(2001))).status_code == 400


def test_abc_filter_rejects_oversized_query(client):
    assert _filter(client, "G" * 201, [1]).status_code == 400


def test_abc_filter_rejects_non_integer_ids(client):
    assert _filter(client, PHRASE, ["not-an-id"]).status_code == 400


def test_abc_filter_rejects_non_list_ids(client):
    resp = client.post("/api/tunes/abc-filter", json={"q": PHRASE, "tune_ids": "1,2"})
    assert resp.status_code == 400
