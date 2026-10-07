"""Spec 057: which language a request is answered in, and the switch."""

import pytest

from database import get_db_connection
from places_helpers import logged_in

pytestmark = pytest.mark.integration


@pytest.fixture
def ian_language():
    """Put user 1's language back after a test changes it."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT language FROM user_account WHERE user_id = 1")
    original = cur.fetchone()[0]
    yield
    cur.execute("UPDATE user_account SET language = %s WHERE user_id = 1", (original,))
    conn.commit()
    conn.close()


def _lang_of(html):
    import re

    return re.search(r'<html lang="(\w+)"', html).group(1)


def test_a_visitor_gets_english(client):
    html = client.get("/sessions").get_data(as_text=True)
    assert _lang_of(html) == "en"
    assert ">Sessions</span>" in html


def test_the_switch_sets_the_cookie_and_goes_back(client):
    resp = client.get("/language/ga?next=/sessions")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/sessions"
    assert "ceol_lang=ga" in resp.headers["Set-Cookie"]
    html = client.get("/sessions").get_data(as_text=True)
    assert _lang_of(html) == "ga"
    assert "Seisiúin" in html


def test_the_switch_refuses_another_site(client):
    assert (
        client.get("/language/ga?next=https://evil.example/").headers["Location"] == "/"
    )
    assert client.get("/language/ga?next=//evil.example/").headers["Location"] == "/"


def test_an_unknown_language_is_404(client):
    assert client.get("/language/fr").status_code == 404


def test_the_profile_setting_wins_over_the_cookie(client, ian_language):
    client.set_cookie("ceol_lang", "en")
    with logged_in(client) as user:
        user.language = "ga"
        html = client.get("/sessions").get_data(as_text=True)
    assert _lang_of(html) == "ga"


def test_the_profile_api_reads_and_saves_it(client, ian_language):
    with logged_in(client):
        assert client.put("/api/me/profile", json={"language": "ga"}).status_code == 200
        body = client.get("/api/me/profile").get_json()
    assert body["account"]["language"] == "ga"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT language FROM user_account WHERE user_id = 1")
    assert cur.fetchone()[0] == "ga"
    conn.close()


def test_the_profile_api_refuses_other_languages(client, ian_language):
    with logged_in(client):
        assert client.put("/api/me/profile", json={"language": "fr"}).status_code == 400


def test_switching_while_signed_in_saves_the_profile(client, ian_language):
    with logged_in(client):
        client.get("/language/ga?next=/sessions")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT language FROM user_account WHERE user_id = 1")
    assert cur.fetchone()[0] == "ga"
    conn.close()


# Stage 4: the sentences the API sends back follow the request's language.
EXPIRED_EN = "Invalid or expired link. Please request a new one."
EXPIRED_GA = "Nasc neamhbhailí nó as feidhm. Iarr ceann nua."


def _exchange_message(client, headers):
    resp = client.post(
        "/api/auth/exchange", json={"token": "no-such-token"}, headers=headers
    )
    assert resp.status_code == 401
    return resp.get_json()["message"]


def test_api_messages_follow_the_cookie(client):
    client.set_cookie("ceol_lang", "ga")
    assert _exchange_message(client, {}) == EXPIRED_GA


def test_the_native_app_names_its_language(client):
    native = {"X-Ceol-Client": "ios/1.0.0 (build 1)", "Accept-Language": "ga"}
    assert _exchange_message(client, native) == EXPIRED_GA


def test_a_browsers_accept_language_is_not_followed(client):
    assert _exchange_message(client, {"Accept-Language": "ga"}) == EXPIRED_EN
