"""
The web can hear (spec 061 stage 2): /api/listen/connection gives a person who may
listen on the server where the listening service is and the token to sign in to it
with (the web session's own user_session row); /listen/test is the plain page that
uses it; and the listening service takes a browser's token in its start message,
since a browser can set no header on a WebSocket.
"""

import asyncio
import json

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
    cur.execute(
        "DELETE FROM user_session WHERE user_id = %s AND created_date > NOW() - INTERVAL '10 minutes'",
        (SARAH,),
    )
    conn.commit()
    conn.close()


def _session_row(token):
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM user_session WHERE session_id = %s", (token,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_a_listener_gets_the_service_and_a_token_that_is_their_own_session(
    client, authenticated_user, sarah_may_listen
):
    sarah_may_listen(True)
    with authenticated_user:
        resp = client.get("/api/listen/connection")
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body["url"].startswith("ws")
        assert body["sample_rate"] == 22050
        assert _session_row(body["token"]) == SARAH
        # asked again, the same token: one session row, not one per visit
        assert client.get("/api/listen/connection").get_json()["token"] == body["token"]
        with client.session_transaction() as sess:
            assert sess["db_session_id"] == body["token"]


def test_without_the_right_there_is_no_token(
    client, authenticated_user, sarah_may_listen
):
    with authenticated_user:
        resp = client.get("/api/listen/connection")
        assert resp.status_code == 403
        assert "token" not in resp.get_json()


def test_signed_out_there_is_no_token(client, db_setup):
    assert client.get("/api/listen/connection").status_code == 401


def test_the_test_page_sends_others_home(client, authenticated_user, sarah_may_listen):
    with authenticated_user:
        resp = client.get("/listen/test")
        assert resp.status_code == 302


def test_the_test_page_is_there_for_a_listener(
    client, authenticated_user, sarah_may_listen
):
    sarah_may_listen(True)
    with authenticated_user:
        page = client.get("/listen/test")
        assert page.status_code == 200
        assert b'id="listen-test-root"' in page.data
        assert b"listentest/page.js" in page.data


# --------------------------------------------------------------------------- #
# The listening service: a browser's token arrives in its start message
# --------------------------------------------------------------------------- #


class FakeSocket:
    """Enough of Starlette's WebSocket for listen/service.listen()."""

    def __init__(self, messages, token=None, wait=False):
        headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
        self.scope = {"headers": headers}
        self.query_params = {}
        self.inbox = list(messages)
        self.wait = wait  # after the messages, wait rather than disconnect
        self.sent = []
        self.accepted = False
        self.closed = None

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000):
        self.closed = code

    async def receive(self):
        if self.inbox:
            return {"type": "websocket.receive", "text": json.dumps(self.inbox.pop(0))}
        if self.wait:
            await asyncio.sleep(3600)
        return {"type": "websocket.disconnect"}

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class StubStream:
    def __init__(self, sid, mode="audio", known=None):
        self.id, self.mode = sid, mode
        self.have = self.heard_t = self.known_tunes = 0
        self.socket = None
        self.last_seen = 0


@pytest.fixture
def service(monkeypatch):
    from listen import service

    async def no_steps(stream):
        return None

    monkeypatch.setattr(service, "TOKEN", "service-secret")
    monkeypatch.setitem(service.state, "models", object())
    monkeypatch.setattr(service, "Stream", StubStream)
    monkeypatch.setattr(service, "_step_loop", no_steps)
    monkeypatch.setattr(service, "_app_token_allowed", lambda token: token == "good")
    service.streams.clear()
    yield service
    service.streams.clear()


START = {"type": "start", "stream_id": "s-061", "sample_rate": 22050}


def test_the_service_admits_a_browser_whose_start_carries_a_good_token(service):
    ws = FakeSocket([{**START, "token": "good"}])
    asyncio.run(service.listen(ws))
    assert ws.accepted
    assert ws.sent[0]["type"] == "ready" and ws.sent[0]["stream_id"] == "s-061"
    assert ws.closed is None


def test_the_service_closes_a_browser_whose_start_has_a_bad_token(service):
    ws = FakeSocket([{**START, "token": "bad"}])
    asyncio.run(service.listen(ws))
    assert ws.sent == [{"type": "error", "error": "not allowed"}]
    assert ws.closed == 4401
    assert "s-061" not in service.streams


def test_the_service_closes_a_browser_whose_start_has_no_token(service):
    ws = FakeSocket([START])
    asyncio.run(service.listen(ws))
    assert ws.closed == 4401
    assert "s-061" not in service.streams


def test_a_socket_with_no_token_that_never_starts_is_closed(service, monkeypatch):
    monkeypatch.setattr(service, "START_S", 0.05)
    ws = FakeSocket([], wait=True)
    asyncio.run(service.listen(ws))
    assert ws.closed == 4401


def test_a_bad_header_token_is_still_refused_before_accepting(service):
    ws = FakeSocket([START], token="bad")
    asyncio.run(service.listen(ws))
    assert ws.closed == 4401 and not ws.accepted


def test_the_header_token_still_works_for_the_app(service):
    ws = FakeSocket([START], token="good")
    asyncio.run(service.listen(ws))
    assert ws.sent[0]["type"] == "ready"


def test_the_service_token_in_the_start_message_works_too(service):
    ws = FakeSocket([{**START, "token": "service-secret"}])
    asyncio.run(service.listen(ws))
    assert ws.sent[0]["type"] == "ready"
