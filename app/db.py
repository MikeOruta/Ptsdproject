"""Database helpers: one SQLite connection per web request.

How it works:
- get_db() opens a connection the first time a request needs it and stores it
  on Flask's `g` object (a per-request scratch space), so later calls in the
  same request reuse it.
- close_db() runs automatically when the request ends and closes it.
"""
import sqlite3

from flask import current_app, g


def get_db():
    """Return this request's database connection, opening it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        # Rows behave like dicts: row["email"] instead of row[1]. Easier to read.
        g.db.row_factory = sqlite3.Row
        # SQLite ignores foreign keys unless each connection switches them on.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def upgrade_db(db_path):
    """Bring an older database up to date without deleting its data.
    Runs once at startup. Adds users.email_verified if it is missing; existing
    accounts are treated as verified (DEFAULT 1) so nobody is locked out."""
    conn = sqlite3.connect(db_path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
        if columns and "email_verified" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1 "
                         "CHECK (email_verified IN (0,1))")
            conn.commit()
    finally:
        conn.close()


def close_db(error=None):
    """Close the connection at the end of the request (if one was opened)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()
