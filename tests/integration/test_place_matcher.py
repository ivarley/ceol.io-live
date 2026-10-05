"""The place matcher and the two session write paths (spec 055).

Seed places: austin (1), boston (2), chicago (3), sf "San Francisco" (4), all US;
hill-country-fest (5), a festival under Austin.
"""

import pytest

import places
from places_helpers import PROBE, committed, logged_in  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration


def _create(client, **fields):
    payload = {
        "name": f"{PROBE} {fields.get('path', fields.get('festival_name', ''))}",
        "city": "Austin",
        "state": "TX",
        "country": "USA",
        "add_current_user": False,
        **fields,
    }
    with logged_in(client):
        return client.post("/api/add-session", json=payload)


def _session(committed, path):
    rows = committed.query(
        "SELECT s.place_id, p.slug, s.city, s.state, s.country, s.session_type, s.name "
        "FROM session s LEFT JOIN place p ON p.place_id = s.place_id WHERE s.path = %s",
        (path,),
    )
    return rows[0] if rows else None


class TestMatch:
    def test_same_slug_same_geography_matches(self, committed):
        m = places.match_place(committed.cur, "Austin", "tx", "U.S.A.")
        assert (m["status"], m["place"]["slug"]) == ("match", "austin")

    def test_a_town_whose_slug_is_not_its_name(self, committed):
        m = places.match_place(committed.cur, "San Francisco", "CA", "USA")
        assert (m["status"], m["place"]["slug"]) == ("match", "sf")

    def test_unknown_city_is_new_with_normalized_geography(self, committed):
        m = places.match_place(committed.cur, "Probetown", "TX", "usa")
        assert m["status"] == "new"
        assert (m["slug"], m["name"], m["area"], m["country"]) == (
            "probetown",
            "Probetown",
            "Texas",
            "United States",
        )

    def test_same_slug_elsewhere_is_ambiguous(self, committed):
        m = places.match_place(committed.cur, "Austin", "VT", "USA")
        assert m["status"] == "ambiguous"
        assert m["place"]["slug"] == "austin"
        assert m["slug"] == "austin-vt"

    def test_disambiguates_by_country_without_an_area(self, committed):
        committed.place("athens", "Athens", area="Georgia")
        m = places.match_place(committed.cur, "Athens", "", "Greece")
        assert (m["status"], m["slug"]) == ("ambiguous", "athens-greece")

    def test_the_second_athens_is_found_again(self, committed):
        committed.place("athens", "Athens", area="Georgia")
        committed.place("athens-greece", "Athens", area=None, country="Greece")
        m = places.match_place(committed.cur, "Athens", "", "Greece")
        assert (m["status"], m["place"]["slug"]) == ("match", "athens-greece")

    def test_a_festival_slug_is_not_a_town_to_mean(self, committed):
        m = places.match_place(committed.cur, "Hill Country Fest", "TX", "USA")
        assert m["status"] == "new"
        assert m["slug"] == "hill-country-fest-tx"

    def test_endpoint_reports_prefixes_town_first(self, client, committed):
        probemetro = committed.place("probemetro", "Probemetro")
        committed.place("probetown", "Probetown", parent=probemetro)
        with logged_in(client):
            data = client.get(
                "/api/places/match?city=Probetown&state=TX&country=USA"
            ).get_json()
        assert data["status"] == "match"
        assert data["path_prefixes"] == ["probetown", "probemetro"]
        assert data["place"]["parent"] == {"slug": "probemetro", "name": "Probemetro"}


