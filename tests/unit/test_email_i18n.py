"""Spec 057: emails go out in the recipient's language."""

from unittest.mock import patch

import pytest

from app import app
from auth import User
from email_utils import send_login_link_email, send_person_added_email


def _user(language):
    return User(
        user_id=1,
        person_id=1,
        username="u",
        email="u@example.com",
        first_name="U",
        last_name="V",
        language=language,
    )


def _sent_login_email(language):
    with app.test_request_context("/"), patch(
        "email_utils.url_for", return_value="https://ceol.io/auth/login/t"
    ), patch("email_utils.send_email_via_sendgrid", return_value=True) as send:
        send_login_link_email(_user(language), "t")
    return send.call_args[0]


def test_an_english_account_gets_english():
    to, subject, text, html = _sent_login_email("en")
    assert subject == "Your Login Link - Irish Music Sessions"
    assert "This link will expire in 15 minutes." in text
    assert ">Log In</a>" in html


def test_an_irish_account_gets_irish_whatever_the_request():
    to, subject, text, html = _sent_login_email("ga")
    assert subject != "Your Login Link - Irish Music Sessions"
    assert "15" in text and "expire" not in text
    assert (
        "https://ceol.io/auth/login/t" in text
        and "https://ceol.io/auth/login/t" in html
    )


@pytest.mark.parametrize("relationship", ["member", "visitor"])
def test_the_admin_notice_is_in_the_admins_language(relationship):
    with app.test_request_context("/"), patch(
        "email_utils.send_email_via_sendgrid", return_value=True
    ) as send:
        for lang in ("en", "ga"):
            send_person_added_email(
                {"name": "A B", "email": "a@example.com", "language": lang},
                {"name": "P Q", "email": None, "relationship": relationship},
                {"name": "Mueller", "location": "", "path": "austin/mueller"},
            )
    (en_args, _), (ga_args, _) = send.call_args_list
    assert en_args[1] == "New person added to session: Mueller"
    assert f"in Unknown as a {relationship}." in en_args[2]
    assert ga_args[1] != en_args[1] and "Mueller" in ga_args[1]
    assert "austin/mueller" in ga_args[2]
