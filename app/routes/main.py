"""Main routes. Phase 1: a hello page that proves the app can reach the database."""
from flask import Blueprint, render_template

from app.db import get_db

bp = Blueprint("main", __name__)


@bp.route("/")
def hello():
    db = get_db()
    # Count the tables SQLite knows about (skip SQLite's internal table).
    table_count = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name != 'sqlite_sequence'"
    ).fetchone()[0]
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return render_template("hello.html", table_count=table_count, user_count=user_count)
