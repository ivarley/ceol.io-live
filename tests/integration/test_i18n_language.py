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


def test_the_added_person_notice_carries_each_admins_language(client):
    """Stage 5: add-person-to-session emails each session admin in their language."""
    from unittest.mock import patch

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT sp.session_id FROM session_person sp
           JOIN user_account ua ON ua.person_id = sp.person_id
           WHERE sp.is_admin LIMIT 1"""
    )
    session_id = cur.fetchone()[0]
    cur.execute(
        """SELECT person_id FROM person WHERE person_id NOT IN
           (SELECT person_id FROM session_person WHERE session_id = %s) LIMIT 1""",
        (session_id,),
    )
    person_id = cur.fetchone()[0]
    try:
        with logged_in(client), patch(
            "api_routes.send_person_added_email", return_value=True
        ) as send:
            resp = client.post(
                "/api/add-person-to-session",
                json={"person_id": person_id, "session_id": session_id},
            )
        assert resp.status_code == 200, resp.get_json()
        assert send.called
        admin = send.call_args[0][0]
        assert admin["language"] in ("en", "ga") and admin["email"]
    finally:
        cur.execute(
            "DELETE FROM session_person WHERE person_id = %s AND session_id = %s",
            (person_id, session_id),
        )
        conn.commit()
        conn.close()


HELP_URLS = [
    "/help",
    "/help/sessions",
    "/help/offline",
    "/help/my-tunes",
    "/help/release-notes",
    "/help/release-notes/2026-07",
]


@pytest.mark.parametrize("url", HELP_URLS)
def test_help_pages_come_in_both_languages(client, url):
    english = client.get(url, follow_redirects=True)
    assert english.status_code == 200
    client.set_cookie("ceol_lang", "ga")
    irish = client.get(url, follow_redirects=True)
    assert irish.status_code == 200
    assert _lang_of(irish.get_data(as_text=True)) == "ga"
    assert irish.data != english.data


def test_the_glossary_review_page_needs_no_sign_in_and_isnt_indexed(client):
    resp = client.get("/irish-glossary-review")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="robots" content="noindex' in html
    assert "<td>fonn (pl. foinn)</td>" in html
    assert "This file is also the page" not in html and "spec 057" not in html
