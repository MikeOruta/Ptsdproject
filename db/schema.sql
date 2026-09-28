-- =====================================================================
-- PTSD Risk Prediction System - database schema (MySQL / MariaDB)
-- Creates database ptsd_system with 10 tables.
-- Run:  mysql -u root -p < db/schema.sql
-- Re-running is safe: tables are dropped and recreated (DEV ONLY - wipes data).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS ptsd_system
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ptsd_system;

-- Drop in reverse dependency order so foreign keys don't block us.
DROP TABLE IF EXISTS therapist_notes, prediction_results, assessments,
  system_logs, admins, therapists, military_personnel, assessment_questions,
  ml_models, users;

-- 1. users: one row per login account. The role decides what they can do (RBAC).
CREATE TABLE users (
  user_id        INT AUTO_INCREMENT PRIMARY KEY,
  email          VARCHAR(255) NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,          -- werkzeug hash, never plain text
  full_name      VARCHAR(150) NOT NULL,
  role           ENUM('military_personnel','therapist','administrator') NOT NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login     TIMESTAMP NULL
) ENGINE=InnoDB;

-- 2-4. Profile tables: 1:1 with users (user_id UNIQUE enforces "one profile per user").
CREATE TABLE military_personnel (
  personnel_id   INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL UNIQUE,
  service_number VARCHAR(50) UNIQUE,
  branch         VARCHAR(100),
  military_rank  VARCHAR(100),                   -- "rank" is a reserved word in MySQL 8
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE therapists (
  therapist_id   INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL UNIQUE,
  license_number VARCHAR(100),
  specialization VARCHAR(150),
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE admins (
  admin_id       INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL UNIQUE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. system_logs: audit trail of key actions (login, predict, admin changes).
CREATE TABLE system_logs (
  log_id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NULL,                       -- NULL for anonymous events (failed login)
  action         VARCHAR(100) NOT NULL,
  details        TEXT,
  ip_address     VARCHAR(45),                    -- 45 chars fits IPv6
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 6. ml_models: every trained model version; exactly one should be is_active.
CREATE TABLE ml_models (
  model_id       INT AUTO_INCREMENT PRIMARY KEY,
  version        VARCHAR(50) NOT NULL UNIQUE,
  algorithm      VARCHAR(100) NOT NULL DEFAULT 'LogisticRegression',
  file_path      VARCHAR(255) NOT NULL,
  metrics_json   TEXT,                           -- precision/recall/F1/confusion matrix
  is_active      BOOLEAN NOT NULL DEFAULT FALSE,
  uploaded_by    INT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (uploaded_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 7. assessments: the inputs a service member submits.
-- Known Issue A resolved: includes age, gender, deployment duration, combat
-- exposure, prior trauma and social isolation, which the form and model need.
-- Scales: 0-10 scores unless stated. pcl5_score is kept for clinical reference
-- only and is NOT a model feature (Known Issue B: it would leak the outcome).
CREATE TABLE assessments (
  assessment_id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id                    INT NOT NULL,
  age                        TINYINT UNSIGNED NOT NULL,
  gender                     ENUM('male','female','other') NOT NULL,
  deployment_duration_months SMALLINT UNSIGNED NOT NULL,
  combat_exposure            TINYINT UNSIGNED NOT NULL,   -- 0-10
  prior_trauma               BOOLEAN NOT NULL,
  social_isolation           TINYINT UNSIGNED NOT NULL,   -- 0-10
  sleep_score                TINYINT UNSIGNED NOT NULL,   -- 0-10, higher = worse sleep
  anxiety_score              TINYINT UNSIGNED NOT NULL,   -- 0-21 (GAD-7 range)
  depression_score           TINYINT UNSIGNED NOT NULL,   -- 0-27 (PHQ-9 range)
  alcohol_use                TINYINT UNSIGNED NOT NULL,   -- 0-40 (AUDIT range)
  pcl5_score                 TINYINT UNSIGNED NULL,       -- 0-80, optional, not a feature
  other_factors              TEXT,
  created_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 8. prediction_results: 1:1 with assessments (assessment_id UNIQUE).
CREATE TABLE prediction_results (
  result_id      INT AUTO_INCREMENT PRIMARY KEY,
  assessment_id  INT NOT NULL UNIQUE,
  model_id       INT NULL,                       -- which model version produced it
  probability    DECIMAL(5,4) NOT NULL,          -- 0.0000-1.0000
  risk_category  ENUM('Low','Moderate','High') NOT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
  FOREIGN KEY (model_id) REFERENCES ml_models(model_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 9. therapist_notes: a therapist's notes on an assessment.
CREATE TABLE therapist_notes (
  note_id        INT AUTO_INCREMENT PRIMARY KEY,
  assessment_id  INT NOT NULL,
  therapist_id   INT NOT NULL,
  note           TEXT NOT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE,
  FOREIGN KEY (therapist_id) REFERENCES therapists(therapist_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 10. assessment_questions: form questions the admin can manage.
CREATE TABLE assessment_questions (
  question_id    INT AUTO_INCREMENT PRIMARY KEY,
  field_name     VARCHAR(100) NOT NULL UNIQUE,   -- matches an assessments column
  question_text  VARCHAR(500) NOT NULL,
  min_value      INT,
  max_value      INT,
  display_order  INT NOT NULL DEFAULT 0,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;
