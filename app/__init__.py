"""Flask application factory.

create_app() builds and configures the app. Using a function (instead of a
global app object) lets tests create a fresh app with a separate test database.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, render_template

from app import security
from app.db import close_db
from app.ml_service import model_service
from ml.features import RISK_THRESHOLDS

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    # Read settings from .env so secrets never live in the code.
    load_dotenv(PROJECT_ROOT / ".env")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DB_PATH=str(PROJECT_ROOT / os.getenv("DB_PATH", "db/ptsd_system.db")),
        # Name shown in the header, e.g. "Ministry of Defence - Health Services".
        ORG_NAME=os.getenv("ORG_NAME", "Defence Health Services"),
        # Emergency number shown in the footer and on results.
        SUPPORT_LINE=os.getenv("SUPPORT_LINE", "999 or 112"),
        # Probability cut-offs for Low / Moderate / High (configurable per deployment).
        RISK_MODERATE=float(os.getenv("RISK_MODERATE", RISK_THRESHOLDS["moderate"])),
        RISK_HIGH=float(os.getenv("RISK_HIGH", RISK_THRESHOLDS["high"])),
        # Session cookie: not readable by JavaScript, not sent by other sites,
        # HTTPS-only in production, and expires after 30 minutes of inactivity.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SECURE_COOKIES", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,   # 5 MB upload limit (model files)
        CSRF_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "change-me":
        raise RuntimeError("Set a real SECRET_KEY in .env (see .env.example).")

    # Load the ML model once, at startup.
    model_service.load_active(app.config["DB_PATH"])
    if not model_service.ready:
        app.logger.warning("Prediction model not loaded: %s", model_service.error)

    # Run on every request.
    app.before_request(security.load_current_user)
    app.before_request(security.check_csrf)
    app.after_request(security.add_security_headers)
    app.teardown_appcontext(close_db)

    # Values every template can use.
    @app.context_processor
    def template_globals():
        return {
            "csrf_token": security.csrf_token,
            "org_name": app.config["ORG_NAME"],
            "support_line": app.config["SUPPORT_LINE"],
            "risk_moderate": app.config["RISK_MODERATE"],
            "risk_high": app.config["RISK_HIGH"],
            "role_labels": security.ROLE_LABELS,
            "current_user": g.get("user"),
        }

    from app.routes import admin, auth, main, personnel, therapist
    for module in (main, auth, personnel, therapist, admin):
        app.register_blueprint(module.bp)

    for code in (400, 403, 404, 413, 500):
        app.register_error_handler(
            code, lambda e, code=code: (render_template("error.html", code=code, error=e), code))

    return app
