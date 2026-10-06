"""The Places admin API (spec 055 "Places admin page"): site admins only."""

import pytest

from places_helpers import committed, logged_in  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration


def _put(client, place_id, **body):
    with logged_in(client):
        return client.put(f"/api/admin/places/{place_id}", json=body)


@pytest.fixture
def town(committed):
    """probetown with two sessions filed under its slug, and one old redirect that
    already points at one of them."""
    t = committed.place("probetown", "Probetown")
    committed.session("probetown/the-pub", t)
    committed.session("probetown/the-hall", t)
    committed.redirect("probetown/old-pub", "probetown/the-pub")
    return t


def test_only_a_site_admin(client, town):
    with logged_in(client, person_id=1, is_system_admin=False):
        assert client.get("/api/admin/places").status_code == 403
        assert (
            client.put(f"/api/admin/places/{town}", json={"name": "X"}).status_code
            == 403
        )
        assert client.post("/api/admin/places", json={"name": "X"}).status_code == 403
        assert client.delete(f"/api/admin/places/{town}").status_code == 403


def test_the_payload_counts(client, town):
    with logged_in(client):
        places = client.get("/api/admin/places").get_json()["places"]
    row = next(p for p in places if p["slug"] == "probetown")
    assert (row["town_sessions"], row["paths"], row["children"]) == (2, 2, 0)


def test_rename_moves_paths_and_writes_redirects(client, committed, town):
    resp = _put(client, town, name="Probetown", slug="probe-town")
    data = resp.get_json()
    assert data["success"] is True, data
    assert sorted(m["to"] for m in data["moved"]) == [
        "probe-town/the-hall",
        "probe-town/the-pub",
    ]
    redirects = dict(
        committed.query(
            "SELECT from_path, to_path FROM path_redirect WHERE from_path LIKE 'probetown%%'"
        )
    )
    assert redirects == {
        "probetown/the-pub": "probe-town/the-pub",
        "probetown/the-hall": "probe-town/the-hall",
        "probetown/old-pub": "probe-town/the-pub",  # the chain collapsed
        "probetown": "probe-town",  # the bare prefix
    }


def test_old_addresses_redirect_after_a_rename(client, town):
    _put(client, town, name="Probetown", slug="probe-town")
    resp = client.get("/sessions/probetown/the-pub/tunes")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/sessions/probe-town/the-pub/tunes")
    resp = client.get("/sessions/probetown")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/sessions/probe-town")


def test_rename_to_a_taken_slug(client, town):
    resp = _put(client, town, name="Probetown", slug="austin")
    assert resp.status_code == 400
    assert "taken" in resp.get_json()["error"]


def test_rename_to_a_bad_slug(client, town):
    assert _put(client, town, name="Probetown", slug="Probe Town").status_code == 400
    assert _put(client, town, name="Probetown", slug="2026").status_code == 400


def test_edit_relabels_the_towns_sessions(client, committed, town):
    resp = _put(client, town, name="Probe Town", area="tx", country="USA")
    assert resp.get_json()["success"] is True
    rows = committed.query(
        "SELECT DISTINCT city, state, country FROM session WHERE place_id = %s", (town,)
    )
    assert rows == [("Probe Town", "Texas", "United States")]


def test_set_and_clear_a_parent(client, committed, town):
    metro = committed.place("probemetro", "Probemetro")
    assert _put(client, town, name="Probetown", parent_place_id=metro).get_json()[
        "success"
    ]
    assert committed.query(
        "SELECT parent_place_id FROM place WHERE place_id = %s", (town,)
    ) == [(metro,)]
    assert _put(client, town, name="Probetown", parent_place_id=None).get_json()[
        "success"
    ]
    assert committed.query(
        "SELECT parent_place_id FROM place WHERE place_id = %s", (town,)
    ) == [(None,)]


def test_a_parent_cycle_is_refused(client, committed, town):
    metro = committed.place("probemetro", "Probemetro")
    _put(client, town, name="Probetown", parent_place_id=metro)
    resp = _put(client, metro, name="Probemetro", parent_place_id=town)
    assert resp.status_code == 400
    assert "inside" in resp.get_json()["error"]
    assert _put(client, town, name="Probetown", parent_place_id=town).status_code == 400


def test_a_festival_cannot_be_a_parent(client, town):
    assert _put(client, town, name="Probetown", parent_place_id=5).status_code == 400


def test_add_a_metro(client, committed):
    with logged_in(client):
        resp = client.post(
            "/api/admin/places",
            json={"name": "Probe Metro", "area": "TX", "country": "US"},
        )
    assert resp.status_code == 201, resp.get_json()
    assert committed.query(
        "SELECT slug, area, country, kind FROM place WHERE name = 'Probe Metro'"
    ) == [("probe-metro", "Texas", "United States", "place")]


def test_delete_refuses_a_place_with_sessions(client, town):
    with logged_in(client):
        resp = client.delete(f"/api/admin/places/{town}")
    assert resp.status_code == 400
    assert "sessions" in resp.get_json()["error"]


def test_delete_refuses_a_place_with_children(client, committed):
    metro = committed.place("probemetro", "Probemetro")
    committed.place("probetown2", "Probetown2", parent=metro)
    with logged_in(client):
        resp = client.delete(f"/api/admin/places/{metro}")
    assert resp.status_code == 400
    assert "Probetown2" in resp.get_json()["error"]


def test_delete_an_unused_place(client, committed):
    metro = committed.place("probemetro", "Probemetro")
    with logged_in(client):
        resp = client.delete(f"/api/admin/places/{metro}")
    assert resp.get_json()["success"] is True
    assert committed.query("SELECT 1 FROM place WHERE place_id = %s", (metro,)) == []
