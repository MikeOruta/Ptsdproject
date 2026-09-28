"""Role-Based Access Control: each role reaches only its own pages."""
import pytest

from tests.conftest import VALID_ASSESSMENT, login

PAGES = {
    "military_personnel": ["/personnel/", "/personnel/assessment", "/personnel/history"],
    "therapist": ["/clinician/", "/clinician/report"],
    "administrator": ["/admin/", "/admin/users", "/admin/questions", "/admin/models", "/admin/logs"],
}


@pytest.mark.parametrize("page", [p for pages in PAGES.values() for p in pages])
def test_anonymous_users_are_sent_to_login(client, page):
    r = client.get(page)
    assert r.status_code == 302 and "/auth/login" in r.headers["Location"]


@pytest.mark.parametrize("role", PAGES)
def test_each_role_can_open_its_own_pages(client, make_user, role):
    make_user("u@example.org", role)
    login(client, "u@example.org", role)
    for page in PAGES[role]:
        assert client.get(page).status_code == 200, page


@pytest.mark.parametrize("role", PAGES)
def test_each_role_is_blocked_from_other_roles_pages(client, make_user, role):
    make_user("u@example.org", role)
    login(client, "u@example.org", role)
    for other_role, pages in PAGES.items():
        if other_role != role:
            for page in pages:
                assert client.get(page).status_code == 403, f"{role} reached {page}"


def test_member_cannot_see_another_members_result(app, make_user):
    make_user("a@example.org", "military_personnel")
    make_user("b@example.org", "military_personnel")
    a, b = app.test_client(), app.test_client()
    login(a, "a@example.org", "military_personnel")
    login(b, "b@example.org", "military_personnel")
    location = a.post("/personnel/assessment", data=VALID_ASSESSMENT).headers["Location"]
    assert a.get(location).status_code == 200
    assert b.get(location).status_code == 404


def test_access_denied_is_logged(client, app, make_user):
    import sqlite3
    make_user("u@example.org", "military_personnel")
    login(client, "u@example.org", "military_personnel")
    client.get("/admin/")
    n = sqlite3.connect(app.config["DB_PATH"]).execute(
        "SELECT COUNT(*) FROM system_logs WHERE action = 'access_denied'").fetchone()[0]
    assert n == 1


def test_admin_cannot_deactivate_self(client, make_user):
    uid = make_user("admin@example.org", "administrator")
    login(client, "admin@example.org", "administrator")
    r = client.post(f"/admin/users/{uid}/toggle", follow_redirects=True)
    assert b"cannot deactivate your own account" in r.data
