"""Registration, login and logout.

- Passwords are stored as salted hashes (werkzeug), never as plain text.
- Only service members can self-register. Mental health professionals and
  administrators are created by an administrator (see admin.py), so nobody
  can give themselves elevated access.
- The login page has role tabs, but the SERVER checks the chosen role against
  the account's real role.
- 5 failed attempts within 15 minutes locks the account for 15 minutes.
- Self-registered accounts must confirm their email (signed link, see
  app/mailer.py) before they can sign in.
"""
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db
from app.mailer import mail_configured, read_verify_token, send_verification_email
from app.security import ROLE_HOME, ROLES, log_action
from app.validation import clean_text, validate_email, validate_password

bp = Blueprint("auth", __name__, url_prefix="/auth")

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
MAX_VERIFY_EMAILS_PER_HOUR = 3   # stops the resend button being used to spam someone


def is_locked_out(email):
    count = get_db().execute(
        """SELECT COUNT(*) FROM system_logs
           WHERE action = 'login_failed' AND details = ?
             AND created_at >= datetime('now', ?)""",
        (email, f"-{LOCKOUT_MINUTES} minutes"),
    ).fetchone()[0]
    return count >= MAX_FAILED_LOGINS


def safe_next(target):
    """Only allow redirects to pages on this site (blocks open-redirect attacks)."""
    return target if target and target.startswith("/") and not target.startswith("//") else None


def send_verification(user):
    """Email a verification link, at most MAX_VERIFY_EMAILS_PER_HOUR times per account."""
    sent = get_db().execute(
        """SELECT COUNT(*) FROM system_logs WHERE action = 'verification_sent'
           AND details = ? AND created_at >= datetime('now', '-1 hour')""",
        (user["email"],)).fetchone()[0]
    if sent >= MAX_VERIFY_EMAILS_PER_HOUR:
        return False
    if send_verification_email(user["user_id"], user["email"], user["full_name"]):
        log_action("verification_sent", user["email"], user_id=user["user_id"])
        return True
    return False


