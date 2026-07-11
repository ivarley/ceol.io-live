"""Authorization on person-scoped API endpoints (spec 035 follow-up).

These endpoints shipped with no guard at all — /api/person/<id>/logins returned
any person's login history (IPs, user agents) to anonymous callers. They are now
admin-or-self (api_auth.api_admin_or_self_required). The session logs feed stays
deliberately public (@public_api): it backs the logged-out session detail page.

NOTE: the shared `authenticated_user` fixture is a SYSTEM ADMIN
(sample_user_data.is_system_admin=True), so the 403 path needs the local
non-admin context below.
"""

from contextlib import contextmanager
from unittest.mock import patch

from auth import User


GATED_GETS = [
    "/api/person/{pid}/logins",
    "/api/person/{pid}/attended",
    "/api/person/{pid}/tunes-stats",
    "/api/person/{pid}/available-sessions",
    "/api/person/{pid}/active_session",
]


@contextmanager
def logged_in(client, person_id, is_system_admin=False):
    """Minimal session login mirroring the conftest fixture, but with control
    over person_id and admin-ness (user_id 2 = a seeded non-admin account)."""
    user = User(
        user_id=1 if is_system_admin else 2,
        person_id=person_id,
        username="admin" if is_system_admin else "regular",
        email="t@example.com",
        first_name="T",
        last_name="U",
        is_active=True,
        is_system_admin=is_system_admin,
        timezone="UTC",
        email_verified=True,
    )
    with patch("auth.User.get_by_id", return_value=user):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.user_id)
            sess["_fresh"] = True
            sess["is_system_admin"] = is_system_admin
            sess["admin_session_ids"] = []
        yield user
        with client.session_transaction() as sess:
            sess.clear()


class TestPersonEndpointAuth:
    def test_anonymous_gets_401(self, client):
        for url in GATED_GETS:
            resp = client.get(url.format(pid=1))
            assert resp.status_code == 401, url
            assert resp.get_json()["success"] is False
        assert client.post("/api/person/1/search-sessions", json={"query": "x"}).status_code == 401

    def test_other_user_gets_403(self, client):
        with logged_in(client, person_id=2, is_system_admin=False):
            for url in GATED_GETS:
                resp = client.get(url.format(pid=999999))
                assert resp.status_code == 403, url
            resp = client.post("/api/person/999999/search-sessions", json={"query": "x"})
            assert resp.status_code == 403

    def test_self_allowed(self, client):
        with logged_in(client, person_id=2, is_system_admin=False):
            for url in GATED_GETS:
                resp = client.get(url.format(pid=2))
                assert resp.status_code == 200, url

    def test_admin_allowed_for_others(self, client):
        with logged_in(client, person_id=1, is_system_admin=True):
            for url in GATED_GETS:
                resp = client.get(url.format(pid=2))
                assert resp.status_code == 200, url

    def test_session_logs_stay_public(self, client):
        """The Logs tab is visible logged-out — the feed must remain public."""
        resp = client.get("/api/sessions/austin/mueller/logs")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_removed_person_tunes_endpoints_are_gone(self, client):
        """The orphaned /api/person/tunes* endpoints (only caller was the deleted
        legacy tune_detail_modal.js) are deleted, not just unlinked."""
        assert client.get("/api/person/tunes/55").status_code == 404
        assert client.post("/api/person/tunes", json={"tune_id": 55}).status_code == 404
        assert client.put("/api/person/tunes/55/status", json={}).status_code == 404
        assert client.get("/api/person/1/tunes").status_code == 404
