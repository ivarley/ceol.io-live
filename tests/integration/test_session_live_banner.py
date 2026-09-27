"""The session page's "Open Today's Session Log" banner.

The session-detail payload carries `active_instances` (the nights on right now, from
session_instance.is_active), and the page shell leads with one banner per live night,
linking to that night's log. With nothing live there is no banner.
"""
import pytest


@pytest.fixture
def live_fixture(db_cursor, db_conn):
    """A session with every instance switched off except one, restored afterwards: the
    test DB is shared with the dev servers and the active-sessions job owns this flag.
    """
    db_cursor.execute(
        "SELECT session_id, path FROM session ORDER BY session_id LIMIT 1"
    )
    session_id, path = db_cursor.fetchone()
    db_cursor.execute(
        "SELECT session_instance_id, is_active FROM session_instance WHERE session_id = %s ORDER BY date DESC",
        (session_id,),
    )
    saved = db_cursor.fetchall()
    assert saved, "seed must provide at least one instance at the first session"
    live_id = saved[0][0]
    db_cursor.execute(
        "UPDATE session_instance SET is_active = (session_instance_id = %s) WHERE session_id = %s",
        (live_id, session_id),
    )
    db_conn.commit()
    yield {"session_id": session_id, "path": path, "live_id": live_id}
    for instance_id, was_active in saved:
        db_cursor.execute(
            "UPDATE session_instance SET is_active = %s WHERE session_instance_id = %s",
            (was_active, instance_id),
        )
    db_conn.commit()


def _payload(path):
    import database
    from serializers import build_session_detail_payload

    conn = database.get_db_connection()
    try:
        return build_session_detail_payload(conn, path, first_page=5)
    finally:
        conn.close()


class TestActiveInstancesPayload:
    def test_lists_the_live_night(self, live_fixture):
        payload = _payload(live_fixture["path"])
        ids = [i["session_instance_id"] for i in payload["active_instances"]]
        assert ids == [live_fixture["live_id"]]
        assert payload["active_instances"][0]["date"]

    def test_empty_when_nothing_is_on(self, live_fixture, db_cursor, db_conn):
        db_cursor.execute(
            "UPDATE session_instance SET is_active = FALSE WHERE session_id = %s",
            (live_fixture["session_id"],),
        )
        db_conn.commit()
        assert _payload(live_fixture["path"])["active_instances"] == []


class TestBanner:
    def test_page_leads_with_a_link_to_the_live_log(self, client, live_fixture):
        resp = client.get(f"/sessions/{live_fixture['path']}")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert (
            "Open Today&#39;s Session Log" in html or "Open Today's Session Log" in html
        )
        assert (
            f'href="/sessions/{live_fixture["path"]}/{live_fixture["live_id"]}"' in html
        )

    def test_no_banner_when_nothing_is_on(
        self, client, live_fixture, db_cursor, db_conn
    ):
        db_cursor.execute(
            "UPDATE session_instance SET is_active = FALSE WHERE session_id = %s",
            (live_fixture["session_id"],),
        )
        db_conn.commit()
        html = client.get(f"/sessions/{live_fixture['path']}").get_data(as_text=True)
        assert "live-log-banner" not in html
