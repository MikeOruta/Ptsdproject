# Development Log — PTSD Risk Prediction System

A step-by-step record of how the system was built and why each decision was made.

---

## Step 0 — Project setup (2026-09-28)

**What was done**
- Created the project folder and linked it to the GitHub repository
  (MikeOruta/Ptsdproject) for version control.
- Created the folder structure:

  | Folder | Purpose |
  |---|---|
  | `app/` | The Flask web application (routes, templates, static files) |
  | `ml/` | Machine-learning code and the trained model |
  | `data/` | Datasets (synthetic only) |
  | `db/` | Database schema and setup script |
  | `docs/` | Documentation (this log, ethics statement) |
  | `tests/` | Automated tests |

- Created a Python **virtual environment** (`venv/`) so the project's packages are
  isolated from the rest of the computer, and listed them in `requirements.txt`
  (Flask, scikit-learn, pandas, joblib, python-dotenv, pytest).
- Created `.gitignore` so secrets (`.env`), the database file and the virtual
  environment are never uploaded to GitHub.
- Stored configuration (database location, secret key) in `.env`, with a safe
  template in `.env.example`. **Why:** secrets must never be written into source code.

## Step 0b — Database design (2026-09-28)

**What was done:** designed 10 tables in `db/schema.sql`:

| Table | Purpose |
|---|---|
| `users` | Login accounts; `role` is military_personnel, therapist or administrator |
| `military_personnel`, `therapists`, `admins` | One profile per user (1:1, `user_id UNIQUE`) |
| `assessments` | The answers a service member submits |
| `prediction_results` | The model's output for each assessment (1:1) |
| `therapist_notes` | Notes a therapist writes on an assessment |
| `assessment_questions` | Form questions the administrator can manage |
| `ml_models` | Each trained model version and its metrics; one is active |
| `system_logs` | Audit trail of key actions |

**Decisions**
- **Known Issue A — missing fields:** `assessments` includes age, gender,
  deployment duration, combat exposure, prior trauma and social isolation,
  because the model and input form need them.
- **Known Issue B — data leakage:** `pcl5_score` is stored for reference only and
  is **not** used as a model input. If the outcome is derived from PCL-5, using
  PCL-5 as an input would let the model "see the answer".
- **Database engine — SQLite instead of MySQL.** SQLite is built into Python,
  needs no separate server, and stores everything in one file. This matches the
  project's lightweight, low-resource design goal. Limitation: only one write at a
  time, which is fine for this scale; a large deployment would move to MySQL or
  PostgreSQL.
- Allowed values (roles, gender, score ranges) are enforced by the database itself
  with `CHECK` constraints, as a second line of defence behind form validation.

**How to verify:** `python db/init_db.py` creates the database and confirms all
10 tables exist.

## Phase 1 — Application skeleton (2026-09-28)

**What was done**

| File | What it does |
|---|---|
| `app/__init__.py` | *App factory*: builds the Flask app, loads settings from `.env`, registers routes. Refuses to start without a real secret key. |
| `app/db.py` | Opens one database connection per web request and closes it afterwards. Turns on foreign-key checking. |
| `app/routes/main.py` | The home page route (`/`). Queries the database to prove the connection works. |
| `app/templates/hello.html` | The HTML page shown to the user (Jinja2 template). |
| `run.py` | Starts the development server. |

**Why an app factory?** Tests can create a fresh copy of the app with a separate
test database, so tests never touch real data.

**Why a secret key?** Flask signs the login cookie with it, so users cannot forge
or edit their session (for example, to change their role). It is randomly
generated and kept in `.env`.

**Result:** running `python run.py` and opening http://127.0.0.1:5000 shows
*"Database connected: 10 tables found, 0 users registered."*

## Phase 2 — Machine learning model (2026-09-28)

Full details: [ML_MODEL.md](ML_MODEL.md).

| File | What it does |
|---|---|
| `ml/features.py` | Defines the 10 input features, valid ranges and risk thresholds, in one place (Objective 2) |
| `ml/generate_synthetic_data.py` | Creates the clearly-labelled synthetic dataset with documented relationships and deliberate data-quality problems |
| `ml/train_model.py` | Cleaning → imputation → scaling → encoding → feature selection → Logistic Regression; stratified split, 5-fold CV, metrics, saves the model and registers it in `ml_models` |

**Decision: synthetic data instead of public data (proposal §3.4).** No public
dataset has these features, and the available sample had data leakage. This is
documented as a limitation; the training script accepts a real dataset later
without code changes.

**Result:** test recall 0.71, precision 0.36, F1 0.48, ROC-AUC 0.79; risk
categories are ordered correctly (actual PTSD rate 7% Low → 23% Moderate → 48% High).

## Phase 3 — Backend (2026-09-28)

| File | What it does |
|---|---|
| `app/security.py` | `login_required` / `role_required` decorators (RBAC), CSRF tokens, audit logging, security headers |
| `app/validation.py` | Server-side validation of every input |
| `app/ml_service.py` | Loads the active model once at startup; predicts; explains which answers drove the result |
| `app/routes/auth.py` | Register (service members only), login with role tabs + server-side role check, lockout, logout |
| `app/routes/personnel.py` | Dashboard, assessment → prediction → result, history with trend |
| `app/routes/therapist.py` | Caseload sorted by risk, assessment review + notes, anonymous report |
| `app/routes/admin.py` | Users, question wording, model upload/activation, audit log |
| `db/create_user.py`, `db/seed_demo.py` | Create the first administrator; load fictional demo data |

**Key decisions**
- Only service members self-register; staff accounts are created by administrators,
  so nobody can give themselves elevated access.
- Administrators cannot read assessment answers (least privilege).
- Every clinician view of a record is logged (accountability for sensitive data).
- The assessment and its prediction are saved in one database transaction.
- Informed consent is required and enforced by the database.

## Phase 4 — Frontend (2026-09-28)

Government-service design: navy and gold, an "OFFICIAL · SENSITIVE" banner,
a role badge in the navigation bar, and accessible contrast and focus states.
No external fonts or frameworks, for speed on slow connections.

Pages: landing, login (role tabs), register, assessment form, risk result
(gauge, contributing factors, next steps, print), history with trend chart,
clinician caseload / review / report, admin overview / users / questions /
models / audit log, about-the-model, privacy, error pages. Illustrations are
original SVG artwork (soldiers on patrol, generic emblem): license-free and
not copying any real organisation's insignia.

## Phase 5 — Testing and documentation (2026-09-28)

37 automated tests (`tests/`), all passing:
- **Authentication:** registration, hashing, weak and duplicate rejection, wrong role tab, lockout, CSRF
- **RBAC:** every role reaches only its own pages; members cannot see each other's results
- **Prediction:** saving, disclaimer, high > low risk, validation, consent, configurable thresholds

The tests found and fixed one real security bug: a forged form with no CSRF
token was accepted from a visitor with no session.

Documentation: `README.md`, `docs/ML_MODEL.md`, `docs/ETHICS.md`, `docs/DEPLOYMENT.md`.
