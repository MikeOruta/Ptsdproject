"""Security building blocks used by every part of the app.

- login_required / role_required : Role-Based Access Control (RBAC) decorators
- CSRF protection                 : every POST form must carry a secret token
- log_action                      : writes key actions to system_logs (audit trail)
- security headers                : tell the browser to block common attacks
"""
import secrets
from functools import wraps

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from app.db import get_db

ROLES = ("military_personnel", "therapist", "administrator")
ROLE_LABELS = {
    "military_personnel": "Service Member",
    "therapist": "Mental Health Professional",
    "administrator": "Administrator",
}
# Where each role lands after logging in.
ROLE_HOME = {
    "military_personnel": "personnel.dashboard",
    "therapist": "therapist.dashboard",
    "administrator": "admin.dashboard",
}


# ------------------------------------------------------------ current user
def load_current_user():
    """Runs before every request: put the logged-in user (or None) on g.user."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = get_db().execute(
            "SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        if user is None:          # account deleted or deactivated -> log out
            session.clear()
        else:
            g.user = user


# ------------------------------------------------------------ RBAC decorators
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Allow the view only for the given roles. Checked on the SERVER, so a user
    cannot reach another role's pages by typing the URL."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                log_action("access_denied", f"{g.user['role']} tried {request.path}")
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------------------------------------------ CSRF
def csrf_token():
    """One random token per session, embedded in every form as a hidden field."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf():
    """Runs before every request: reject POSTs without the matching token, so
    another website cannot submit forms on a signed-in user's behalf."""
    if request.method == "POST" and current_app.config.get("CSRF_ENABLED", True):
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        # Both must be non-empty: otherwise "no token" would match "no token".
        if not sent or not expected or not secrets.compare_digest(sent, expected):
            abort(400, "Your form expired. Please go back, refresh the page and try again.")


# ------------------------------------------------------------ audit log
def log_action(action, details=None, user_id=None):
    """Record an action in system_logs. Parameterised SQL, never string-built."""
    if user_id is None and g.get("user") is not None:
        user_id = g.user["user_id"]
    db = get_db()
    db.execute(
        "INSERT INTO system_logs (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, action, details, request.remote_addr),
    )
    db.commit()


# ------------------------------------------------------------ headers
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"       # no MIME guessing
    response.headers["X-Frame-Options"] = "DENY"                 # no clickjacking via iframes
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (              # only load our own files
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.endpoint and request.endpoint != "static":
        # Sensitive pages must not be stored in the browser cache.
        response.headers["Cache-Control"] = "no-store"
    return response
