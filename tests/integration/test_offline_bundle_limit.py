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


# The version tag: a browser holding the current copy gets a 304 and nothing is built.


def _get(client, authenticated_user, etag=None):
    headers = {"If-None-Match": etag} if etag else {}
    with authenticated_user:
        return client.get("/api/offline/bundle", headers=headers)


def test_the_bundle_carries_its_version(client, authenticated_user):
    resp = _get(client, authenticated_user)
    assert resp.status_code == 200
    assert resp.headers["ETag"].startswith('"')
    assert "no-store" in resp.headers["Cache-Control"]


def test_an_unchanged_bundle_is_a_304_and_nothing_is_built(
    client, authenticated_user, monkeypatch
):
    etag = _get(client, authenticated_user).headers["ETag"]
    built = []
    real = routes._build_offline_bundle
    monkeypatch.setattr(
        routes, "_build_offline_bundle", lambda: built.append(1) or real()
    )
    resp = _get(client, authenticated_user, etag)
    assert resp.status_code == 304 and resp.data == b""
    assert resp.headers["ETag"] == etag
    assert built == []
    # Cloudflare weakens a tag when it compresses; the weak form still matches.
    assert _get(client, authenticated_user, "W/" + etag).status_code == 304


def test_a_change_to_the_tunebook_changes_the_version(
    client, authenticated_user, db_conn, db_cursor
):
    etag = _get(client, authenticated_user).headers["ETag"]
    db_cursor.execute(
        "SELECT person_tune_id, notes FROM person_tune WHERE person_id = 2 LIMIT 1"
    )
    row = db_cursor.fetchone()
    assert row, "the seeded regular user has tunes"
    person_tune_id, notes = row[0], row[1]
    db_cursor.execute(
        "UPDATE person_tune SET notes = %s WHERE person_tune_id = %s",
        ((notes or "") + " (changed)", person_tune_id),
    )
    db_conn.commit()
    try:
        resp = _get(client, authenticated_user, etag)
        assert resp.status_code == 200
        assert resp.headers["ETag"] != etag
    finally:
        db_cursor.execute(
            "UPDATE person_tune SET notes = %s WHERE person_tune_id = %s",
            (notes, person_tune_id),
        )
        db_conn.commit()
