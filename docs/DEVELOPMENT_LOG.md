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

**Next:** Phase 2 — synthetic dataset and Logistic Regression model.
