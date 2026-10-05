"""Place pages and the directory (spec 055 "Place pages and the directory"), and
one directory row per festival (spec 056 "Directory and home")."""

import pytest

from places_helpers import committed  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration

API = "/api/sessions/with-today-status"


@pytest.fixture
def metro(committed):
    """probemetro (a metro) containing probetown; a session in each."""
    m = committed.place("probemetro", "Probemetro")
    t = committed.place("probetown", "Probetown", parent=m)
    committed.session("probemetro/downtown", m)
    committed.session(
        "probemetro/the-pub", t
    )  # filed under the metro slug, town is probetown
    committed.session("probetown/the-hall", t)
    return {"metro": m, "town": t}


def _paths(data):
    return sorted(s["path"] for s in data["sessions"])


def test_a_metro_lists_its_towns_sessions(client, metro):
    data = client.get(f"{API}?place=probemetro").get_json()
    assert _paths(data) == [
        "probemetro/downtown",
        "probemetro/the-pub",
        "probetown/the-hall",
    ]
    assert data["place"]["name"] == "Probemetro"
    assert data["place"]["children"] == [{"slug": "probetown", "name": "Probetown"}]


def test_a_town_lists_its_own(client, metro):
    data = client.get(f"{API}?place=probetown").get_json()
    assert _paths(data) == ["probemetro/the-pub", "probetown/the-hall"]
    assert data["place"]["parent"] == {"slug": "probemetro", "name": "Probemetro"}


def test_rows_carry_their_town(client, metro):
    data = client.get(f"{API}?place=probemetro").get_json()
    pub = next(s for s in data["sessions"] if s["path"] == "probemetro/the-pub")
    assert pub["place"] == {"slug": "probetown", "name": "Probetown"}
    assert pub["kind"] == "session"


def test_unknown_or_festival_place_is_404(client):
    assert client.get(f"{API}?place=nowhere").status_code == 404
    assert client.get(f"{API}?place=hill-country-fest").status_code == 404


def test_unscoped_is_everything_with_no_place_block(client, metro):
    data = client.get(API).get_json()
    assert "place" not in data
    assert "probetown/the-hall" in _paths(data)


def test_the_place_page(client, metro):
    resp = client.get("/sessions/probemetro")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<title>Sessions in Probemetro</title>" in html
    assert '"slug": "probetown"' in html  # the embedded payload carries the children


class TestFestivalRows:
    def test_a_festival_is_one_row(self, client, committed):
        committed.session(
            "hill-country-fest/2027",
            1,
            name="Hill Country Trad Fest 2027",
            session_type="festival",
            initiation_date="2027-06-04",
            termination_date="2027-06-06",
        )
        rows = [
            s for s in client.get(API).get_json()["sessions"] if s["kind"] == "festival"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert (row["name"], row["path"], row["years"]) == (
            "Hill Country Trad Fest",
            "hill-country-fest",
            2,
        )
        assert row["place"] == {"slug": "austin", "name": "Austin"}
        # Active while any year is: 2027 ends in the future.
        assert row["termination_date"] == "2027-06-06"

    def test_a_year_with_no_last_day_keeps_it_active(self, client, committed):
        committed.session(
            "hill-country-fest/2027",
            1,
            session_type="festival",
            initiation_date="2027-06-04",
        )
        row = next(
            s for s in client.get(API).get_json()["sessions"] if s["kind"] == "festival"
        )
        assert row["termination_date"] is None

    def test_a_member_of_any_year_is_a_member(self, client, committed):
        from places_helpers import logged_in

        sid = committed.session("hill-country-fest/2027", 1, session_type="festival")
        committed.member(sid, 2)
        with logged_in(client, person_id=2, is_system_admin=False):
            row = next(
                s
                for s in client.get(API).get_json()["sessions"]
                if s["kind"] == "festival"
            )
        assert row["user_is_member"] is True

    def test_the_festival_is_in_its_towns_page(self, client):
        data = client.get(f"{API}?place=austin").get_json()
        assert "hill-country-fest" in _paths(data)
