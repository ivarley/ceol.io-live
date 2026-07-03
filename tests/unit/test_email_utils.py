"""
Unit tests for email_utils (spec 027: app update emails).

Covers the per-call from-address / unsubscribe-URL parameters on
send_email_via_sendgrid, the stateless signed unsubscribe tokens, and the
Markdown-based send_update_email sender.
"""

import pytest

from email_utils import (
    send_email_via_sendgrid,
    generate_unsubscribe_token,
    verify_unsubscribe_token,
    send_update_email,
)


def sent_payload(mock_sendgrid):
    """The dict payload of the (single) Mail object passed to SendGrid."""
    mock_client = mock_sendgrid.return_value
    assert mock_client.send.call_count == 1
    return mock_client.send.call_args[0][0].get()


@pytest.mark.unit
class TestSendEmailViaSendgrid:
    def test_default_sender_and_mailto_unsubscribe_unchanged(self, mock_sendgrid, app_context):
        result = send_email_via_sendgrid("to@example.com", "Subj", "body")
        assert result is True
        payload = sent_payload(mock_sendgrid)
        # conftest sets MAIL_DEFAULT_SENDER=test@ceol.io
        assert payload["from"]["email"] == "test@ceol.io"
        assert payload["headers"]["List-Unsubscribe"].startswith("<mailto:")
        assert payload["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_from_email_override(self, mock_sendgrid, app_context):
        send_email_via_sendgrid("to@example.com", "Subj", "body", from_email="ceol@ceol.io")
        assert sent_payload(mock_sendgrid)["from"]["email"] == "ceol@ceol.io"

    def test_unsubscribe_url_replaces_mailto_header(self, mock_sendgrid, app_context):
        url = "https://ceol.io/unsubscribe/abc123"
        send_email_via_sendgrid("to@example.com", "Subj", "body", unsubscribe_url=url)
        payload = sent_payload(mock_sendgrid)
        assert payload["headers"]["List-Unsubscribe"] == f"<{url}>"
        assert payload["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_send_failure_returns_false(self, mock_sendgrid, app_context):
        mock_sendgrid.return_value.send.side_effect = Exception("boom")
        assert send_email_via_sendgrid("to@example.com", "Subj", "body") is False


@pytest.mark.unit
class TestUnsubscribeTokens:
    def test_round_trip(self, app_context):
        token = generate_unsubscribe_token(42)
        assert verify_unsubscribe_token(token) == 42

    def test_tampered_token_rejected(self, app_context):
        token = generate_unsubscribe_token(42)
        assert verify_unsubscribe_token(token[:-2] + "xx") is None

    def test_garbage_token_rejected(self, app_context):
        assert verify_unsubscribe_token("not-a-token") is None
        assert verify_unsubscribe_token("") is None


@pytest.mark.unit
class TestSendUpdateEmail:
    BODY_MD = "# Big News\n\nWe added *tune search*."

    def _send(self, app_context, **kwargs):
        # Request context so url_for(_external=True) can build the unsubscribe link
        with app_context.test_request_context():
            return send_update_email(
                kwargs.pop("user_id", 42),
                kwargs.pop("to_email", "user@example.com"),
                kwargs.pop("subject", "App updates"),
                kwargs.pop("body_markdown", self.BODY_MD),
            )

    def test_sends_from_updates_sender_default(self, mock_sendgrid, app_context, monkeypatch):
        monkeypatch.delenv("MAIL_UPDATES_SENDER", raising=False)
        assert self._send(app_context) is True
        assert sent_payload(mock_sendgrid)["from"]["email"] == "ceol@ceol.io"

    def test_updates_sender_env_override(self, mock_sendgrid, app_context, monkeypatch):
        monkeypatch.setenv("MAIL_UPDATES_SENDER", "news@ceol.io")
        self._send(app_context)
        assert sent_payload(mock_sendgrid)["from"]["email"] == "news@ceol.io"

    def test_markdown_rendered_in_html_part(self, mock_sendgrid, app_context):
        self._send(app_context)
        payload = sent_payload(mock_sendgrid)
        html = next(c["value"] for c in payload["content"] if c["type"] == "text/html")
        assert "<h1>Big News</h1>" in html
        assert "<em>tune search</em>" in html

    def test_plain_text_part_is_raw_markdown(self, mock_sendgrid, app_context):
        self._send(app_context)
        payload = sent_payload(mock_sendgrid)
        text = next(c["value"] for c in payload["content"] if c["type"] == "text/plain")
        assert "# Big News" in text
        assert "*tune search*" in text
        assert "<h1>" not in text

    def test_footer_and_unsubscribe_link_in_both_parts(self, mock_sendgrid, app_context):
        self._send(app_context, user_id=77)
        payload = sent_payload(mock_sendgrid)
        text = next(c["value"] for c in payload["content"] if c["type"] == "text/plain")
        html = next(c["value"] for c in payload["content"] if c["type"] == "text/html")
        for part in (text, html):
            assert "because you opted in" in part
            assert "/unsubscribe/" in part
        # The link token must resolve back to this recipient
        token = text.split("/unsubscribe/")[1].split()[0].strip()
        with app_context.app_context():
            assert verify_unsubscribe_token(token) == 77

    def test_unsubscribe_url_in_list_unsubscribe_header(self, mock_sendgrid, app_context):
        self._send(app_context, user_id=77)
        payload = sent_payload(mock_sendgrid)
        header = payload["headers"]["List-Unsubscribe"]
        assert header.startswith("<") and header.endswith(">")
        assert "/unsubscribe/" in header
