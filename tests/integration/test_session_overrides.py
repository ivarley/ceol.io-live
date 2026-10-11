"""A session's own name, setting and key for a tune, as the seed holds them
(schema/seed_data.sql, "every combination of the three overrides"), and what the
viewer sees of them: the search cards' session_defaults in every scope, the
preview's, the quick matches' your_alias, and the precedence between sessions
(most attended, then most recent, then first by name).

Signed in as sarah_fiddle (person 2): a member of Mueller, Downtown, Hyde Park,
Riverside and Barton Springs, not of Chicago."""

import pytest

HYDE_PARK = "Hyde Park Session"

# tune_id -> what Hyde Park says about it, as the seed has it.
PERMUTATIONS = {
    6: ("The Sweetheart", None, None),
    15: (None, 12381, None),
    17: (None, None, "Dmajor"),
    19: ("The Rambling Connaughtman", 12390, None),
    21: ("Kelly's Castle", None, "Gmajor"),
    29: (None, 12420, "Amajor"),
    33: ("Goodbye Ireland", 12428, "Dmajor"),
}
NAMES = {
    6: "Do You Like Her",
    15: "Calliope House",
    17: "Coleraine",
    19: "Connaughtman",
    21: "Castle Kelly",
    29: "Dusty Windowsills",
    33: "Farewell To Ireland",
}


def _search(client, q, scope=""):
    r = client.get(f"/api/tunes/deep-search?q={q}&limit=30{scope}")
    assert r.status_code == 200, r.get_json()
    return {t["tune_id"]: t for t in r.get_json()["results"]}


@pytest.mark.parametrize("tune_id", sorted(PERMUTATIONS))
def test_every_combination_of_overrides_reaches_the_card(client, authenticated_user, tune_id):
    alias, setting_id, key = PERMUTATIONS[tune_id]
    with authenticated_user:
        hit = _search(client, NAMES[tune_id])[tune_id]
    d = hit["session_defaults"]
    assert d is not None, "a session of yours has a say"
    assert (d["session_name"], d["alias"], d["setting_id"], d["key"]) == (HYDE_PARK, alias, setting_id, key)
    assert d["session_path"] == "austin/hyde-park"
    assert hit["in_your_sessions"] is True


@pytest.mark.parametrize("tune_id", sorted(PERMUTATIONS))
def test_the_preview_agrees_with_the_card(client, authenticated_user, tune_id):
    with authenticated_user:
        card = _search(client, NAMES[tune_id])[tune_id]["session_defaults"]
        preview = client.get(f"/api/tunes/{tune_id}/preview").get_json()
    assert preview["session_defaults"] == card
    if card["setting_id"] is not None:
        # The setting is one the preview can page to.
        assert card["setting_id"] in {s["setting_id"] for s in preview["settings"]}


def test_the_defaults_come_in_every_scope(client, authenticated_user):
    with authenticated_user:
        mine = _search(client, "Farewell To Ireland")[33]["session_defaults"]
        scoped = _search(client, "Farewell To Ireland", "&session=austin/mueller")[33]["session_defaults"]
    assert mine == scoped
    assert mine["alias"] == "Goodbye Ireland"


def test_found_by_your_sessions_name_for_it(client, authenticated_user):
    with authenticated_user:
        by_alias = _search(client, "sweetheart")
        by_name = _search(client, "Do You Like Her")
    assert by_alias[6]["matched_alias"] == "The Sweetheart"
    assert by_name[6]["matched_alias"] is None
    assert by_name[6]["session_defaults"]["alias"] == "The Sweetheart"


def test_precedence_goes_to_the_session_you_attend_most(client, authenticated_user):
    """Mueller (11 nights, a key only) beats Hyde Park (2 nights, a name and a key):
    Mueller's overrides apply, so the tune keeps its catalogue name."""
    with authenticated_user:
        d = _search(client, "Mason's Apron")[74]["session_defaults"]
    assert d["session_name"] == "Mueller Session"
    assert (d["alias"], d["setting_id"], d["key"]) == (None, None, "A")


def test_precedence_then_goes_to_the_session_attended_most_recently(client, authenticated_user):
    """Hyde Park and Riverside: two nights each, Riverside's later."""
    with authenticated_user:
        d = _search(client, "Frieze Breeches")[34]["session_defaults"]
    assert d["session_name"] == "Riverside Session"
    assert d["alias"] == "Frieze Breeches (Riverside)"


def test_precedence_then_goes_to_the_first_session_by_name(client, authenticated_user):
    """Riverside and Barton Springs: the same two nights."""
    with authenticated_user:
        d = _search(client, "Glendart")[45]["session_defaults"]
    assert d["session_name"] == "Barton Springs Session"
    assert d["alias"] == "Glendart (Barton Springs)"


def test_a_session_you_are_not_in_has_no_say(client, authenticated_user):
    with authenticated_user:
        hit = _search(client, "Cutting Bracken")[647]
    assert hit["session_defaults"] is None
    assert hit["in_your_sessions"] is False
    assert hit["matched_alias"] is None


def test_the_quick_matches_and_vocabulary_lead_with_your_sessions_name(client, authenticated_user):
    """At a Hyde Park night (instance 450): /match rows carry the catalogue name and
    your_alias; the vocabulary carries your_alias; the usually-next path reads the same
    vocabulary entry."""
    with authenticated_user:
        rows = client.get("/api/live/instances/450/match?q=my%20love").get_json()["results"]
        vocab = client.get("/api/live/instances/450/vocabulary").get_json()["known_tunes"]
    row = next(r for r in rows if r["tune_id"] == 6)
    assert row["tune_name"] == "The Sweetheart"
    assert row["catalogue_name"] == "This Is My Love, Do You Like Her?"
    assert row["your_alias"] == "The Sweetheart"
    known = {t["tune_id"]: t for t in vocab}
    assert known[6]["alias"] == "The Sweetheart" and known[6]["your_alias"] == "The Sweetheart"
    # Mueller's say wins for the Apron even at a Hyde Park night: no name of yours.
    assert known[74]["alias"] == "The Apron" and "your_alias" not in known[74]
    # A Mueller night: your sessions' names still lead (Hyde Park's for the jig).
    with authenticated_user:
        rows = client.get("/api/live/instances/1/match?q=my%20love").get_json()["results"]
    row = next(r for r in rows if r["tune_id"] == 6)
    assert row["your_alias"] == "The Sweetheart"
