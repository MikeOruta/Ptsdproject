-- =====================================================================
-- PTSD Risk Prediction System - database schema (SQLite)
-- Creates the 10 tables. Run with:  python db/init_db.py
-- Re-running is safe: tables are dropped and recreated (DEV ONLY - wipes data).
--
-- SQLite notes (things that differ from MySQL):
--  * No ENUM type, so allowed values are enforced with CHECK constraints.
--  * No BOOLEAN type: we store 0/1 in INTEGER columns with CHECK (x IN (0,1)).
--  * INTEGER PRIMARY KEY AUTOINCREMENT = MySQL's INT AUTO_INCREMENT PRIMARY KEY.
--  * Foreign keys are only enforced when each connection runs
--    "PRAGMA foreign_keys = ON" (done in init_db.py and the app's db code).
-- =====================================================================

-- Drop child tables before parents so foreign keys don't block us.
DROP TABLE IF EXISTS therapist_notes;
DROP TABLE IF EXISTS prediction_results;
DROP TABLE IF EXISTS assessments;
DROP TABLE IF EXISTS system_logs;
DROP TABLE IF EXISTS admins;
DROP TABLE IF EXISTS therapists;
DROP TABLE IF EXISTS military_personnel;
DROP TABLE IF EXISTS assessment_questions;
DROP TABLE IF EXISTS ml_models;
DROP TABLE IF EXISTS users;

-- 1. users: one row per login account. The role decides what they can do (RBAC).
CREATE TABLE users (
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  email          TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,                  -- werkzeug hash, never plain text
  full_name      TEXT NOT NULL,
  role           TEXT NOT NULL
                 CHECK (role IN ('military_personnel','therapist','administrator')),
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login     TEXT
);

-- 2-4. Profile tables: 1:1 with users (user_id UNIQUE enforces "one profile per user").
CREATE TABLE military_personnel (
  personnel_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
  service_number TEXT UNIQUE,
  branch         TEXT,
  military_rank  TEXT
);

CREATE TABLE therapists (
  therapist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
  license_number TEXT,
  specialization TEXT
);

CREATE TABLE admins (
  admin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE
);

-- 5. system_logs: audit trail of key actions (login, predict, admin changes).
CREATE TABLE system_logs (
  log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER REFERENCES users(user_id) ON DELETE SET NULL, -- NULL = anonymous
  action         TEXT NOT NULL,
  details        TEXT,
  ip_address     TEXT,
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. ml_models: every trained model version; exactly one should be is_active.
CREATE TABLE ml_models (
  model_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  version        TEXT NOT NULL UNIQUE,
  algorithm      TEXT NOT NULL DEFAULT 'LogisticRegression',
  file_path      TEXT NOT NULL,
  metrics_json   TEXT,                           -- precision/recall/F1/confusion matrix
  is_active      INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0,1)),
  uploaded_by    INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. assessments: the inputs a service member submits.
-- Known Issue A resolved: includes age, gender, deployment duration, combat
-- exposure, prior trauma and social isolation, which the form and model need.
-- pcl5_score is kept for clinical reference only and is NOT a model feature
-- (Known Issue B: using it as both input and outcome would leak the answer).
CREATE TABLE assessments (
  assessment_id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id                    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  age                        INTEGER NOT NULL CHECK (age BETWEEN 18 AND 70),
  gender                     TEXT NOT NULL CHECK (gender IN ('male','female','other')),
  deployment_duration_months INTEGER NOT NULL CHECK (deployment_duration_months BETWEEN 0 AND 120),
  combat_exposure            INTEGER NOT NULL CHECK (combat_exposure BETWEEN 0 AND 10),
  prior_trauma               INTEGER NOT NULL CHECK (prior_trauma IN (0,1)),
  social_isolation           INTEGER NOT NULL CHECK (social_isolation BETWEEN 0 AND 10),
  sleep_score                INTEGER NOT NULL CHECK (sleep_score BETWEEN 0 AND 10),   -- higher = worse sleep
  anxiety_score              INTEGER NOT NULL CHECK (anxiety_score BETWEEN 0 AND 21), -- GAD-7 range
  depression_score           INTEGER NOT NULL CHECK (depression_score BETWEEN 0 AND 27), -- PHQ-9 range
  alcohol_use                INTEGER NOT NULL CHECK (alcohol_use BETWEEN 0 AND 40),   -- AUDIT range
  pcl5_score                 INTEGER CHECK (pcl5_score BETWEEN 0 AND 80),             -- optional, not a feature
  other_factors              TEXT,
  consent_given              INTEGER NOT NULL CHECK (consent_given = 1), -- informed consent (Proposal 3.13)
  created_at                 TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. prediction_results: 1:1 with assessments (assessment_id UNIQUE).
CREATE TABLE prediction_results (
  result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id  INTEGER NOT NULL UNIQUE REFERENCES assessments(assessment_id) ON DELETE CASCADE,
  model_id       INTEGER REFERENCES ml_models(model_id) ON DELETE SET NULL,
  probability    REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
  risk_category  TEXT NOT NULL CHECK (risk_category IN ('Low','Moderate','High')),
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. therapist_notes: a therapist's notes on an assessment.
CREATE TABLE therapist_notes (
  note_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id  INTEGER NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
  therapist_id   INTEGER NOT NULL REFERENCES therapists(therapist_id) ON DELETE CASCADE,
  note           TEXT NOT NULL,
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. assessment_questions: form questions the admin can manage.
CREATE TABLE assessment_questions (
  question_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  field_name     TEXT NOT NULL UNIQUE,           -- matches an assessments column
  question_text  TEXT NOT NULL,
  help_text      TEXT,
  min_value      INTEGER,
  max_value      INTEGER,
  display_order  INTEGER NOT NULL DEFAULT 0,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

-- Default wording for the assessment form (administrators can edit it).
-- Ranges must match ml/features.py; they are not editable to protect the model.
INSERT INTO assessment_questions (field_name, question_text, help_text, min_value, max_value, display_order) VALUES
 ('age', 'What is your age?', 'In years.', 18, 70, 1),
 ('gender', 'What is your gender?', NULL, NULL, NULL, 2),
 ('deployment_duration_months', 'How long was your most recent deployment?', 'In months.', 0, 120, 3),
 ('combat_exposure', 'How often were you exposed to combat or life-threatening situations during deployment?', '0 = never, 10 = constantly.', 0, 10, 4),
 ('prior_trauma', 'Before this deployment, had you experienced a traumatic event?', 'For example an assault, accident, disaster or earlier combat.', 0, 1, 5),
 ('social_isolation', 'How cut off do you feel from family, friends and colleagues?', '0 = well supported, 10 = completely isolated.', 0, 10, 6),
 ('sleep_score', 'How much trouble have you had sleeping in the past month?', 'Including nightmares and waking at night. 0 = none, 10 = severe.', 0, 10, 7),
 ('anxiety_score', 'Anxiety score (GAD-7)', 'Total from the 7-question GAD-7 anxiety questionnaire, 0 to 21.', 0, 21, 8),
 ('depression_score', 'Depression score (PHQ-9)', 'Total from the 9-question PHQ-9 depression questionnaire, 0 to 27.', 0, 27, 9),
 ('alcohol_use', 'Alcohol use score (AUDIT)', 'Total from the 10-question AUDIT alcohol questionnaire, 0 to 40.', 0, 40, 10);

CREATE INDEX idx_assessments_user ON assessments(user_id, created_at);
CREATE INDEX idx_logs_created ON system_logs(created_at);
