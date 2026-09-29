"""Registration, login, logout, lockout and password storage."""
import sqlite3

from tests.conftest import PASSWORD, login

REGISTRATION = {"full_name": "Jane Soldier", "email": "jane@example.org", "service_number": "sn123",
                "password": PASSWORD, "confirm_password": PASSWORD}


def test_register_then_login(client, app):
    r = client.post("/auth/register", data=REGISTRATION)
    assert r.status_code == 302                       # redirected to login
    r = login(client, "jane@example.org", "military_personnel")
    assert r.status_code == 302 and "/personnel" in r.headers["Location"]


def test_therapist_register_then_login(client):
    data = {
        "role": "therapist",
        "full_name": "Dr. Sarah Reid",
        "email": "sarah@example.org",
        "license_number": "LIC-456",
        "specialization": "PTSD recovery",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    r = client.post("/auth/register", data=data)
    assert r.status_code == 302
    r = login(client, "sarah@example.org", "therapist")
    assert r.status_code == 302 and "/therapist" in r.headers["Location"]


def test_password_is_hashed_not_plain(client, app):
    client.post("/auth/register", data=REGISTRATION)
    stored = sqlite3.connect(app.config["DB_PATH"]).execute(
        "SELECT password_hash FROM users WHERE email = 'jane@example.org'").fetchone()[0]
    assert PASSWORD not in stored and stored.startswith(("scrypt:", "pbkdf2:"))


def test_weak_password_rejected(client):
    r = client.post("/auth/register", data={**REGISTRATION, "password": "short", "confirm_password": "short"})
    assert r.status_code == 200 and b"at least 10 characters" in r.data


def test_duplicate_email_rejected(client):
    client.post("/auth/register", data=REGISTRATION)
    r = client.post("/auth/register", data={**REGISTRATION, "service_number": "other"})
    assert b"already exists" in r.data


def test_wrong_password(client, make_user):
    make_user("a@example.org", "military_personnel")
    r = login(client, "a@example.org", "military_personnel", password="WrongPass123")
    assert r.status_code == 401


def test_wrong_role_tab_is_rejected(client, make_user):
    """Choosing the Administrator tab with a service member's account must fail."""
    make_user("a@example.org", "military_personnel")
    assert login(client, "a@example.org", "administrator").status_code == 401


def test_lockout_after_five_failures(client, make_user):
    make_user("a@example.org", "military_personnel")
    for _ in range(5):
        login(client, "a@example.org", "military_personnel", password="WrongPass123")
    # Even the correct password is refused while locked.
    assert login(client, "a@example.org", "military_personnel").status_code == 429


def test_deactivated_user_cannot_login(client, app, make_user):
    uid = make_user("a@example.org", "military_personnel")
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (uid,))
    conn.commit()
    assert login(client, "a@example.org", "military_personnel").status_code == 401


def test_logout(client, make_user):
    make_user("a@example.org", "military_personnel")
    login(client, "a@example.org", "military_personnel")
    client.post("/auth/logout")
    assert client.get("/personnel/").status_code == 302   # back to login


def test_csrf_blocks_forged_post(app, make_user):
    """With CSRF protection on, a POST without the token is rejected."""
    app.config["CSRF_ENABLED"] = True
    assert app.test_client().post("/auth/login", data={"email": "x@y.org", "password": "x"}).status_code == 400
