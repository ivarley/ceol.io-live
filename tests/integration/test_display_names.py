"""The name a tune is shown under and the names beside it (tune_names.py), as every
named row carries them: display_name and other_names on the search cards in every
scope, the preview, the quick matches and the vocabulary.

Your own name for a tune (person_tune.name_alias) leads over your sessions' names;
at a session, that session's own name beats the name of the session of yours that
wins the precedence; the others beside the title skip any spelling of a name
already shown ("The Rambling Connaughtman" is "Rambling Connaughtman").

Signed in as sarah_fiddle (person 2), with the seed's personal names: 'Slán le
hÉirinn' for Farewell To Ireland (33), 'Rambling Connaughtman' for Connaughtman's
Rambles (19), 'Maid Behind the Bar' for Maid Behind The Bar, The (64)."""

HYDE_PARK = "&session=austin/hyde-park"
MUELLER = "&session=austin/mueller"


def _search(client, q, scope=""):
    r = client.get(f"/api/tunes/deep-search?q={q}&limit=30{scope}")
    assert r.status_code == 200, r.get_json()
    return {t["tune_id"]: t for t in r.get_json()["results"]}


def _names(hit):
    return hit["display_name"], hit["other_names"]


def test_your_own_name_leads_then_the_sessions_then_the_catalogues(
    client, authenticated_user
):
    with authenticated_user:
        hit = _search(client, "Farewell To Ireland")[33]
    # Hyde Park calls it Goodbye Ireland; your name wins, the two others follow.
    assert _names(hit) == (
        "Slán le hÉirinn",
        ["Goodbye Ireland", "Farewell To Ireland"],
    )
    # session_defaults still say what the session says: the add flows start from them.
    assert hit["session_defaults"]["alias"] == "Goodbye Ireland"


def test_the_sessions_name_leads_when_you_have_none(client, authenticated_user):
    with authenticated_user:
        hit = _search(client, "Do You Like Her")[6]
    assert _names(hit) == ("The Sweetheart", ["This Is My Love, Do You Like Her?"])


def test_the_catalogues_name_when_nobody_has_another(client, authenticated_user):
    with authenticated_user:
        hit = _search(client, "Cutting Bracken")[647]
    assert _names(hit) == ("Cutting Bracken", [])


def test_a_spelling_of_a_shown_name_is_not_offered(client, authenticated_user):
    with authenticated_user:
        rambles = _search(client, "Connaughtman")[19]
        maid = _search(client, "Maid Behind")[64]
    # Yours is Hyde Park's without the article: only the catalogue's is another name.
    assert _names(rambles) == ("Rambling Connaughtman", ["Connaughtman's Rambles, The"])
    # Yours is the catalogue's name, the article moved: no other names at all.
    assert _names(maid) == ("Maid Behind the Bar", [])


def test_the_matched_name_comes_first(client, authenticated_user):
    with authenticated_user:
        by_alias = _search(client, "sweetheart")[6]
        by_name = _search(client, "Do You Like Her")[6]
    # Found by the title itself: the title is not repeated beside it.
    assert _names(by_alias) == ("The Sweetheart", ["This Is My Love, Do You Like Her?"])
    assert _names(by_name) == ("The Sweetheart", ["This Is My Love, Do You Like Her?"])


def test_at_a_session_its_own_name_beats_the_session_that_wins_the_precedence(
    client, authenticated_user
):
    """Riverside wins the precedence for the Frieze Breeches (attended later than Hyde
    Park), and names the card in your tunebook and at Mueller; at Hyde Park, Hyde
    Park's own name leads."""
    with authenticated_user:
        mine = _search(client, "Frieze Breeches")[34]
        at_hyde_park = _search(client, "Frieze Breeches", HYDE_PARK)[34]
        at_mueller = _search(client, "Frieze Breeches", MUELLER)[34]
    assert _names(mine) == ("Frieze Breeches (Riverside)", ["Frieze Breeches, The"])
    assert _names(at_hyde_park) == (
        "Frieze Breeches (Hyde Park)",
        ["Frieze Breeches, The"],
    )
    assert _names(at_mueller) == (
        "Frieze Breeches (Riverside)",
        ["Frieze Breeches, The"],
    )


def test_your_own_name_leads_at_a_session_too(client, authenticated_user):
    with authenticated_user:
        hit = _search(client, "Farewell To Ireland", HYDE_PARK)[33]
    assert _names(hit) == (
        "Slán le hÉirinn",
        ["Goodbye Ireland", "Farewell To Ireland"],
    )


def test_the_preview_agrees_and_its_alias_line_opens_with_the_other_names(
    client, authenticated_user
):
    with authenticated_user:
        card = _search(client, "Farewell To Ireland")[33]
        preview = client.get("/api/tunes/33/preview").get_json()
        scoped = client.get(
            f"/api/tunes/34/preview?session=austin/hyde-park"
        ).get_json()
    assert (preview["display_name"], preview["other_names"]) == _names(card)
    assert preview["aliases"][:2] == ["Goodbye Ireland", "Farewell To Ireland"]
    assert scoped["display_name"] == "Frieze Breeches (Hyde Park)"
    assert scoped["other_names"] == ["Frieze Breeches, The"]
    # The session's alias was in the line already; it is not there twice.
    assert scoped["aliases"].count("Frieze Breeches (Hyde Park)") == 0


def test_the_quick_matches_and_the_vocabulary_name_tunes_the_same_way(
    client, authenticated_user
):
    """A Hyde Park night (instance 450): the rows the logger's type-ahead and the
    listening meter name tunes from."""
    with authenticated_user:
        rows = client.get("/api/live/instances/450/match?q=farewell").get_json()[
            "results"
        ]
        vocab = client.get("/api/live/instances/450/vocabulary").get_json()[
            "known_tunes"
        ]
    row = next(r for r in rows if r["tune_id"] == 33)
    assert (row["display_name"], row["other_names"]) == (
        "Slán le hÉirinn",
        ["Goodbye Ireland", "Farewell To Ireland"],
    )
    known = {t["tune_id"]: t for t in vocab}
    assert (known[33]["display_name"], known[33]["other_names"]) == (
        "Slán le hÉirinn",
        ["Goodbye Ireland", "Farewell To Ireland"],
    )
    # No name of yours, Mueller's say (no name) wins the precedence: Hyde Park's own
    # name still leads at a Hyde Park night.
    assert (known[74]["display_name"], known[74]["other_names"]) == (
        "The Apron",
        ["Mason's Apron, The"],
    )
    # A tune nobody has named: its catalogue name, nothing beside it.
    plain = next(
        t for t in vocab if t["tune_id"] not in (6, 15, 17, 19, 21, 29, 33, 34, 64, 74)
    )
    assert plain["display_name"] == plain["name"] and plain["other_names"] == []
