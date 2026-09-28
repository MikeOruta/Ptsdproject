"""Fill the database with FICTIONAL demo accounts and assessments, so the
system can be demonstrated (e.g. to supervisors) without any real data.

Usage (from the project root):  python -m db.seed_demo
Requires DEMO_PASSWORD in .env - every demo account uses that password.
All demo emails end in @demo.local. The people are invented; their answers
are rows from the SYNTHETIC dataset, scored by the real model.
"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.ml_service import model_service
from app.validation import validate_password
from ml.features import FEATURES, TARGET
from ml.train_model import DEFAULT_DATA, clean

MEMBERS = [
    ("Brian Otieno", "Corporal", "Army"), ("Faith Wanjiru", "Private", "Army"),
    ("Kevin Mutua", "Sergeant", "Army"), ("Amina Hassan", "Lieutenant", "Air Force"),
    ("Daniel Kiprop", "Private", "Army"), ("Grace Achieng", "Corporal", "Navy"),
    ("Peter Njoroge", "Warrant Officer", "Army"), ("Mercy Chebet", "Private", "Air Force"),
    ("Samuel Omondi", "Lance Corporal", "Army"), ("Joyce Mwende", "Sergeant", "Navy"),
    ("Ibrahim Abdi", "Private", "Army"), ("Esther Nyambura", "Captain", "Army"),
    ("Collins Wafula", "Corporal", "Army"), ("Lucy Moraa", "Private", "Navy"),
]
STAFF = [
    ("Dr. Ruth Kamau", "clinician1@demo.local", "therapist", "Clinical Psychologist"),
    ("Dr. James Oduya", "clinician2@demo.local", "therapist", "Psychiatrist"),
    ("System Administrator", "admin@demo.local", "administrator", None),
]
NOTES = [
    "Contacted by phone. Reports poor sleep and irritability since return. Booked for assessment.",
    "Initial consultation completed. Referred for trauma-focused CBT. Review in 4 weeks.",
    "Follow-up: sleep improving, alcohol use reduced. Continue monitoring.",
]


def main():
    app = create_app()   # also loads .env, where DEMO_PASSWORD lives
    password = os.getenv("DEMO_PASSWORD", "")
    if err := validate_password(password):
        sys.exit(f"Set DEMO_PASSWORD in .env first ({err})")
    if not model_service.ready:
        sys.exit(f"Model not loaded: {model_service.error}")

    rng = random.Random(7)
    data, _ = clean(pd.read_csv(DEFAULT_DATA))
    data = data.dropna(subset=FEATURES)
    # Over-represent positive cases a little so every risk level appears in the demo.
    pool = pd.concat([data[data[TARGET] == 1].sample(20, random_state=1),
                      data[data[TARGET] == 0].sample(25, random_state=1)]).sample(frac=1, random_state=2)
    rows = iter(pool.to_dict("records"))
    pw_hash = generate_password_hash(password)

    with app.app_context():
        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE email LIKE '%@demo.local'").fetchone():
            sys.exit("Demo data already present. Run python db/init_db.py first to reset.")
        with db:
            therapist_ids = []
            for name, email, role, spec in STAFF:
                uid = db.execute("INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                                 (email, pw_hash, name, role)).lastrowid
                if role == "therapist":
                    therapist_ids.append(db.execute(
                        "INSERT INTO therapists (user_id, license_number, specialization) VALUES (?, ?, ?)",
                        (uid, f"PSY-{1000 + uid}", spec)).lastrowid)
                else:
                    db.execute("INSERT INTO admins (user_id) VALUES (?)", (uid,))

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for i, (name, rank, branch) in enumerate(MEMBERS, start=1):
                email = f"member{i:02d}@demo.local"
                uid = db.execute("INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, 'military_personnel')",
                                 (email, pw_hash, name)).lastrowid
                db.execute("INSERT INTO military_personnel (user_id, service_number, branch, military_rank) VALUES (?, ?, ?, ?)",
                           (uid, f"SN-{48200 + i * 37}", branch, rank))
                # 1-4 assessments per person, spread over the last six months.
                n = rng.choice([1, 1, 2, 3, 4])
                for k in range(n):
                    values = next(rows)
                    values = {f: (int(values[f]) if f != "gender" else values[f]) for f in FEATURES}
                    when = now - timedelta(days=rng.randint(0, 20) + (n - 1 - k) * 35, hours=rng.randint(0, 9))
                    p = model_service.predict_probability(values)
                    cat = "High" if p >= app.config["RISK_HIGH"] else "Moderate" if p >= app.config["RISK_MODERATE"] else "Low"
                    # Column names come from the fixed FEATURES list (not user input);
                    # all VALUES are still passed as ? parameters.
                    aid = db.execute(
                        f"""INSERT INTO assessments (user_id, {', '.join(FEATURES)}, consent_given, created_at)
                            VALUES (?, {', '.join('?' * len(FEATURES))}, 1, ?)""",
                        (uid, *[values[f] for f in FEATURES], when.strftime("%Y-%m-%d %H:%M:%S"))).lastrowid
                    db.execute("INSERT INTO prediction_results (assessment_id, model_id, probability, risk_category, created_at) VALUES (?, ?, ?, ?, ?)",
                               (aid, model_service.model_id, p, cat, when.strftime("%Y-%m-%d %H:%M:%S")))
                    if cat == "High" and rng.random() < 0.6:
                        db.execute("INSERT INTO therapist_notes (assessment_id, therapist_id, note, created_at) VALUES (?, ?, ?, ?)",
                                   (aid, rng.choice(therapist_ids), rng.choice(NOTES),
                                    (when + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")))
            db.execute("INSERT INTO system_logs (action, details) VALUES ('demo_seeded', 'Fictional demo data loaded')")
    print(f"Demo data loaded: {len(MEMBERS)} service members, {len(STAFF)} staff. "
          "Sign in with any @demo.local email and DEMO_PASSWORD from .env.")


if __name__ == "__main__":
    main()
