"""POST /api/report: "Report" in every page's menu (App Store guideline 1.2).

A report is an email to support, Reply-To whoever sent it. Signed in, it names the
account; signed out, it carries the address they left, if any. Nothing is stored.
"""

from unittest.mock import patch

IOS = {"X-Ceol-Client": "ios/1.0.0 (build 1)"}


def _sign_in(client):
    r = client.post(
        "/api/auth/login-password",
        json={"email": "ian@ceol.io", "password": "password123"},
        headers=IOS,
    )
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}", **IOS}


@patch("email_utils.send_email_via_sendgrid", return_value=True)
def test_signed_in_report_names_the_account_and_replies_to_it(send, client):
    headers = _sign_in(client)
    r = client.post(
        "/api/report",
        json={
            "reason": "offensive",
            "message": "Rude session description",
            "page_url": "https://ceol.app/sessions/austin/mueller",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    assert r.get_json() == {"success": True}
    to, subject, body = send.call_args.args
    assert to == "support@ceol.app"
    assert "Offensive" in subject and "/sessions/austin/mueller" in subject
    assert "Rude session description" in body
    assert "ian@ceol.io" in body
    assert send.call_args.kwargs["reply_to"] == "ian@ceol.io"


@patch("email_utils.send_email_via_sendgrid", return_value=True)
def test_signed_out_report_replies_to_the_address_left(send, client):
    r = client.post(
        "/api/report",
        json={"reason": "broken", "contact_email": "visitor@example.com"},
    )
    assert r.status_code == 200, r.get_json()
    assert "Not signed in (visitor@example.com)" in send.call_args.args[2]
    assert send.call_args.kwargs["reply_to"] == "visitor@example.com"


@patch("email_utils.send_email_via_sendgrid", return_value=True)
def test_refuses_a_bad_report_without_sending(send, client):
    cases = [
        ({"reason": "spite"}, "invalid_reason"),
        ({"reason": "other"}, "message_required"),
        ({"reason": "wrong", "contact_email": "not an address"}, "invalid_email"),
        ({"reason": "wrong", "message": "x" * 4001}, None),
    ]
    for body, code in cases:
        r = client.post("/api/report", json=body)
        assert r.status_code == 400, body
        if code:
            assert r.get_json()["code"] == code
    send.assert_not_called()


@patch("email_utils.send_email_via_sendgrid", return_value=False)
def test_a_failed_send_says_so(send, client):
    r = client.post("/api/report", json={"reason": "broken"})
    assert r.status_code == 503
    assert r.get_json()["code"] == "send_failed"
    assert "support@ceol.app" in r.get_json()["message"]


def test_privacy_and_support_pages_in_both_languages(client):
    for path, english, irish in [
        ("/privacy", "Privacy Policy", "Polasaí príobháideachais"),
        ("/support", "Contact &amp; Support", "Teagmháil agus tacaíocht"),
    ]:
        r = client.get(path)
        assert r.status_code == 200
        page = r.get_data(as_text=True)
        assert english in page and "support@ceol.app" in page
        client.get("/language/ga")
        assert irish in client.get(path).get_data(as_text=True)
        client.get("/language/en")


def test_report_page_links_back_only_to_a_real_address(client):
    good = client.get("/report?page=https://ceol.app/sessions/austin").get_data(
        as_text=True
    )
    assert 'href="https://ceol.app/sessions/austin"' in good
    bad = client.get("/report?page=javascript:alert(1)").get_data(as_text=True)
    assert (
        'href="javascript:' not in bad
    )  # (the language switch's next= still names it)
    assert "About this page" not in bad
