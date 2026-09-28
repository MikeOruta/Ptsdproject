"""Create (or reset) the SQLite database from db/schema.sql and list its tables.

Usage (from the project root, with the venv active):
    python db/init_db.py

WARNING: schema.sql drops and recreates every table, so this wipes all data.
"""
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "db" / "schema.sql"

# The database file location comes from .env (DB_PATH), relative to the project root.
load_dotenv(PROJECT_ROOT / ".env")
DB_PATH = PROJECT_ROOT / os.getenv("DB_PATH", "db/ptsd_system.db")

EXPECTED_TABLES = {
    "users", "military_personnel", "therapists", "admins", "system_logs",
    "assessments", "prediction_results", "therapist_notes",
    "assessment_questions", "ml_models",
}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite needs this on every connection
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()

    # Ask SQLite which tables now exist (sqlite_sequence is SQLite's own internal table).
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'sqlite_sequence'"
    ).fetchall()
    conn.close()

    found = {name for (name,) in rows}
    print(f"Database: {DB_PATH}")
    for name in sorted(found):
        print(f"  [ok] {name}")
    missing = EXPECTED_TABLES - found
    if missing:
        raise SystemExit(f"Missing tables: {', '.join(sorted(missing))}")
    print(f"All {len(EXPECTED_TABLES)} tables created.")


if __name__ == "__main__":
    main()
