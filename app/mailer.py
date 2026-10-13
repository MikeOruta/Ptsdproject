"""Sending email, and the signed links used to confirm an email address.

Email is sent with Python's built-in smtplib, using the SMTP settings in .env
(for Gmail: MAIL_SERVER=smtp.gmail.com, MAIL_PORT=587 and an App Password).
If MAIL_SERVER is not set - e.g. on a developer's laptop - the email is printed
to the terminal instead, so the verification flow can still be tested.

Verification links contain a token signed with SECRET_KEY (itsdangerous, which
comes with Flask). Nobody can forge or alter a token without the secret key,
and each token expires after VERIFY_MAX_AGE seconds. No token is stored in the
database.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

VERIFY_SALT = "email-verify"            # keeps these tokens separate from any other signed data
VERIFY_MAX_AGE = 24 * 60 * 60           # links expire after 24 hours


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=VERIFY_SALT)


def make_verify_token(user_id, email):
    """Signed token holding the user id and email. The email is included so a
    token stops working if the account's email address is ever changed."""
    return _serializer().dumps({"uid": user_id, "email": email})


def read_verify_token(token):
    """Return (user_id, email) from a valid token, or None if it is invalid or expired."""
    try:
        data = _serializer().loads(token, max_age=VERIFY_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    return data.get("uid"), data.get("email")


def mail_configured():
    """True when .env has a mail server AND login details, so real emails can be sent."""
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))


def send_email(to, subject, body):
    """Send a plain-text email. Returns True if it was sent (or printed in dev mode)."""
    cfg = current_app.config
    if not mail_configured():
        # Development mode: email not set up in .env, so show it in the terminal.
        print(f"\n--- EMAIL (not sent: email settings in .env are incomplete) ---\n"
              f"To: {to}\nSubject: {subject}\n\n{body}\n---\n", flush=True)
        return True

    msg = EmailMessage()
    msg["From"] = cfg.get("MAIL_FROM") or cfg.get("MAIL_USERNAME")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
            smtp.starttls()                                   # encrypt the connection
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        current_app.logger.error("Could not send email to %s: %s", to, e)
        return False
    return True


def send_verification_email(user_id, email, full_name):
    """Email the user a link that confirms they own this address."""
    link = url_for("auth.verify_email", token=make_verify_token(user_id, email), _external=True)
    body = (
        f"Hello {full_name},\n\n"
        f"Thank you for registering with {current_app.config['ORG_NAME']}.\n"
        "Please confirm that this is your email address by opening the link below:\n\n"
        f"{link}\n\n"
        "The link expires in 24 hours. If you did not create this account, ignore this email.\n"
    )
    return send_email(email, "Confirm your email address", body)
