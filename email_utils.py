import os
from flask import url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send_email_via_sendgrid(to_email, subject, body_text, body_html=None):
    """Send email using SendGrid API"""
    try:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            print("SendGrid API key not configured")
            return False

        from_email = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@ceol.io")

        sg = SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body_text,
            html_content=body_html,
        )

        response = sg.send(message)

        # Check response status
        if response.status_code in [200, 201, 202]:
            print(f"Email sent successfully to {to_email}")
            return True
        else:
            print(f"SendGrid returned status {response.status_code}: {response.body}")
            return False

    except Exception as e:
        print(f"SendGrid email error: {str(e)}")
        # Log more specific error types
        if "unauthorized" in str(e).lower():
            print("Check your SENDGRID_API_KEY")
        elif "forbidden" in str(e).lower():
            print("Check that sender email is verified in SendGrid")
        return False


def send_password_reset_email(user, token):
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

    return send_email_via_sendgrid(user.email, subject, body_text, body_html)


def send_verification_email(user, token):
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

    return send_email_via_sendgrid(user.email, subject, body_text, body_html)