class TestRule:
    def _check(self, committed, path, session_type="regular", town="austin"):
        town_id = places.get_place_by_slug(committed.cur, town)["place_id"]
        return places.validate_path_for_place(
            committed.cur, path, session_type, town_id
        )

    def test_town_and_name(self, committed):
        assert self._check(committed, "austin/mueller") is None

    def test_unknown_first_segment(self, committed):
        assert "no place" in self._check(committed, "atx/mueller")

    def test_a_year_under_a_town(self, committed):
        assert "year" in self._check(committed, "austin/2026")

    def test_festival_year(self, committed):
        assert self._check(committed, "hill-country-fest/2027", "festival") is None

    def test_a_name_under_a_festival(self, committed):
        assert "year" in self._check(committed, "hill-country-fest/late", "festival")

    def test_a_regular_session_under_a_festival(self, committed):
        assert "festival" in self._check(committed, "hill-country-fest/2027")

    def test_a_festival_under_a_town(self, committed):
        assert "festival" in self._check(committed, "austin/acf", "festival")

    def test_metro_contains_its_town(self, committed):
        probemetro = committed.place("probemetro", "Probemetro")
        committed.place("probetown", "Probetown", parent=probemetro)
        assert self._check(committed, "probemetro/the-pub", town="probetown") is None
        assert self._check(committed, "probetown/the-pub", town="probetown") is None

    def test_a_place_that_does_not_contain_the_town(self, committed):
        committed.place("probetown", "Probetown")
        assert "town" in self._check(committed, "austin/the-pub", town="probetown")


class TestCreate:
    def test_matches_an_existing_town(self, client, committed):
        resp = _create(client, path="austin/probe-one")
        assert resp.get_json()["success"] is True, resp.get_json()
        place_id, slug, city, state, country, *_ = _session(
            committed, "austin/probe-one"
        )
        # Geography is written from the town, in the long form.
        assert (slug, city, state, country) == (
            "austin",
            "Austin",
            "Texas",
            "United States",
        )

    def test_creates_a_new_town(self, client, committed):
        resp = _create(client, path="probetown/probe", city="Probetown")
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "probetown/probe")[1] == "probetown"
        assert committed.query(
            "SELECT name, area, country FROM place WHERE slug = 'probetown'"
        ) == [("Probetown", "Texas", "United States")]

    def test_ambiguous_is_a_409_and_creates_nothing(self, client, committed):
        resp = _create(client, path="austin/probe-vt", state="VT")
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["code"] == "place_ambiguous"
        assert data["place"]["slug"] == "austin"
        assert data["suggested_slug"] == "austin-vt"
        assert _session(committed, "austin/probe-vt") is None
        assert committed.query("SELECT 1 FROM place WHERE slug = 'austin-vt'") == []

    def test_resubmit_with_the_existing_place(self, client, committed):
        resp = _create(client, path="austin/probe-pick", state="VT", place_id=1)
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "austin/probe-pick")[1] == "austin"

    def test_resubmit_as_a_new_place(self, client, committed):
        resp = _create(client, path="austin-vt/probe-new", state="VT", place_new=True)
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "austin-vt/probe-new")[1] == "austin-vt"

    def test_generated_prefix_follows_the_town(self, client, committed):
        # The sheet generated san-francisco/...; the town is `sf`.
        resp = _create(
            client, path="san-francisco/probe", city="San Francisco", state="CA"
        )
        data = resp.get_json()
        assert data["success"] is True, data
        assert data["session_path"] == "sf/probe"
        assert _session(committed, "sf/probe")[1] == "sf"

    def test_a_place_that_does_not_contain_the_town_is_refused(self, client, committed):
        resp = _create(client, path="boston/probe")
        assert resp.status_code == 400
        assert "town" in resp.get_json()["message"]

    def test_one_segment_is_refused(self, client, committed):
        resp = _create(client, path="probe")
        assert resp.status_code == 400

    def test_new_festival_and_first_year(self, client, committed):
        resp = _create(
            client,
            session_type="festival",
            festival_name="Probe Trad Weekend",
            year="2027",
            name="",
        )
        data = resp.get_json()
        assert data["success"] is True, data
        assert data["session_path"] == "probe-trad-weekend/2027"
        place_id, slug, *_, session_type, name = _session(
            committed, "probe-trad-weekend/2027"
        )
        assert (slug, session_type, name) == (
            "austin",
            "festival",
            "Probe Trad Weekend 2027",
        )
        assert committed.query(
            "SELECT kind, parent_place_id, name FROM place WHERE slug = 'probe-trad-weekend'"
        ) == [("festival", 1, "Probe Trad Weekend")]

    def test_new_festival_dates(self, client, committed):
        resp = _create(
            client,
            session_type="festival",
            festival_name="Probe Dates Fest",
            year="2027",
            inception_date="2027-10-21",
            termination_date="2027-10-24",
            recurrence='{"schedules": []}',
        )
        assert resp.get_json()["success"] is True, resp.get_json()
        assert committed.query(
            "SELECT initiation_date::text, termination_date::text, recurrence FROM session "
            "WHERE path = 'probe-dates-fest/2027'"
        ) == [("2027-10-21", "2027-10-24", None)]

    def test_new_festival_inverted_dates(self, client, committed):
        resp = _create(
            client,
            session_type="festival",
            festival_name="Probe Dates Fest",
            year="2027",
            inception_date="2027-10-24",
            termination_date="2027-10-21",
        )
        assert resp.status_code == 400

    def test_another_year_of_the_same_festival(self, client, committed):
        resp = _create(
            client,
            session_type="festival",
            festival_name="Hill Country Fest",
            year="2027",
            name=f"{PROBE} hcf",
        )
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "hill-country-fest/2027")[5] == "festival"

    def test_festival_slug_taken_by_a_town(self, client, committed):
        resp = _create(
            client, session_type="festival", festival_name="Boston", year="2027"
        )
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "slug_taken"

    def test_festival_the_old_way_is_refused(self, client, committed):
        resp = _create(client, path="austin/probe-fest", session_type="festival")
        assert resp.status_code == 400