@bp.route("/login", methods=["GET", "POST"])
def login():
    # On submit, the role chosen in the form's "Access as" dropdown wins over the
    # ?role= in the address (which is only the default tab the page opened on).
    if request.method == "POST":
        role = request.form.get("role") or request.args.get("role", "military_personnel")
    else:
        role = request.args.get("role", "military_personnel")
    valid_roles = ("military_personnel", "therapist", "administrator")
    if role not in valid_roles:
        role = "military_personnel"

    if request.method == "POST":
        email = clean_text(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        db = get_db()

        if is_locked_out(email):
            flash(f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.", "error")
            return render_template("auth/login.html", role=role, email=email), 429

        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        # One generic message for every failure, so attackers can't tell
        # whether an email exists or which role it has.
        if (user is None or not user["is_active"] or user["role"] != role
                or not check_password_hash(user["password_hash"], password)):
            log_action("login_failed", email, user_id=None)
            flash("Incorrect email, password or role.", "error")
            return render_template("auth/login.html", role=role, email=email), 401

        # Checked only after the password is correct, so this message never
        # reveals to a stranger whether an email is registered.
        if not user["email_verified"]:
            log_action("login_unverified", email, user_id=user["user_id"])
            session["verify_email"] = email
            flash("Please confirm your email address first. Open the link we sent you, "
                  "or request a new one below.", "error")
            return redirect(url_for("auth.check_email"))

        session.clear()                    # new session on login (prevents session fixation)
        session.permanent = True            # applies the 30-minute timeout
        session["user_id"] = user["user_id"]
        db.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
                   (user["user_id"],))
        db.commit()
        log_action("login", f"role={user['role']}", user_id=user["user_id"])
        return redirect(safe_next(request.args.get("next")) or url_for(ROLE_HOME[user["role"]]))

    return render_template("auth/login.html", role=role, email="")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Self-registration for service members and clinicians.

    Administrators are created directly by the system administrator and are not
    available on the public registration page.
    """
    role = request.values.get("role", "military_personnel")
    if role not in ("military_personnel", "therapist"):
        role = "military_personnel"

    form = {}
    if request.method == "POST":
        form = {
            "full_name": clean_text(request.form.get("full_name"), 150),
            "email": clean_text(request.form.get("email"), 255).lower(),
            "service_number": clean_text(request.form.get("service_number"), 50).upper(),
            "branch": clean_text(request.form.get("branch"), 100),
            "military_rank": clean_text(request.form.get("military_rank"), 100),
            "license_number": clean_text(request.form.get("license_number"), 100).upper(),
            "specialization": clean_text(request.form.get("specialization"), 150),
        }
        password = request.form.get("password", "")
        errors = []
        if len(form["full_name"]) < 3:
            errors.append("Enter your full name.")
        if err := validate_email(form["email"]):
            errors.append(err)
        if role == "military_personnel" and not form["service_number"]:
            errors.append("Enter your service number.")
        if role == "therapist" and not form["license_number"]:
            errors.append("Enter your professional licence number.")
        if err := validate_password(password):
            errors.append(err)
        if password != request.form.get("confirm_password", ""):
            errors.append("Passwords do not match.")

        if not errors:
            db = get_db()
            try:
                with db:  # users row and profile row are saved together, or not at all
                    cur = db.execute(   # email_verified = 0 until the emailed link is opened
                        """INSERT INTO users (email, password_hash, full_name, role, email_verified)
                           VALUES (?, ?, ?, ?, 0)""",
                        (form["email"], generate_password_hash(password), form["full_name"], role))
                    if role == "military_personnel":
                        db.execute(
                            """INSERT INTO military_personnel (user_id, service_number, branch, military_rank)
                               VALUES (?, ?, ?, ?)""",
                            (cur.lastrowid, form["service_number"], form["branch"] or None,
                             form["military_rank"] or None))
                    else:
                        db.execute(
                            """INSERT INTO therapists (user_id, license_number, specialization)
                               VALUES (?, ?, ?)""",
                            (cur.lastrowid, form["license_number"], form["specialization"] or None))
            except sqlite3.IntegrityError:
                errors.append("An account with this email, service number or licence number already exists.")
            else:
                log_action("register", f"role={role} email={form['email']}", user_id=cur.lastrowid)
                user = db.execute("SELECT * FROM users WHERE user_id = ?", (cur.lastrowid,)).fetchone()
                if not send_verification(user):
                    flash("Your account was created, but we could not send the email. "
                          "Use the button below to try again.", "error")
                session["verify_email"] = form["email"]
                return redirect(url_for("auth.check_email"))

        for e in errors:
            flash(e, "error")
    return render_template("auth/register.html", form=form, role=role)


@bp.route("/check-email", methods=["GET", "POST"])
def check_email():
    """'Check your inbox' page, with a button to resend the link."""
    email = session.get("verify_email")
    if email is None:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is not None and not user["email_verified"]:
            if send_verification(user):
                flash("A new confirmation link has been sent.", "success")
            else:
                flash("We could not send another email right now. Please try again later.", "error")
        return redirect(url_for("auth.check_email"))
    return render_template("auth/check_email.html", email=email, mail_configured=mail_configured())


@bp.route("/verify/<token>")
def verify_email(token):
    """The link in the email lands here. A valid token marks the email as verified."""
    data = read_verify_token(token)
    if data is None:
        return render_template("auth/verified.html", ok=False), 400
    user_id, email = data
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE user_id = ? AND email = ?", (user_id, email)).fetchone()
    if user is None:
        return render_template("auth/verified.html", ok=False), 400
    if not user["email_verified"]:
        db.execute("UPDATE users SET email_verified = 1 WHERE user_id = ?", (user_id,))
        db.commit()
        log_action("email_verified", email, user_id=user_id)
    session.pop("verify_email", None)
    return render_template("auth/verified.html", ok=True, role=user["role"])


@bp.route("/logout", methods=["POST"])
def logout():
    if g.user is not None:
        log_action("logout")
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
