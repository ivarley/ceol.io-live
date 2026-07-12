"""The last two page-payload endpoints (spec 035 final migration):

  * GET /api/add-session   — @public_api; the /add-session shell embeds the same
    serializers.build_add_session_payload output. POST /api/add-session (the
    actual create, @api_login_required) shares the rule and must stay gated.
  * GET /api/admin/people  — system-admin only; the /admin/people shell embeds
    the same serializers.build_admin_people_payload output.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from auth import User


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


@pytest.mark.integration
class TestAddSessionPayload:
    def test_anonymous_gets_payload(self, client):
        """The wizard is public — anyone can browse it."""
        resp = client.get("/api/add-session")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["viewer"]["logged_in"] is False
        assert data["default_timezone"] == "America/Chicago"
        options = data["timezone_options"]
        assert isinstance(options, list) and len(options) > 0
        assert {"value", "label"} == set(options[0].keys())
        # The wizard's US-state guess can land on Arizona.
        assert any(o["value"] == "America/Phoenix" for o in options)

    def test_logged_in_viewer_flag(self, client):
        with logged_in(client, person_id=2):
            data = client.get("/api/add-session").get_json()
        assert data["viewer"]["logged_in"] is True

    def test_shell_embeds_same_payload(self, client):
        """The invariant: the page shell and the API share one serializer."""
        page = client.get("/add-session")
        assert page.status_code == 200
        assert b"window.__PAGE_DATA__" in page.data
        assert b"timezone_options" in page.data

    def test_post_contract_unchanged(self, client):
        """The create POST on the same rule stays login-gated (401 JSON)."""
        resp = client.post(
            "/api/add-session",
            json={"name": "X", "path": "x/x", "city": "X", "state": "X", "country": "X"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False


@pytest.mark.integration
class TestAdminPeoplePayload:
    def test_anonymous_gets_401(self, client):
        resp = client.get("/api/admin/people")
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False

    def test_non_admin_gets_403(self, client):
        with logged_in(client, person_id=2, is_system_admin=False):
            resp = client.get("/api/admin/people")
        assert resp.status_code == 403
        assert resp.get_json()["success"] is False

    def test_admin_gets_people(self, client):
        with logged_in(client, person_id=1, is_system_admin=True):
            resp = client.get("/api/admin/people")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        people = data["people"]
        assert len(people) > 0  # seeded people

        person = people[0]
        expected_keys = {
            "person_id", "name", "email", "city", "state", "country",
            "thesession_user_id", "username", "is_system_admin", "last_login",
            "session_count", "session_instance_count", "latest_session_date",
            "latest_session_name", "tune_count", "last_logged_tune",
            "last_tunebook_update",
        }
        assert expected_keys == set(person.keys())

        # Raw JSON-friendly values: counts are ints, dates are ISO strings/null.
        for p in people:
            assert isinstance(p["session_count"], int)
            assert isinstance(p["tune_count"], int)
            for date_key in ("last_login", "last_logged_tune", "last_tunebook_update"):
                assert p[date_key] is None or isinstance(p[date_key], str)
            if p["latest_session_date"] is not None:
                # DATE column -> date-only ISO string (the client displays it
                # verbatim; never Date-parsed, so no west-of-UTC off-by-one).
                assert len(p["latest_session_date"]) == 10

        # The seeded admin person is present (matches the legacy page's rows).
        assert any("Varley" in p["name"] for p in people)

    def test_shell_requires_admin(self, client):
        """The HTML page keeps its redirect-based gating for non-admins."""
        with logged_in(client, person_id=2, is_system_admin=False):
            resp = client.get("/admin/people")
        assert resp.status_code == 302

    def test_shell_embeds_same_payload(self, client):
        with logged_in(client, person_id=1, is_system_admin=True):
            page = client.get("/admin/people")
        assert page.status_code == 200
        assert b"window.__PAGE_DATA__" in page.data
        assert b"Varley" in page.data
