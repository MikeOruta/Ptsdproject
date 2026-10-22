"""Start the development server:  python run.py

Then Ctrl+click a link (here or in the terminal):
    Home / service member sign-in:  http://127.0.0.1:5000/auth/login
    Mental health professional:     http://127.0.0.1:5000/auth/login?role=therapist
    Administrator:                  http://127.0.0.1:5000/auth/login?role=administrator
"""
import os

from app import create_app

app = create_app()

BASE = "http://127.0.0.1:5000"
LINKS = {
    "Home":                         f"{BASE}/",
    "Service member sign-in":       f"{BASE}/auth/login",
    "Service member register":      f"{BASE}/auth/register",
    "Mental health professional":   f"{BASE}/auth/login?role=therapist",
    "Administrator":                f"{BASE}/auth/login?role=administrator",
}

if __name__ == "__main__":
    # With debug=True Flask starts the app twice (a watcher plus the real server);
    # WERKZEUG_RUN_MAIN is set only in the real server, so the links print once.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("\n  Open a page (Ctrl+click):")
        for name, url in LINKS.items():
            print(f"    {name:<28} {url}")
        print(flush=True)
    # debug=True reloads on code changes and shows errors. Development only.
    app.run(debug=True)
