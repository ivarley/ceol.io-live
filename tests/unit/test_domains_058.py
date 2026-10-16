"""Spec 058: the move to ceol.app. What follows the request's host (domains.py):
the login cookies' Domain, the streaming sidecar's address, and, once the move is
switched on, what the old host answers."""

import pytest
from flask import make_response, session

import domains
from app import app, login_manager

HTML = {"Accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def two_domains(monkeypatch):
    monkeypatch.delenv("SESSION_COOKIE_DOMAIN", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_DOMAINS", ".ceol.io, ceol.app")
    monkeypatch.setenv("STREAMING_BASE_URL", "https://streaming.ceol.io")


@pytest.fixture
def moving(monkeypatch, two_domains):
    monkeypatch.setenv("MOVE_TO_HOST", "ceol.app")
    monkeypatch.setenv("MOVE_FROM_HOSTS", "ceol.io,www.ceol.io")
    monkeypatch.delenv("MOVE_SWITCHED", raising=False)


@pytest.fixture
def switched(monkeypatch, moving):
    monkeypatch.setenv("MOVE_SWITCHED", "true")


def _set_cookies(resp):
    return resp.headers.getlist("Set-Cookie")


@pytest.mark.unit
class TestCookieDomain:
    @pytest.mark.parametrize(
        "host,expected",
        [
            ("ceol.io", ".ceol.io"),
            ("www.ceol.io", ".ceol.io"),
            ("ceol.app", ".ceol.app"),
            ("CEOL.APP:443", ".ceol.app"),
            ("streaming.ceol.app", ".ceol.app"),
            ("localhost:3232", None),
            ("evil.example", None),
            ("notceol.app", None),
        ],
    )
    def test_follows_the_host(self, two_domains, host, expected):
        assert domains.cookie_domain(host) == expected

    def test_the_old_single_setting_still_works(self, monkeypatch):
        monkeypatch.delenv("SESSION_COOKIE_DOMAINS", raising=False)
        monkeypatch.setenv("SESSION_COOKIE_DOMAIN", ".ceol.io")
        assert domains.cookie_domain("ceol.io") == ".ceol.io"
        assert domains.cookie_domain("ceol.app") is None

    def test_nothing_set_means_host_only(self, monkeypatch):
        monkeypatch.delenv("SESSION_COOKIE_DOMAINS", raising=False)
        monkeypatch.delenv("SESSION_COOKIE_DOMAIN", raising=False)
        assert domains.cookie_domain("ceol.io") is None

    @pytest.mark.parametrize(
        "base_url,expected",
        [
            ("https://ceol.app", "Domain=ceol.app"),
            ("https://ceol.io", "Domain=ceol.io"),
            ("http://localhost:3232", None),
        ],
    )
    def test_the_session_cookie(self, client, two_domains, base_url, expected):
        # ?referrer= writes to the session; /sw.js needs no database.
        resp = client.get("/sw.js?referrer=7", base_url=base_url)
        cookie = next(c for c in _set_cookies(resp) if c.startswith("session="))
        if expected:
            assert expected in cookie
        else:
            assert "Domain=" not in cookie

    @pytest.mark.parametrize(
        "host,expected",
        [("ceol.app", "Domain=ceol.app"), ("ceol.io", "Domain=ceol.io")],
    )
    def test_the_remember_cookie(self, two_domains, host, expected):
        with app.test_request_context("/", base_url=f"https://{host}"):
            session["_user_id"] = "1"
            resp = make_response("")
            login_manager._set_cookie(resp)
            login_manager._clear_cookie(resp)
        set_cookie, cleared = _set_cookies(resp)
        assert set_cookie.startswith("remember_token=") and expected in set_cookie
        assert cleared.startswith("remember_token=;") and expected in cleared


@pytest.mark.unit
class TestStreamingAddress:
    @pytest.mark.parametrize(
        "host,expected",
        [
            ("ceol.app", "https://streaming.ceol.app"),
            ("ceol.io", "https://streaming.ceol.io"),
            ("localhost:3232", "https://streaming.ceol.io"),
        ],
    )
    def test_follows_the_host(self, two_domains, host, expected):
        assert domains.streaming_base_url(host) == expected

    def test_local_dev_keeps_its_setting(self, monkeypatch):
        monkeypatch.delenv("SESSION_COOKIE_DOMAINS", raising=False)
        monkeypatch.delenv("SESSION_COOKIE_DOMAIN", raising=False)
        monkeypatch.setenv("STREAMING_BASE_URL", "http://localhost:8080")
        assert domains.streaming_base_url("localhost:3232") == "http://localhost:8080"

    def test_a_port_is_kept(self, two_domains, monkeypatch):
        monkeypatch.setenv("STREAMING_BASE_URL", "https://streaming.ceol.io:8443")
        assert (
            domains.streaming_base_url("ceol.app") == "https://streaming.ceol.app:8443"
        )

    def test_app_config_reports_it(self, client, two_domains):
        body = client.get("/api/app-config", base_url="https://ceol.app").get_json()
        assert body["streaming_base_url"] == "https://streaming.ceol.app"


@pytest.mark.unit
class TestBeforeTheSwitch:
    def test_the_new_host_is_not_indexed(self, client, moving):
        resp = client.get("/sw.js", base_url="https://ceol.app")
        assert resp.headers["X-Robots-Tag"] == "noindex"

    def test_the_old_host_is_untouched(self, client, moving):
        resp = client.get("/sw.js", base_url="https://ceol.io")
        assert "X-Robots-Tag" not in resp.headers
        assert b"Main-app service worker" in resp.data


@pytest.mark.unit
class TestAfterTheSwitch:
    def test_a_page_gets_the_moved_page(self, client, switched):
        resp = client.get(
            "/sessions/austin/mueller?tab=logs",
            base_url="https://ceol.io",
            headers=HTML,
        )
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "no-store"
        text = resp.get_data(as_text=True)
        assert "Ceol has moved" in text
        assert 'href="https://ceol.app/sessions/austin/mueller?tab=logs"' in text
        assert "ceol.app/sessions/austin/mueller<" in text

    def test_the_moved_page_in_irish(self, client, switched):
        client.set_cookie("ceol_lang", "ga", domain="ceol.io")
        resp = client.get("/", base_url="https://ceol.io", headers=HTML)
        text = resp.get_data(as_text=True)
        assert 'lang="ga"' in text and "Ceol has moved" not in text

    @pytest.mark.parametrize("path", ["/sw.js", "/live/sw.js"])
    def test_the_workers_retire(self, client, switched, path):
        resp = client.get(path, base_url="https://ceol.io")
        assert resp.status_code == 200
        assert b"registration.unregister()" in resp.data
        assert "no-store" in resp.headers["Cache-Control"]

    @pytest.mark.parametrize(
        "method,path,headers",
        [
            ("POST", "/api/live/ops", {}),
            ("GET", "/api/app-config", HTML),
            ("GET", "/static/css/theme.css", HTML),
            ("GET", "/sessions/austin/mueller", {"Accept": "application/json"}),
        ],
    )
    def test_everything_else_is_redirected(
        self, client, switched, method, path, headers
    ):
        resp = client.open(
            path + "?a=1",
            method=method,
            base_url="https://www.ceol.io",
            headers=headers,
        )
        assert resp.status_code == 308
        assert resp.headers["Location"] == f"https://ceol.app{path}?a=1"

    def test_the_new_host_serves_the_site_and_is_indexed(self, client, switched):
        resp = client.get("/sw.js", base_url="https://ceol.app")
        assert b"Main-app service worker" in resp.data
        assert "X-Robots-Tag" not in resp.headers

    def test_other_hosts_are_untouched(self, client, switched):
        resp = client.get("/sw.js", base_url="http://localhost:3232")
        assert b"Main-app service worker" in resp.data
