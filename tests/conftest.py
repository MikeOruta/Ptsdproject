"""Shared test setup: every test gets a brand-new temporary database, so tests
never touch real data and never affect each other."""
import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from app import create_app

ROOT = Path(__file__).resolve().parent.parent
MODEL_FILE = ROOT / "ml" / "model_v1.pkl"
PASSWORD = "TestPassw0rd99"

VALID_ASSESSMENT = {
    "age": "29", "gender": "male", "deployment_duration_months": "12",
    "combat_exposure": "8", "prior_trauma": "1", "social_isolation": "7",
    "sleep_score": "8", "anxiety_score": "15", "depression_score": "18",
    "alcohol_use": "14", "consent": "yes",
}


@pytest.fixture
def app(tmp_path):
    if not MODEL_FILE.exists():
        pytest.skip("Train the model first: python -m ml.train_model")
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO ml_models (version, file_path, is_active) VALUES ('test', 'ml/model_v1.pkl', 1)")
    conn.commit()
    conn.close()
    return create_app({"DB_PATH": str(db_path), "SECRET_KEY": "test-secret", "CSRF_ENABLED": False,
                       "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Create a user with any role directly in the database."""
    def _make(email, role, name="Test User"):
        conn = sqlite3.connect(app.config["DB_PATH"])
        uid = conn.execute("INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                           (email, generate_password_hash(PASSWORD), name, role)).lastrowid
        if role == "military_personnel":
            conn.execute("INSERT INTO military_personnel (user_id, service_number) VALUES (?, ?)", (uid, f"SN{uid}"))
        elif role == "therapist":
            conn.execute("INSERT INTO therapists (user_id) VALUES (?)", (uid,))
        else:
            conn.execute("INSERT INTO admins (user_id) VALUES (?)", (uid,))
        conn.commit()
        conn.close()
        return uid
    return _make


def login(client, email, role, password=PASSWORD):
    return client.post(f"/auth/login?role={role}", data={"email": email, "password": password, "role": role})
