"""Flask application factory.

create_app() builds and configures the app. Using a function (instead of a
global app object) lets tests create a fresh app with a test database.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from app.db import close_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    # Read settings from .env so secrets never live in the code.
    load_dotenv(PROJECT_ROOT / ".env")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["DB_PATH"] = str(PROJECT_ROOT / os.getenv("DB_PATH", "db/ptsd_system.db"))

    # Tests can override settings (e.g. point at a temporary database).
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "change-me":
        raise RuntimeError("Set a real SECRET_KEY in .env (see .env.example).")

    # Close the database connection automatically after every request.
    app.teardown_appcontext(close_db)

    # Register the routes (URLs). Each area of the site is a "blueprint".
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