class TestAdminUpdate:
    def _put(self, client, at, **fields):
        with logged_in(client):
            return client.put(f"/api/sessions/{at}/admin-update", json=fields)

    def test_rename_writes_a_redirect(self, client, committed):
        committed.session("austin/probe-old", 1)
        resp = self._put(client, "austin/probe-old", path="austin/probe-new")
        assert resp.get_json()["success"] is True, resp.get_json()
        assert committed.query(
            "SELECT to_path FROM path_redirect WHERE from_path = 'austin/probe-old'"
        ) == [("austin/probe-new",)]

    def test_renaming_back_drops_the_stale_row(self, client, committed):
        committed.session("austin/probe-a", 1)
        self._put(client, "austin/probe-a", path="austin/probe-b")
        self._put(client, "austin/probe-b", path="austin/probe-a")
        assert committed.query(
            "SELECT from_path, to_path FROM path_redirect WHERE from_path LIKE 'austin/probe-%%'"
        ) == [("austin/probe-b", "austin/probe-a")]

    def test_rename_to_a_place_outside_the_town_is_refused(self, client, committed):
        committed.session("austin/probe-x", 1)
        resp = self._put(client, "austin/probe-x", path="boston/probe-x")
        assert resp.status_code == 400

    def test_unchanged_form_save_leaves_the_town_alone(self, client, committed):
        committed.session("austin/probe-same", 1)
        resp = self._put(
            client,
            "austin/probe-same",
            path="austin/probe-same",
            name=f"{PROBE} renamed",
            city="Austin",
            state="TX",
            country="USA",
        )
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "austin/probe-same")[0] == 1

    def test_moving_town_needs_a_path_that_fits(self, client, committed):
        committed.session("austin/probe-move", 1)
        resp = self._put(
            client, "austin/probe-move", city="Boston", state="MA", country="USA"
        )
        assert resp.status_code == 400
        resp = self._put(
            client,
            "austin/probe-move",
            path="boston/probe-move",
            city="Boston",
            state="MA",
            country="USA",
        )
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "boston/probe-move")[:3] == (2, "boston", "Boston")

    def test_a_pre_055_path_can_still_be_saved(self, client, committed):
        # One segment, no town: saving the rest of the form must not be blocked.
        committed.session("probelegacy", None)
        resp = self._put(
            client,
            "probelegacy",
            path="probelegacy",
            name=f"{PROBE} legacy",
            city="Austin",
            state="TX",
            country="USA",
        )
        assert resp.get_json()["success"] is True, resp.get_json()
        assert _session(committed, "probelegacy")[1] == "austin"
