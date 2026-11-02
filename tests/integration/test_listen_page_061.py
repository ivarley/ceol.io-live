"""
Listen on the web, Ad-hoc mode (spec 061 stage 3): the /listen page and the ways in
to it (the fifth tab, Home's "What tune is this?", and the flag the "Add a tune"
searches read), all only for those who may listen on Ceol's server. From a search,
/listen carries the session or the night the sure tune can go to, and where to go
back to, which must be a path on this site.
"""

import json
import re

import pytest

SARAH = 2  # the seeded non-admin authenticated_user stands for


@pytest.fixture
def sarah_may_listen(db_setup):
    from database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()

    def set_right(allowed):
        cur.execute(
            "UPDATE user_account SET can_listen_on_server = %s WHERE user_id = %s",
            (allowed, SARAH),
        )
        conn.commit()

    yield set_right
    set_right(False)
    conn.close()


@pytest.fixture
def a_night(db_setup):
    """A seeded night: (instance_id, session name, session path)."""
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT si.session_instance_id, s.name, s.path
               FROM session_instance si JOIN session s ON s.session_id = si.session_id
               ORDER BY si.session_instance_id LIMIT 1"""
        )
        return cur.fetchone()
    finally:
        conn.close()


def _payload(html):
    m = re.search(rb"window\.__PAGE_DATA__ = (.*?);</script>", html)
    assert m, "no payload"
    return json.loads(m.group(1))


def test_listen_sends_others_home(client, authenticated_user, sarah_may_listen):
    with authenticated_user:
        assert client.get("/listen").status_code == 302


def test_listen_signed_out_goes_to_login(client, db_setup):
    resp = client.get("/listen")
    assert resp.status_code == 302
    assert "login" in resp.headers["Location"]


def test_listen_is_there_for_a_listener_with_no_context(
    client, authenticated_user, sarah_may_listen
):
    sarah_may_listen(True)
    with authenticated_user:
        page = client.get("/listen")
        assert page.status_code == 200
        assert b'id="listen-root"' in page.data
        assert b"listenpage/page.js" in page.data
        assert _payload(page.data) == {"success": True, "context": None}


def test_from_a_session_search_it_carries_the_session(
    client, authenticated_user, sarah_may_listen, a_night
):
    sarah_may_listen(True)
    _, name, path = a_night
    with authenticated_user:
        page = client.get(f"/listen?session={path}&back=/sessions/{path}/tunes")
        ctx = _payload(page.data)["context"]
        assert ctx == {
            "kind": "session",
            "session_name": name,
            "session_path": path,
            "back": f"/sessions/{path}/tunes",
        }


def test_from_a_night_search_it_carries_the_night(
    client, authenticated_user, sarah_may_listen, a_night
):
    sarah_may_listen(True)
    instance_id, name, path = a_night
    with authenticated_user:
        ctx = _payload(client.get(f"/listen?instance={instance_id}").data)["context"]
        assert ctx["kind"] == "night"
        assert ctx["instance_id"] == instance_id
        assert ctx["session_name"] == name
        assert re.match(r"\d{4}-\d{2}-\d{2}$", ctx["date"])
        # no back given: the night's logger
        assert ctx["back"] == f"/live/instances/{instance_id}"


@pytest.mark.parametrize(
    "back",
    [
        "https://evil.example.com/",
        "//evil.example.com/",
        "/\\evil.example.com",
        "javascript:alert(1)",
    ],
)
def test_back_is_only_ever_a_path_on_this_site(
    client, authenticated_user, sarah_may_listen, a_night, back
):
    sarah_may_listen(True)
    _, _, path = a_night
    with authenticated_user:
        ctx = _payload(
            client.get("/listen", query_string={"session": path, "back": back}).data
        )["context"]
        assert ctx["back"] == f"/sessions/{path}"


def test_an_unknown_session_or_night_is_no_context(
    client, authenticated_user, sarah_may_listen
):
    sarah_may_listen(True)
    with authenticated_user:
        assert (
            _payload(client.get("/listen?session=no/such-session").data)["context"]
            is None
        )
        assert (
            _payload(client.get("/listen?instance=999999999").data)["context"] is None
        )


def test_a_listener_has_the_fifth_tab_and_the_search_flag(
    client, authenticated_user, sarah_may_listen
):
    sarah_may_listen(True)
    with authenticated_user:
        page = client.get("/sessions").data
        assert b'data-tab="listen"' in page
        assert b'href="/listen" class="header-nav-item' in page
        assert b"window.CEOL_LISTENS = true;" in page


def test_others_keep_four_tabs_and_no_search_flag(
    client, authenticated_user, sarah_may_listen
):
    with authenticated_user:
        page = client.get("/sessions").data
        assert b'data-tab="listen"' not in page
        assert b'href="/listen"' not in page
        assert b"window.CEOL_LISTENS = false;" in page


def test_signed_out_there_is_no_listen_tab(client, db_setup):
    page = client.get("/sessions").data
    assert b'data-tab="listen"' not in page
    assert b"window.CEOL_LISTENS = false;" in page


def test_home_says_who_may_ask_what_tune_this_is(
    client, authenticated_user, sarah_may_listen
):
    with authenticated_user:
        assert (
            client.get("/api/home").get_json()["viewer"]["can_listen_on_server"]
            is False
        )


def test_home_says_a_listener_may(client, authenticated_user, sarah_may_listen):
    sarah_may_listen(True)
    with authenticated_user:
        assert (
            client.get("/api/home").get_json()["viewer"]["can_listen_on_server"] is True
        )
