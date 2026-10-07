# i18n-converted
import os
import logging
import markdown
from flask import url_for, current_app
from flask_babel import force_locale, gettext as _
from itsdangerous import URLSafeSerializer, BadSignature
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Header

# Configure logger for email operations
logger = logging.getLogger(__name__)


def send_email_via_sendgrid(
    to_email, subject, body_text, body_html=None, from_email=None, unsubscribe_url=None
):
    """Send email using SendGrid API.

    from_email: overrides MAIL_DEFAULT_SENDER for this message (must be a
    SendGrid-verified sender). unsubscribe_url: personalized one-click
    unsubscribe target; replaces the default mailto List-Unsubscribe header
    (RFC 8058 — mail clients render a native Unsubscribe button and POST to it).
    """
    try:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            logger.error("SendGrid API key not configured")
            return False

        if from_email is None:
            from_email = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@ceol.io")
        unsubscribe_email = os.environ.get("MAIL_UNSUBSCRIBE", "unsubscribe@ceol.io")

        logger.info(
            f"Sending email via SendGrid - To: {to_email}, From: {from_email}, Subject: {subject}"
        )

        sg = SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body_text,
            html_content=body_html,
        )

        # List-Unsubscribe headers for better deliverability
        if unsubscribe_url:
            message.header = Header("List-Unsubscribe", f"<{unsubscribe_url}>")
        else:
            message.header = Header("List-Unsubscribe", f"<mailto:{unsubscribe_email}>")
        message.add_header(
            Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
        )

        response = sg.send(message)

        # Check response status
        if response.status_code in [200, 201, 202]:
            logger.info(
                f"Email sent successfully - To: {to_email}, Subject: {subject}, Status: {response.status_code}"
            )
            return True
        else:
            logger.error(
                f"SendGrid error - To: {to_email}, Subject: {subject}, Status: {response.status_code}, Response: {response.body}"
            )
            return False

    except Exception as e:
        logger.error(
            f"SendGrid email error - To: {to_email}, Subject: {subject}, Error: {str(e)}"
        )
        # Log more specific error types
        if "unauthorized" in str(e).lower():
            logger.error("SendGrid authentication failed - check SENDGRID_API_KEY")
        elif "forbidden" in str(e).lower():
            logger.error(
                "SendGrid access forbidden - check that sender email is verified in SendGrid"
            )
        return False


def _recipient_language(user):
    """The language an email to this account goes out in (spec 057): theirs."""
    from i18n import user_language

    try:
        return user_language(user)
    except Exception:
        return "en"


def _language_of_user_id(user_id):
    from i18n import LANGUAGES
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT language FROM user_account WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] in LANGUAGES else "en"


def _button(url, label):
    return (
        f'<p><a href="{url}" style="background-color: #007bff; color: white; '
        f'padding: 10px 20px; text-decoration: none; border-radius: 5px;">{label}</a></p>'
    )


def send_password_reset_email(user, token):
    logger.info(
        f"Initiating password reset email - User: {user.username}, Email: {user.email}"
    )

    reset_url = url_for("reset_password", token=token, _external=True)

    with force_locale(_recipient_language(user)):
        subject = _("Password Reset Request - Irish Music Sessions")
        ignore = _(
            "If you did not make this request, please ignore this email and no changes will be made."
        )
        expires = _("This link will expire in 1 hour.")
        body_text = f"""{_("To reset your password, visit the following link:")}
{reset_url}

{ignore}

{expires}
"""

        body_html = f"""
    <h2>{_("Password Reset Request")}</h2>
    <p>{_("To reset your password, click the following link:")}</p>
    <p><a href="{reset_url}">{_("Reset Your Password")}</a></p>
    <p>{ignore}</p>
    <p><strong>{expires}</strong></p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Password reset email sent successfully - User: {user.username}")
    else:
        logger.error(
            f"Password reset email failed - User: {user.username}, Email: {user.email}"
        )

    return result


def send_verification_email(user, token):
    logger.info(
        f"Initiating verification email - User: {user.username}, Email: {user.email}"
    )

    verification_url = url_for("verify_email", token=token, _external=True)

    with force_locale(_recipient_language(user)):
        subject = _("Verify Your Email Address - Irish Music Sessions")
        welcome = _("Welcome to Irish Music Sessions!")
        ignore = _("If you did not create this account, please ignore this email.")
        expires = _("This link will expire in 24 hours.")
        body_text = f"""{welcome}

{_("Please click the following link to verify your email address and activate your account:")}
{verification_url}

{ignore}

{expires}
"""

        body_html = f"""
    <h2>{welcome}</h2>
    <p>{_("Thank you for registering with us. Please verify your email address to activate your account.")}</p>
    {_button(verification_url, _("Verify Email Address"))}
    <p>{_("If the button doesn't work, copy and paste this link into your browser:")}</p>
    <p>{verification_url}</p>
    <p>{ignore}</p>
    <p><strong>{expires}</strong></p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Verification email sent successfully - User: {user.username}")
    else:
        logger.error(
            f"Verification email failed - User: {user.username}, Email: {user.email}"
        )

    return result


