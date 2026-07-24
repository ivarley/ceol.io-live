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
