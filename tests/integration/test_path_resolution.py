"""Resolving /sessions/<anything> (spec 055 "Resolution"), on the page and in
/api/resolve. Seed: austin/mueller (session 1, place austin), hill-country-fest/2026
(session 6, a festival year whose town is Austin)."""

import pytest

import places
from places_helpers import committed  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration


@pytest.fixture
def metro(committed):
    """probemetro (a metro) containing probetown; a session filed under each slug."""
    probemetro = committed.place("probemetro", "Probemetro")
    probetown = committed.place("probetown", "Probetown", parent=probemetro)
    pub = committed.session("probemetro/the-pub", probetown)
    hall = committed.session("probetown/the-hall", probetown)
    return {"probemetro": probemetro, "probetown": probetown, "pub": pub, "hall": hall}


def _location(resp):
    return resp.headers["Location"].replace("http://localhost", "")


class TestResolver:
    def test_exact(self, committed):
        r = places.resolve_session_path(committed.cur, "austin/mueller")
        assert (r["kind"], r["session_id"], r["moved"]) == ("session", 1, False)

    def test_bare_place(self, committed):
        r = places.resolve_session_path(committed.cur, "hill-country-fest")
        assert (r["kind"], r["place"]["kind"]) == ("place", "festival")

    def test_alias_from_the_town(self, committed, metro):
        r = places.resolve_session_path(committed.cur, "probetown/the-pub")
        assert (r["path"], r["moved"]) == ("probemetro/the-pub", True)

    def test_alias_from_the_metro(self, committed, metro):
        r = places.resolve_session_path(committed.cur, "probemetro/the-hall")
        assert (r["path"], r["moved"]) == ("probetown/the-hall", True)

    def test_no_alias_from_a_place_that_does_not_contain_the_town(
        self, committed, metro
    ):
        assert places.resolve_session_path(committed.cur, "austin/the-pub") is None

    def test_alias_must_be_unique(self, committed, metro):
        committed.session("probemetro/the-hall", metro["probemetro"])
        # probemetro/the-hall now exists exactly; probetown/the-hall exists exactly.
        # From a third place containing both there would be two: none is chosen.
        texas = committed.place("texas-probe", "Texas probe")
        committed.query(
            "UPDATE place SET parent_place_id = %s WHERE place_id = %s RETURNING 1",
            (texas, metro["probemetro"]),
        )
        assert (
            places.resolve_session_path(committed.cur, "texas-probe/the-hall") is None
        )

    def test_redirect_chain_of_three(self, committed):
        committed.redirect("probe/a", "probe/b")
        committed.redirect("probe/b", "probe/c")
        committed.redirect("probe/c", "austin/mueller")
        r = places.resolve_session_path(committed.cur, "probe/a")
        assert (r["path"], r["moved"]) == ("austin/mueller", True)

    def test_redirect_chain_of_four_is_too_long(self, committed):
        committed.redirect("probe/a", "probe/b")
        committed.redirect("probe/b", "probe/c")
        committed.redirect("probe/c", "probe/d")
        committed.redirect("probe/d", "austin/mueller")
        assert places.resolve_session_path(committed.cur, "probe/a") is None

    def test_instance_under_an_alias(self, committed, metro):
        r = places.resolve_session_path(committed.cur, "probetown/the-pub/2026-10-01")
        assert (r["kind"], r["path"], r["instance"], r["moved"]) == (
            "instance",
            "probemetro/the-pub",
            "2026-10-01",
            True,
        )

    def test_a_festival_year_is_a_session_not_an_instance(self, committed):
        r = places.resolve_session_path(committed.cur, "hill-country-fest/2026")
        assert (r["kind"], r["session_id"]) == ("session", 6)

    def test_unknown(self, committed):
        assert places.resolve_session_path(committed.cur, "nowhere/at-all") is None


class TestRecordRedirect:
    def test_chains_collapse(self, committed):
        places.record_redirect(committed.cur, "austin/a", "austin/b")
        places.record_redirect(committed.cur, "austin/b", "austin/c")
        committed.cur.execute(
            "SELECT from_path, to_path FROM path_redirect WHERE from_path IN ('austin/a', 'austin/b') ORDER BY 1"
        )
        assert committed.cur.fetchall() == [
            ("austin/a", "austin/c"),
            ("austin/b", "austin/c"),
        ]


class TestPages:
    def test_alias_301_keeps_tab_and_query(self, client, metro):
        resp = client.get("/sessions/probetown/the-pub/tunes?x=1")
        assert resp.status_code == 301
        assert _location(resp) == "/sessions/probemetro/the-pub/tunes?x=1"

    def test_alias_301_keeps_a_tune_deep_link(self, client, metro):
        resp = client.get("/sessions/probetown/the-pub/tunes/1001")
        assert resp.status_code == 301
        assert _location(resp) == "/sessions/probemetro/the-pub/tunes/1001"

    def test_redirect_301(self, client, committed):
        committed.redirect("austin/old-mueller", "austin/mueller")
        resp = client.get("/sessions/austin/old-mueller")
        assert resp.status_code == 301
        assert _location(resp) == "/sessions/austin/mueller"

    def test_instance_under_an_alias(self, client, committed, metro):
        committed.instance(metro["pub"], "2026-10-01")
        resp = client.get("/sessions/probetown/the-pub/2026-10-01")
        assert resp.status_code == 301
        assert _location(resp) == "/sessions/probemetro/the-pub/2026-10-01"
        resp = client.get(_location(resp))
        assert resp.status_code == 302  # on to the live logger, as before
        assert "/live/" in resp.headers["Location"]

    def test_exact_page_renders(self, client):
        assert client.get("/sessions/austin/mueller").status_code == 200

    def test_festival_year_renders(self, client):
        assert client.get("/sessions/hill-country-fest/2026").status_code == 200

    def test_bare_place_is_its_page(self, client):
        assert client.get("/sessions/austin").status_code == 200

    def test_unknown_is_404(self, client):
        assert client.get("/sessions/nowhere/at-all").status_code == 404


class TestApiResolve:
    def test_alias_lands_on_the_session(self, client, metro):
        data = client.get("/api/resolve?path=/sessions/probetown/the-pub").get_json()
        assert data["kind"] == "session"
        assert data["session"]["path"] == "probemetro/the-pub"

    def test_instance_under_an_alias(self, client, committed, metro):
        instance_id = committed.instance(metro["pub"], "2026-10-01")
        data = client.get("/api/resolve?path=probetown/the-pub/2026-10-01").get_json()
        assert data["kind"] == "instance"
        assert data["instance"]["session_instance_id"] == instance_id

    def test_bare_place(self, client):
        data = client.get("/api/resolve?path=hill-country-fest").get_json()
        assert data["kind"] == "place"
        assert data["place"]["kind"] == "festival"
        assert data["place"]["parent"] == {"slug": "austin", "name": "Austin"}

    def test_unknown(self, client):
        assert client.get("/api/resolve?path=nowhere/at-all").status_code == 404
