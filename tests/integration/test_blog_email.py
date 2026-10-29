"""A blog post emailed to the update subscribers (blog_send, migration 066): once, in
each subscriber's language, recorded like an app update. SendGrid is never hit."""

import json
from unittest.mock import patch

import pytest

import blog
from test_update_emails import login_as, make_user  # noqa: F401  (fixture)


def _set_language(db_conn, user_id, lang):
    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "UPDATE user_account SET language = %s WHERE user_id = %s", (lang, user_id)
    )
    db_conn.commit()


def _send(client, slug="welcome"):
    return client.post(
        f"/api/blog/{slug}/send", data="{}", content_type="application/json"
    )


def test_only_a_system_admin_can_send(client, make_user):
    user = make_user(opted_in=True)
    with login_as(client, user):
        assert _send(client).status_code == 403


def test_an_unknown_post_is_404(client, make_user):
    admin = make_user(is_admin=True)
    with login_as(client, admin), patch("api_routes.send_blog_post_email"):
        assert _send(client, "no-such-post").status_code == 404


def test_the_post_goes_to_each_subscriber_in_their_language(client, db_conn, make_user):
    admin = make_user(is_admin=True)
    english = make_user(opted_in=True)
    irish = make_user(opted_in=True)
    _set_language(db_conn, irish["user_id"], "ga")
    out = make_user(opted_in=False)

    with login_as(client, admin), patch(
        "api_routes.send_blog_post_email", return_value=True
    ) as mock_send:
        resp = _send(client)
    assert resp.status_code == 200, resp.data
    data = json.loads(resp.data)
    assert data["success"] is True
    assert data["failure_count"] == 0

    calls = {c.args[0]: c for c in mock_send.call_args_list}
    assert out["user_id"] not in calls
    en = calls[english["user_id"]]
    assert en.args[1] == english["email"]
    assert en.args[2] == "Welcome to the Ceol blog"
    assert "Howdy! Fáilte!" in en.args[3]
    assert en.args[5] == "en"
    ga = calls[irish["user_id"]]
    assert ga.args[2] == "Fáilte go blag Ceol"
    assert "Seo an chéad iontráil" in ga.args[3]
    assert ga.args[5] == "ga"

    db_conn.rollback()
    cur = db_conn.cursor()
    cur.execute(
        "SELECT subject, recipient_count, success_count FROM email_message WHERE blog_slug = 'welcome'"
    )
    row = cur.fetchone()
    assert row[0] == "Welcome to the Ceol blog"
    assert row[1] == row[2] == data["recipient_count"]

    # Once only.
    with login_as(client, admin), patch("api_routes.send_blog_post_email") as again:
        resp = _send(client)
    assert resp.status_code == 409
    again.assert_not_called()


def test_the_post_page_hides_the_send_from_a_reader(client, make_user):
    reader = make_user(opted_in=True)
    with login_as(client, reader):
        html = client.get("/blog/welcome").get_data(as_text=True)
    assert 'id="blog-send"' not in html


def test_the_post_page_offers_the_send_to_an_admin_until_it_has_gone(client, make_user):
    admin = make_user(is_admin=True)
    with login_as(client, admin):
        assert 'id="blog-send"' in client.get("/blog/welcome").get_data(as_text=True)
        with patch("api_routes.send_blog_post_email", return_value=True):
            assert _send(client).status_code == 200
        html = client.get("/blog/welcome").get_data(as_text=True)
    assert 'id="blog-send"' not in html
    assert "Emailed to" in html


def test_the_email_body_is_the_post_with_absolute_links(client):
    from app import app

    with app.test_request_context("/", base_url="https://ceol.app"):
        body_html, body_text = blog.email_body(
            blog.post("welcome"), "en", "https://ceol.app"
        )
    assert body_html.startswith("<h1>Welcome to the Ceol blog</h1>")
    assert 'href="https://ceol.app/register"' in body_html
    assert 'href="/' not in body_html
    assert "https://ceol.app/blog/welcome" in body_html
    assert "<" not in body_text
    assert "Howdy! Fáilte!" in body_text
    assert body_text.rstrip().endswith("https://ceol.app/blog/welcome")
