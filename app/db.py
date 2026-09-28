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


def close_db(error=None):
    """Close the connection at the end of the request (if one was opened)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()
