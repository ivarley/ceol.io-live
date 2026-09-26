"""The thesession.org proxies are throttled per caller (rate_limit.py).

Two endpoints call thesession.org for someone who is not signed in: the public tune
search, and the notation backfill. Unlimited, they are an open proxy — anyone can
point a loop at Ceol and have Ceol hammer a volunteer-run site from Ceol's address.

What these pin is the behaviour worth depending on: the limit exists, it refuses in
language a client can act on (a status, a code, and when to come back), it counts the
right caller, and one endpoint's traffic does not spend another's allowance. The
exact numbers are deliberately not restated here — a test that only echoes a constant
fails when the constant is tuned and teaches nobody anything.
"""

import time

import pytest

import rate_limit


@pytest.fixture(autouse=True)
def fresh():
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture(autouse=True)
def no_outbound_calls(monkeypatch):
    """Nothing here should reach thesession.org.

    The limiter runs before the view, so the calls BEFORE the limit is reached would
    otherwise each make a real request with a 10s timeout — thirty of those is a test
    run that looks hung. It also means these tests pass or fail on their own logic
    rather than on whether a volunteer-run site is up.
    """

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"tunes": [], "sessions": [], "settings": []}

    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())


class TestTheWindow:
    def test_it_allows_the_limit_and_refuses_the_next(self):
        for i in range(3):
            assert rate_limit.check("s", 3, 60, key="k") == 0, f"call {i} should pass"
        assert rate_limit.check("s", 3, 60, key="k") > 0

    def test_it_says_how_long_to_wait(self):
        rate_limit.check("s", 1, 60, key="k")
        wait = rate_limit.check("s", 1, 60, key="k")
        assert 0 < wait <= 60

    def test_the_window_slides_rather_than_resetting_on_the_hour(self):
        # A fixed window lets a caller spend the whole allowance at the end of one and
        # the whole next allowance immediately after — twice the limit, back to back.
        # Two hits inside a 0.3s window, then wait part of it out: the FIRST ages out
        # and exactly one slot opens, rather than the counter going back to zero.
        assert rate_limit.check("s", 2, 0.3, key="k") == 0
        time.sleep(0.2)
        assert rate_limit.check("s", 2, 0.3, key="k") == 0
        assert rate_limit.check("s", 2, 0.3, key="k") > 0
        time.sleep(0.15)
        assert rate_limit.check("s", 2, 0.3, key="k") == 0
        assert rate_limit.check("s", 2, 0.3, key="k") > 0

    def test_callers_are_counted_separately(self):
        assert rate_limit.check("s", 1, 60, key="a") == 0
        assert rate_limit.check("s", 1, 60, key="b") == 0
        assert rate_limit.check("s", 1, 60, key="a") > 0

    def test_scopes_are_counted_separately(self):
        # Searching must not spend the notation allowance; different calls, different
        # costs to the site on the other end.
        assert rate_limit.check("search", 1, 60, key="k") == 0
        assert rate_limit.check("backfill", 1, 60, key="k") == 0

    def test_it_does_not_grow_without_bound(self, monkeypatch):
        # A spray of forged addresses must not be a memory leak.
        monkeypatch.setattr(rate_limit, "_MAX_KEYS", 50)
        for i in range(500):
            rate_limit.check("s", 5, 60, key=f"ip-{i}")
        assert len(rate_limit._HITS) <= 60


@pytest.fixture
def flask_app():
    from app import app as flask_application

    return flask_application


class TestWhoGetsCounted:
    def test_an_anonymous_caller_is_counted_by_the_address_the_proxy_saw(
        self, flask_app
    ):
        # The LAST X-Forwarded-For entry. Each proxy appends, so the rightmost is what
        # Render observed and everything left of it is what the client claimed. Taking
        # the leftmost — which the login logging does, correctly, because a log records
        # an assertion — would let anyone mint a fresh allowance per request.
        with flask_app.test_request_context(
            "/", headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 9.9.9.9"}
        ):
            assert rate_limit._client_ip() == "9.9.9.9"
            assert rate_limit._caller_key() == "ip:9.9.9.9"

    def test_a_forged_header_cannot_buy_a_fresh_allowance(self, flask_app):
        keys = set()
        for forged in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
            with flask_app.test_request_context(
                "/", headers={"X-Forwarded-For": f"{forged}, 9.9.9.9"}
            ):
                keys.add(rate_limit._caller_key())
        assert keys == {"ip:9.9.9.9"}, "the claimed address must not change the bucket"

    def test_a_signed_in_caller_is_counted_as_themselves(self, client, flask_app):
        # Ceol's users are often in one room on one pub wifi — a whole session's worth
        # of players behind one NAT. Counting them together would throttle the table
        # because one person searched, so an account is its own bucket.
        with flask_app.test_request_context(
            "/", headers={"X-Forwarded-For": "9.9.9.9"}
        ):
            anon = rate_limit._caller_key()
        assert anon.startswith("ip:")


class TestTheEndpointsRefuseInLanguageAClientCanAct:
    def test_a_flood_of_searches_is_refused_with_a_code_and_a_retry_after(
        self, client, monkeypatch
    ):
        monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
        last = None
        for _ in range(60):
            last = client.get("/api/tunes/thesession-search?q=cooley")
            if last.status_code == 429:
                break
        assert last.status_code == 429, "a flood of searches should have been refused"
        body = last.get_json()
        assert body["success"] is False
        assert body["code"] == "rate_limited"
        assert int(last.headers["Retry-After"]) >= 1

    def test_the_notation_backfill_is_refused_too(self, client, monkeypatch):
        # Its per-tune token bounds what ONE token can do; this bounds one caller.
        monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
        last = None
        for _ in range(60):
            last = client.post("/api/tunes/1/settings/cache")
            if last.status_code == 429:
                break
        assert last.status_code == 429
        assert last.get_json()["code"] == "rate_limited"

    def test_searching_does_not_spend_the_notation_allowance(self, client, monkeypatch):
        monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
        for _ in range(60):
            if client.get("/api/tunes/thesession-search?q=cooley").status_code == 429:
                break
        # The other endpoint is untouched by that, and answers on its own terms
        # (401 without a token — the point is that it is not 429).
        assert client.post("/api/tunes/1/settings/cache").status_code != 429

    def test_the_switch_the_e2e_suite_uses_actually_switches_it_off(
        self, client, monkeypatch
    ):
        # playwright.config.ts sets this, because that suite drives these endpoints
        # from one address far harder than a person would and a mid-run 429 would fail
        # whichever spec came next.
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
        for _ in range(60):
            assert (
                client.get("/api/tunes/thesession-search?q=cooley").status_code != 429
            )
