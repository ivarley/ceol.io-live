"""
The live screen as a LOGGED-OUT visitor (spec 024, public read-only view).

The live logger is now the session-instance page for everyone: /sessions/<path>/<date>
redirects there signed out too, the screen shell and the bootstrap are public, and what
a signed-out viewer gets back is read-only AND stripped of people. Writes stay gated.

The people scrub is the part worth pinning down: it's the one place where "the UI
doesn't render it" is not good enough — the payload itself must not carry names.
"""

import pytest

from database import get_db_connection
from live_logging_routes import strip_people, _PEOPLE_KEYS

pytestmark = pytest.mark.integration

SID = 9400
INST = 9490
TUNE = 9401


@pytest.fixture
def public_instance():
    """A committed throwaway session/instance with one logged tune that HAS people on
    it (a logger and a set starter) — so a failed scrub would be visible."""
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("INSERT INTO session (session_id, name, path) VALUES (%s, %s, %s)",
                (SID, "Public Read Test", "public-read-test"))
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel')",
                (TUNE, "The Public Reel"))
    cur.execute("INSERT INTO session_instance (session_instance_id, session_id, date, is_active) "
                "VALUES (%s, %s, %s, FALSE)", (INST, SID, "2026-02-02"))
    cur.execute("SELECT person_id FROM person ORDER BY person_id LIMIT 1")
    person_id = cur.fetchone()[0]
    cur.execute("SELECT user_id FROM user_account WHERE person_id = %s", (person_id,))
    row = cur.fetchone()
    user_id = row[0] if row else None
    cur.execute(
        "INSERT INTO session_instance_tune "
        "(session_instance_id, tune_id, name, order_position, record_type, "
        " started_by_person_id, created_by_user_id) "
        "VALUES (%s, %s, %s, 'm', 'tune', %s, %s)",
        (INST, TUNE, "The Public Reel", person_id, user_id),
    )
    conn.commit()

    yield {"session_id": SID, "instance_id": INST, "path": "public-read-test",
           "date": "2026-02-02", "person_id": person_id}

    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_event WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (INST,))
    cur.execute("DELETE FROM session_tune WHERE session_id = %s", (SID,))
    cur.execute("DELETE FROM tune WHERE tune_id = %s", (TUNE,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (SID,))
    conn.commit()
    cur.close()
    conn.close()


def test_strip_people_removes_every_people_key():
    record = {"session_instance_tune_id": 1, "name": "X", "tune_id": 2,
              **{k: "leak" for k in _PEOPLE_KEYS}}
    out = strip_people(record)
    assert set(out) == {"session_instance_tune_id", "name", "tune_id"}


class TestPublicScreen:
    def test_instance_url_redirects_anonymous_to_the_live_screen(self, client, public_instance):
        """The legacy pill page is not the signed-out view any more."""
        resp = client.get(f"/sessions/{public_instance['path']}/{public_instance['date']}")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/live/instances/{public_instance['instance_id']}")

    def test_screen_shell_is_public(self, client, public_instance):
        resp = client.get(f"/live/instances/{public_instance['instance_id']}")
        assert resp.status_code == 200
        html = resp.data.decode()
        # The shell tells the bundle it is read-only, with no person.
        assert '"canEdit": false' in html or "canEdit: false" in html
        assert "currentPerson: null" in html


class TestPublicBootstrap:
    def test_anonymous_bootstrap_is_readable_but_has_no_people(self, client, public_instance):
        resp = client.get(f"/api/live/instances/{public_instance['instance_id']}/bootstrap")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["can_edit"] is False
        assert body["current_person"] is None
        assert body["records"], "the log itself must still be readable"
        for record in body["records"] + [r for s in body["sets"] for r in s]:
            for key in _PEOPLE_KEYS:
                assert key not in record, f"anonymous bootstrap leaked {key}"

    def test_signed_in_bootstrap_still_carries_people(self, client, authenticated_user, public_instance):
        with authenticated_user:
            resp = client.get(f"/api/live/instances/{public_instance['instance_id']}/bootstrap")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["can_edit"] is True
        assert body["current_person"] is not None
        record = body["records"][0]
        assert "logged_by" in record and "started_by_name" in record

    def test_bootstrap_reports_whether_the_session_is_under_way(self, client, public_instance):
        """Signed-out viewers stream only while the instance is active; the client
        re-reads this on every reconnect, so it must be in the payload."""
        resp = client.get(f"/api/live/instances/{public_instance['instance_id']}/bootstrap")
        assert resp.get_json()["instance_active"] is False


class TestPublicIsReadOnly:
    def test_ops_still_require_auth(self, client, public_instance):
        resp = client.post(f"/api/live/instances/{public_instance['instance_id']}/ops",
                           json={"op_type": "edit_notes", "notes": "nope"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["people", "vocabulary"])
    def test_people_and_vocabulary_stay_gated(self, client, public_instance, path):
        resp = client.get(f"/api/live/instances/{public_instance['instance_id']}/{path}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# searching thesession.org while signed out (spec 052 §B20)
# ---------------------------------------------------------------------------


class TestThesessionSearchIsPublic:
    """The tune catalogue is thesession.org's and is public there; this endpoint only
    proxies a search of it. It is offered signed-out so the public /tunes tab can
    reach past Ceol's own catalogue.

    The network is mocked: a test that really calls thesession.org fails when their
    site is slow, which says nothing about this code.
    """

    _PAYLOAD = {
        "tunes": [
            {"id": 9, "name": "Banish Misfortune", "type": "jig",
             "url": "https://thesession.org/tunes/9"},
            {"id": 999999, "name": "Not In Ceol", "type": "reel",
             "url": "https://thesession.org/tunes/999999"},
        ]
    }

    def _mock(self):
        from unittest.mock import patch, Mock

        resp = Mock(status_code=200)
        resp.json.return_value = self._PAYLOAD
        return patch("live_logging_routes.requests.get", return_value=resp)

    def test_a_signed_out_visitor_gets_results(self, client):
        with self._mock():
            resp = client.get("/api/tunes/thesession-search?q=banish")
        assert resp.status_code == 200, "this is the public tune tab's reach"
        body = resp.get_json()
        assert body["success"] is True
        assert [r["name"] for r in body["results"]] == ["Banish Misfortune", "Not In Ceol"]

    def test_it_says_which_hits_ceol_already_has(self, client):
        # The /tunes page uses this to decide whether a row opens the tune drawer or
        # leaves for thesession.org — without it every hit would have to leave.
        with self._mock():
            body = client.get("/api/tunes/thesession-search?q=banish").get_json()
        by_id = {r["tune_id"]: r for r in body["results"]}
        assert by_id[9]["is_local"] is True
        assert by_id[999999]["is_local"] is False

    def test_signed_out_carries_no_personalisation(self, client):
        # current_user is personalisation ONLY. With nobody signed in there is no list
        # to compare against, and the flags must not claim otherwise.
        with self._mock():
            body = client.get("/api/tunes/thesession-search?q=banish").get_json()
        for r in body["results"]:
            assert r["on_list"] is False
            assert r["in_session"] is False

    def test_a_short_query_never_reaches_thesession(self, client):
        # One character would match most of the catalogue; the guard is in the handler
        # rather than only in the UI, because the UI is not the only caller.
        from unittest.mock import patch

        with patch("live_logging_routes.requests.get") as get:
            resp = client.get("/api/tunes/thesession-search?q=a")
        assert resp.status_code == 200
        assert resp.get_json()["results"] == []
        get.assert_not_called()

    def test_the_personalised_deep_search_is_still_gated(self, client):
        # Relaxing the proxy does not relax the rest: /api/tunes/deep-search reports
        # what is on YOUR list, so it still needs an account.
        assert client.get("/api/tunes/deep-search?q=banish").status_code == 401
