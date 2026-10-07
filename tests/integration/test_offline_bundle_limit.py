"""The offline bundle is built one at a time per worker process (2026-10-07: eleven
browser tabs asked for an admin's ~11 MB bundle at once and the instance ran out of
memory). A request that can't get a turn in time gets a quick 503."""

import pytest

import api_person_tune_routes as routes

pytestmark = pytest.mark.integration


def test_a_bundle_still_builds(client, authenticated_user):
    with authenticated_user:
        resp = client.get("/api/offline/bundle")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_a_second_build_waits_then_gives_up(client, authenticated_user, monkeypatch):
    monkeypatch.setattr(routes, "OFFLINE_BUNDLE_WAIT_S", 0.05)
    assert routes._OFFLINE_BUNDLE_BUILDS.acquire(timeout=1)  # a build in progress
    try:
        with authenticated_user:
            resp = client.get("/api/offline/bundle")
    finally:
        routes._OFFLINE_BUNDLE_BUILDS.release()
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["code"] == "offline_bundle_busy" and body["retry_after"] == 30
    with authenticated_user:
        assert (
            client.get("/api/offline/bundle").status_code == 200
        )  # the slot is free again