def send_registration_email(email, token):
    """The link that creates an account for an address typed on the login page
    (migration 056). No account exists yet, so it goes to a bare address, and the
    wording has to make sense to someone who never asked for it. No account means no
    language setting: it goes out in the language of the request that asked for it."""
    logger.info(f"Initiating registration email - Email: {email}")

    verification_url = url_for("verify_email", token=token, _external=True)

    subject = _("Create your account - Irish Music Sessions")
    ignore = _(
        "If this wasn't you, ignore this email. No account is created unless the link is clicked."
    )
    expires = _("This link will expire in 24 hours.")
    body_text = f"""{_("Someone, hopefully you, asked to create an Irish Music Sessions account with this email address.")}

{_("Click this link to create your account and log in:")}
{verification_url}

{ignore}

{expires}
"""

    body_html = f"""
    <h2>{_("Create your Irish Music Sessions account")}</h2>
    <p>{_("Someone, hopefully you, asked to create an account with this email address.")}</p>
    {_button(verification_url, _("Create my account"))}
    <p>{_("If the button doesn't work, copy and paste this link into your browser:")}</p>
    <p>{verification_url}</p>
    <p>{ignore}</p>
    <p><strong>{expires}</strong></p>
    """

    result = send_email_via_sendgrid(email, subject, body_text, body_html)

    if result:
        logger.info(f"Registration email sent successfully - Email: {email}")
    else:
        logger.error(f"Registration email failed - Email: {email}")

    return result


def send_login_link_email(user, token):
    """Send magic link for passwordless login (15 min expiry)"""
    logger.info(
        f"Initiating login link email - User: {user.username}, Email: {user.email}"
    )

    login_url = url_for("login_with_token", token=token, _external=True)

    with force_locale(_recipient_language(user)):
        subject = _("Your Login Link - Irish Music Sessions")
        expires = _("This link will expire in 15 minutes.")
        ignore = _("If you did not request this login link, please ignore this email.")
        body_text = f"""{_("Click this link to log in to Irish Music Sessions:")}
{login_url}

{expires}

{ignore}
"""

        body_html = f"""
    <h2>{_("Log In to Irish Music Sessions")}</h2>
    <p>{_("Click the button below to log in:")}</p>
    {_button(login_url, _("Log In"))}
    <p>{_("If the button doesn't work, copy and paste this link into your browser:")}</p>
    <p>{login_url}</p>
    <p><strong>{expires}</strong></p>
    <p>{ignore}</p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Login link email sent successfully - User: {user.username}")
    else:
        logger.error(
            f"Login link email failed - User: {user.username}, Email: {user.email}"
        )

    return result


def send_person_added_email(admin, person, session):
    """Tell a session's admin that someone was added to it, in the admin's language.
    `admin`: dict(name, email, language); `person`: dict(name, email, relationship);
    `session`: dict(name, location, path). An empty location reads "Unknown"."""
    with force_locale(admin.get("language") or "en"):
        location = session["location"] or _("Unknown")
        subject = _("New person added to session: %(session)s", session=session["name"])
        args = dict(person=person["name"], session=session["name"], location=location)
        if person["relationship"] == "member":
            added = _(
                '%(person)s has been added to the session "%(session)s" in %(location)s as a member.',
                **args,
            )
        elif person["relationship"] == "visitor":
            added = _(
                '%(person)s has been added to the session "%(session)s" in %(location)s as a visitor.',
                **args,
            )
        else:
            added = _(
                '%(person)s has been added to the session "%(session)s" in %(location)s as a %(relationship)s.',
                relationship=person["relationship"],
                **args,
            )
        review_url = f"https://ceol.io/admin/sessions/{session['path']}/people"
        body = f"""{_("Hello %(name)s,", name=admin["name"])}

{added}

{_("Person Details:")}
- {_("Name: %(name)s", name=person["name"])}
- {_("Email: %(email)s", email=person["email"] or _("Not provided"))}

{_("You can review and modify this person's role in the session admin interface: %(url)s", url=review_url)}

{_("Best regards,")}
{_("The Ceol.io Session Management System")}"""
    return send_email_via_sendgrid(admin["email"], subject, body)


def _unsubscribe_serializer():
    return URLSafeSerializer(current_app.secret_key, salt="email-unsub")


def generate_unsubscribe_token(user_id):
    """Signed, non-expiring unsubscribe token for a user (spec 027)."""
    return _unsubscribe_serializer().dumps(user_id)


def verify_unsubscribe_token(token):
    """Return the user_id encoded in an unsubscribe token, or None if invalid."""
    try:
        return _unsubscribe_serializer().loads(token)
    except BadSignature:
        return None


def send_update_email(user_id, to_email, subject, body_markdown):
    """Send one app-update email (spec 027): Markdown body, personalized
    unsubscribe link, from the updates sender (default ceol@ceol.io)."""
    from_email = os.environ.get("MAIL_UPDATES_SENDER", "ceol@ceol.io")

    unsubscribe_url = url_for(
        "unsubscribe_updates",
        token=generate_unsubscribe_token(user_id),
        _external=True,
    )

    with force_locale(_language_of_user_id(user_id)):
        opted_in = _(
            "You're receiving this because you opted in to updates on ceol.io."
        )
        unsubscribe = _("Unsubscribe")
        footer_text = opted_in + "\n" + _("Unsubscribe: %(url)s", url=unsubscribe_url)
    # Plain-text part is the raw Markdown source (readable as-is)
    body_text = f"{body_markdown}\n\n--\n{footer_text}\n"

    body_html = f"""
    {markdown.markdown(body_markdown)}
    <hr style="margin-top: 2em; border: none; border-top: 1px solid #ddd;">
    <p style="color: #6c757d; font-size: 0.85em;">
        {opted_in}
        <a href="{unsubscribe_url}">{unsubscribe}</a>
    </p>
    """

    return send_email_via_sendgrid(
        to_email,
        subject,
        body_text,
        body_html,
        from_email=from_email,
        unsubscribe_url=unsubscribe_url,
    )
