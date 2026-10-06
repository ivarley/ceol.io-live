"""/sessions/<festival> (spec 056 "Reaching the right year"): a 302 to the year the
window rule picks or to the only year, else the picker; and the same answer from
/api/resolve. Dates are built relative to today so the window holds whenever the
suite runs."""

import datetime as dt

import pytest

from places_helpers import committed, logged_in  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration

TODAY = dt.date.today()
DAY = dt.timedelta(days=1)


@pytest.fixture
def fest(committed):
    """A festival under Austin with three years. Which is in the window is up to
    each test (see years())."""
    fid = committed.place("probefest", "Probe Fest", kind="festival", parent=1)

    def years(*specs):
        ids = {}
        for y, start, end in specs:
            ids[y] = committed.session(
                f"probefest/{y}",
                1,
                name=f"Probe Fest {y}",
                session_type="festival",
                initiation_date=start,
                termination_date=end,
                timezone="America/Chicago",
            )
        return ids

    return {"id": fid, "years": years}


def _loc(resp):
    return resp.headers["Location"].replace("http://localhost", "")


class TestLanding:
    def test_the_only_year_whatever_the_date(self, client):
        # Seed: hill-country-fest has one year, 2026, in June.
        resp = client.get("/sessions/hill-country-fest")
        assert resp.status_code == 302
        assert _loc(resp) == "/sessions/hill-country-fest/2026"

    def test_a_year_in_the_window(self, client, fest):
        fest["years"](
            (2001, TODAY - 400 * DAY, TODAY - 397 * DAY),
            (2002, TODAY + 3 * DAY, TODAY + 6 * DAY),
        )
        resp = client.get("/sessions/probefest")
        assert resp.status_code == 302
        assert _loc(resp) == "/sessions/probefest/2002"

    def test_a_tab_suffix_follows_the_year(self, client, fest):
        fest["years"]((2002, TODAY, TODAY + DAY), (2001, TODAY - 400 * DAY, None))
        resp = client.get("/sessions/probefest/logs")
        assert resp.status_code == 302
        assert _loc(resp) == "/sessions/probefest/2002/logs"

    def test_the_picker_when_no_year_is_near(self, client, fest):
        fest["years"](
            (2001, TODAY - 400 * DAY, TODAY - 397 * DAY),
            (2002, TODAY + 60 * DAY, TODAY + 63 * DAY),
        )
        resp = client.get("/sessions/probefest")
        assert resp.status_code == 200
        assert b"festival-root" in resp.data
        assert b"Probe Fest" in resp.data


class TestPickerPayload:
    def test_order_and_counts(self, client, committed, fest):
        ids = fest["years"](
            (2000, TODAY - 800 * DAY, TODAY - 797 * DAY),
            (2001, TODAY - 400 * DAY, TODAY - 397 * DAY),
            (2002, TODAY + 60 * DAY, TODAY + 63 * DAY),
        )
        logged = committed.instance(ids[2001], TODAY - 399 * DAY)
        committed.instance(ids[2001], TODAY - 398 * DAY)  # nothing logged
        committed.logged_tune(logged, 27)

        data = client.get("/api/resolve?path=probefest").get_json()
        assert data["kind"] == "place"
        assert data["current"] is None
        assert [y["year"] for y in data["years"]] == [2002, 2001, 2000]
        counts = {y["year"]: y["logged_instances"] for y in data["years"]}
        assert counts == {2002: 0, 2001: 1, 2000: 0}
        assert data["latest"]["year"] == 2002

    def test_current_is_the_window_pick(self, client, fest):
        fest["years"](
            (2001, TODAY - 400 * DAY, None), (2002, TODAY - 2 * DAY, TODAY + DAY)
        )
        data = client.get("/api/resolve?path=probefest").get_json()
        assert data["current"] == {"path": "probefest/2002"}

    def test_add_a_year_is_for_admins_of_the_latest_year(self, client, committed, fest):
        ids = fest["years"](
            (2001, TODAY - 400 * DAY, None), (2002, TODAY + 60 * DAY, None)
        )
        committed.member(ids[2001], 2, is_admin=True)  # an admin of an OLDER year only
        with logged_in(client, person_id=2, is_system_admin=False):
            data = client.get("/api/resolve?path=probefest").get_json()
        assert data["permissions"]["can_add_year"] is False

        committed.member(ids[2002], 2, is_admin=True)
        with logged_in(client, person_id=2, is_system_admin=False):
            data = client.get("/api/resolve?path=probefest").get_json()
        assert data["permissions"]["can_add_year"] is True

    def test_signed_out_cannot_add(self, client, fest):
        fest["years"]((2001, TODAY - 400 * DAY, None), (2002, TODAY + 60 * DAY, None))
        data = client.get("/api/resolve?path=probefest").get_json()
        assert data["permissions"]["can_add_year"] is False


class TestSwitcherBlock:
    def test_a_year_carries_its_festival(self, client, fest):
        fest["years"]((2001, TODAY - 400 * DAY, None), (2002, TODAY + 60 * DAY, None))
        data = client.get("/api/sessions/probefest/2001/detail").get_json()
        assert data["festival"]["place"]["slug"] == "probefest"
        assert [y["year"] for y in data["festival"]["years"]] == [2001, 2002]

    def test_a_regular_session_has_none(self, client):
        assert "festival" not in client.get("/api/sessions/austin/mueller/detail").get_json()

    def test_the_admin_payload_too(self, client, fest):
        fest["years"]((2001, TODAY - 400 * DAY, None))
        with logged_in(client):
            data = client.get(
                "/api/admin/sessions/probefest/2001/admin-detail"
            ).get_json()
        assert data["festival"]["years"][0]["path"] == "probefest/2001"

    def test_the_page_heading_is_the_festival(self, client, fest):
        fest["years"]((2001, TODAY - 400 * DAY, None), (2002, TODAY + 60 * DAY, None))
        html = client.get("/sessions/probefest/2001").get_data(as_text=True)
        assert 'href="/sessions/probefest">Probe Fest</a>' in html
        assert 'id="festival-year-root">2001<' in html
