import os
import logging
from flask import url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Header

# Configure logger for email operations
logger = logging.getLogger(__name__)


def send_email_via_sendgrid(to_email, subject, body_text, body_html=None):
    """Send email using SendGrid API"""
    try:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            logger.error("SendGrid API key not configured")
            return False

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

        # Add List-Unsubscribe headers for better deliverability
        message.header = Header("List-Unsubscribe", f"<mailto:{unsubscribe_email}>")
        message.add_header(Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"))

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


def send_password_reset_email(user, token):
    logger.info(f"Initiating password reset email - User: {user.username}, Email: {user.email}")

    reset_url = url_for("reset_password", token=token, _external=True)

    subject = "Password Reset Request - Irish Music Sessions"
    body_text = f"""To reset your password, visit the following link:
{reset_url}

If you did not make this request, please ignore this email and no changes will be made.

This link will expire in 1 hour.
"""

    body_html = f"""
    <h2>Password Reset Request</h2>
    <p>To reset your password, click the following link:</p>
    <p><a href="{reset_url}">Reset Your Password</a></p>
    <p>If you did not make this request, please ignore this email and no changes will be made.</p>
    <p><strong>This link will expire in 1 hour.</strong></p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Password reset email sent successfully - User: {user.username}")
    else:
        logger.error(f"Password reset email failed - User: {user.username}, Email: {user.email}")

    return result


def send_verification_email(user, token):
    logger.info(f"Initiating verification email - User: {user.username}, Email: {user.email}")

    verification_url = url_for("verify_email", token=token, _external=True)

    subject = "Verify Your Email Address - Irish Music Sessions"
    body_text = f"""Welcome to Irish Music Sessions!

Please click the following link to verify your email address and activate your account:
{verification_url}

If you did not create this account, please ignore this email.

This link will expire in 24 hours.
"""

    body_html = f"""
    <h2>Welcome to Irish Music Sessions!</h2>
    <p>Thank you for registering with us. Please verify your email address to activate your account.</p>
    <p><a href="{verification_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email Address</a></p>
    <p>If the button doesn't work, copy and paste this link into your browser:</p>
    <p>{verification_url}</p>
    <p>If you did not create this account, please ignore this email.</p>
    <p><strong>This link will expire in 24 hours.</strong></p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Verification email sent successfully - User: {user.username}")
    else:
        logger.error(f"Verification email failed - User: {user.username}, Email: {user.email}")

    return result


def send_login_link_email(user, token):
    """Send magic link for passwordless login (15 min expiry)"""
    logger.info(f"Initiating login link email - User: {user.username}, Email: {user.email}")

    login_url = url_for("login_with_token", token=token, _external=True)

    subject = "Your Login Link - Irish Music Sessions"
    body_text = f"""Click this link to log in to Irish Music Sessions:
{login_url}

This link will expire in 15 minutes.

If you did not request this login link, please ignore this email.
"""

    body_html = f"""
    <h2>Log In to Irish Music Sessions</h2>
    <p>Click the button below to log in:</p>
    <p><a href="{login_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Log In</a></p>
    <p>If the button doesn't work, copy and paste this link into your browser:</p>
    <p>{login_url}</p>
    <p><strong>This link will expire in 15 minutes.</strong></p>
    <p>If you did not request this login link, please ignore this email.</p>
    """

    result = send_email_via_sendgrid(user.email, subject, body_text, body_html)

    if result:
        logger.info(f"Login link email sent successfully - User: {user.username}")
    else:
        logger.error(f"Login link email failed - User: {user.username}, Email: {user.email}")

    return result
