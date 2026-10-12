"""Create a staff account from the command line (used to create the FIRST
administrator, who can then create everyone else in the web console), or reset
the password of an existing account.

Usage (from the project root):
    python -m db.create_user --role administrator --email you@example.org --name "Your Name"
    python -m db.create_user --reset --email you@example.org
The password is typed privately (not shown, not saved in shell history).
"""
import argparse
import getpass
import sqlite3
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.validation import validate_email, validate_password


def ask_password():
    """Prompt twice for a password and validate it."""
    password = getpass.getpass("Password: ")
    if err := validate_password(password):
        sys.exit(err)
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return password


def reset_password(email):
    """Replace the stored hash for an existing account and log it."""
    password = ask_password()
    with create_app().app_context():
        db = get_db()
        with db:
            user = db.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
            if user is None:
                sys.exit("No account with that email.")
            db.execute("UPDATE users SET password_hash = ? WHERE user_id = ?",
                       (generate_password_hash(password), user["user_id"]))
            # Audit trail: no web request here, so no IP address.
            db.execute("INSERT INTO system_logs (user_id, action, details) VALUES (?, ?, ?)",
                       (user["user_id"], "password_reset", "Reset from command line"))
    print(f"Password reset for {email}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true",
                        help="reset the password of an existing account")
    parser.add_argument("--role", choices=["administrator", "therapist"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if err := validate_email(email):
        sys.exit(err)

    if args.reset:
        reset_password(email)
        return

    if not args.role or not args.name:
        parser.error("--role and --name are required when creating an account")
    password = ask_password()

    with create_app().app_context():
        db = get_db()
        try:
            with db:
                cur = db.execute(
                    "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                    (email, generate_password_hash(password), args.name.strip(), args.role))
                if args.role == "therapist":
                    db.execute("INSERT INTO therapists (user_id) VALUES (?)", (cur.lastrowid,))
                else:
                    db.execute("INSERT INTO admins (user_id) VALUES (?)", (cur.lastrowid,))
        except sqlite3.IntegrityError:
            sys.exit("An account with that email already exists.")
    print(f"Created {args.role} account for {email}.")


if __name__ == "__main__":
    main()
