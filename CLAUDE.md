# CLAUDE.md — project brief (the master prompt for this project)

## Project notes (added during setup)
- Project folder: Desktop\ptsd-system (OneDrive-synced Desktop). GitHub: MikeOruta/Ptsdproject.
- Started afresh: the earlier sample CSV / train_model.py / data_schema_unified.sql were
  not available, so the schema is written from scratch in db/schema.sql and the dataset
  is generated synthetically in Phase 2.
- DATABASE DECISION: switched from MySQL to SQLite (built into Python, no server,
  one file at db/ptsd_system.db). Reason: the "lightweight and low-resource" design
  goal. This overrides every mention of MySQL in the master prompt below. Create or
  reset the database with `python db/init_db.py`. Run `PRAGMA foreign_keys = ON` on
  every connection.

## Master prompt

I'm building my final-year project: a web-based PTSD risk prediction system for
post-deployment military personnel, using Logistic Regression (Strathmore University,
BBIT). I'm on Windows, so use PowerShell-compatible commands. I must be able to explain
and defend every part of this code, so briefly explain each step as you go, keep the
code simple and commented, and stop at the end of each phase for my review.

STACK: Python 3, Flask, scikit-learn, SQLite (originally MySQL), HTML/CSS/JS with Jinja2 templates.
No heavy frameworks. Design goal is lightweight and low-resource.

STEP 0 - HOUSEKEEPING (do first)
1. Save this whole message as CLAUDE.md in the project root.
2. Create this structure: app/ (routes, models, templates, static), ml/, data/, db/,
   docs/, tests/. Move the CSV to data/, train_model.py to ml/, the .sql to db/.
3. git init, create .gitignore (venv/, __pycache__/, *.pyc, .env, *.log), first commit.
4. Create a venv and requirements.txt (flask, mysql-connector-python, scikit-learn,
   pandas, joblib, python-dotenv, pytest).
5. Check `mysql --version`. If MySQL isn't installed, STOP and tell me how to install
   it (XAMPP or MySQL Installer). Don't continue until I confirm.
6. Store DB credentials in .env (never commit it) and provide .env.example.

DATABASE (10 tables)
users (role: military_personnel / therapist / administrator), military_personnel,
therapists, admins (1:1 profile tables, user_id UNIQUE), system_logs, assessments,
prediction_results (1:1 with assessments), therapist_notes, assessment_questions,
ml_models. Run the script to create database ptsd_system and verify all tables exist.
(Schema: db/schema.sql, SQLite syntax.)

KNOWN ISSUES - resolve these BEFORE Phase 2
A. The assessments table must also hold age, gender, deployment_duration_months,
   combat_exposure, prior_trauma and social_isolation (not only pcl5/anxiety/
   depression/sleep/alcohol/other_factors).
B. DATA LEAKAGE: if PCL-5 is used as the outcome, it must NOT also be a predictor.
   Never present metrics from a label derived from the features as real performance.
C. CLASS IMBALANCE: use stratified splits, class_weight='balanced', and report
   precision, recall, F1 and the confusion matrix, not accuracy alone.

PHASES (commit after each; stop for my review)
Phase 1 - Skeleton + database running, Flask "hello" route, app connects to MySQL.
Phase 2 - ML: build a clearly-labelled SYNTHETIC dataset generator matching the input
  features (age, gender, deployment duration, combat exposure, sleep, anxiety,
  depression, alcohol use, prior trauma, social isolation) with documented,
  literature-style relationships plus noise. Then train Logistic Regression with
  preprocessing (cleaning, imputation, encoding, scaling, feature selection),
  stratified train/test + cross-validation, save ml/model_v1.pkl and scaler, write
  metrics to a JSON file, and register the model in ml_models (is_active=true).
  State in comments and docs that the data is synthetic (a documented limitation).
Phase 3 - Backend: register/login with hashed passwords (werkzeug), sessions, a
  role-check decorator (RBAC), POST /predict (load model once at startup; save the
  assessment and result; risk category Low/Moderate/High from configurable
  probability thresholds), history, therapist notes, admin endpoints (users,
  questions, model upload, logs), and log key actions to system_logs.
Phase 4 - Frontend from my wireframes: shared Login (with role tabs; server-side
  role check) and Register, Assessment form, Risk Result page, MH Professional
  dashboard, Admin console, with a role badge in the nav bar.
Phase 5 - Tests (pytest for auth, RBAC, predict), README with run instructions, and
  a short docs/ETHICS.md.

RULES
- Parameterized SQL only (no string-built queries); validate all inputs.
- Never hard-code secrets; never commit .env.
- Every result page must show: "Decision-support only, not a medical diagnosis."
- Treat all data as sensitive; only public/synthetic data is used in this project.
- Ask before installing anything, deleting files, or pushing to a remote.
