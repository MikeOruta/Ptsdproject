"""Create a staff account from the command line (used to create the FIRST
administrator, who can then create everyone else in the web console).

Usage (from the project root):
    python -m db.create_user --role administrator --email you@example.org --name "Your Name"
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["administrator", "therapist"], required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    email = args.email.strip().lower()
    if err := validate_email(email):
        sys.exit(err)
    password = getpass.getpass("Password: ")
    if err := validate_password(password):
        sys.exit(err)
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")

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
