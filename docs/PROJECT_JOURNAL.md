# PTSD Risk Prediction System - Project Journal

This document records the work completed from the start of the project to the current point, and it will be updated as the project continues until completion.

## 1. Project kickoff

- The project began as a final-year web application idea: a PTSD risk prediction system for post-deployment military personnel.
- The system was planned around a lightweight, low-resource design using Python, Flask, SQLite, scikit-learn, HTML/CSS/JS and Jinja2 templates.
- The original requirement set emphasized a simple, explainable model and a confidential working environment.
- The project was organised around a practical structure with folders for the app, database, ML code, tests and documentation.

## 2. Initial setup and project structure

- A fresh project structure was created with the main application folders and supporting directories.
- The database was moved to SQLite instead of MySQL so the system could remain lightweight and self-contained.
- The database was created under `db/ptsd_system.db` and managed using a schema script instead of a server-dependent database service.
- A `.env` file was set up to hold secrets and configuration values, while `.env.example` was kept as a template for safe setup.
- The app uses environment variables for the app secret key, database path, risk thresholds and support settings.

## 3. Core application setup

- A Flask application factory was created to build the app and configure settings cleanly.
- The project uses `create_app()` so the app can be created in a predictable way for local development and testing.
- The project includes a development server entry point via `run.py`.
- Security settings were configured for sessions, cookies and HTTP headers.
- A role-based access system was built around user roles: service member, mental health professional and administrator.

## 4. Database design and schema

- The SQLite schema was created from scratch to match the project requirements.
- The system includes 10 core tables, including:
  - `users`
  - `military_personnel`
  - `therapists`
  - `admins`
  - `system_logs`
  - `assessments`
  - `prediction_results`
  - `therapist_notes`
  - `assessment_questions`
  - `ml_models`
- The database uses foreign keys and a strict schema to preserve data integrity.
- The `users` table stores role information and login details.
- Profile tables keep user-specific information separate from the login record.
- The schema includes the required assessment fields and risk logic support.

## 5. User accounts and role logic

- Registration and login were implemented with hashed passwords using Werkzeug.
- The system validates email format, password strength and account uniqueness.
- Service members can self-register.
- Mental health professionals are handled separately from the public registration page to prevent unrestricted access.
- Administrators are treated as privileged staff accounts and are not meant to be publicly self-registered.
- Role-based access control (RBAC) is enforced on server routes so a user cannot skip to another role’s pages by URL manipulation.

## 6. Authentication and login flow

- The login page was designed to support the user journey, while keeping the administrator role out of the public registration flow.
- The app checks the requested role against the real stored role before logging in.
- Failed login attempts are tracked in the audit log.
- Sessions are cleared on each new login to prevent session fixation.
- The system logs key actions such as login, logout, access denial and user creation.

## 7. Front-end interface

- The homepage was created to present the system clearly and professionally.
- The sign-in flow was refined to match the public-facing flow of the project.
- The public registration flow keeps the service-member experience clear and simple.
- A separate clinical registration path was added for mental health professionals, with professional-specific details such as licence or registration number and specialization.
- The administrator path remains hidden from public self-registration and is intended for direct staff login and administration.

## 8. ML model and data generation work

- The project includes a synthetic dataset generator used to simulate realistic PTSD risk data.
- The synthetic data includes deployment, trauma, sleep, anxiety, depression, alcohol use and social isolation factors.
- The model is trained using a logistic regression pipeline with preprocessing and scaling.
- The design follows the project requirement to avoid data leakage and to report balanced classification metrics instead of using accuracy alone.
- The model is saved and registered in the application’s model table.
- A metrics file is used to record the model’s performance values.

## 9. Current project status

At this point, the project has reached the stage where:

- the app is running locally,
- the SQLite database is created and populated with the required tables,
- the Flask app boots successfully,
- the homepage and auth pages load,
- the role split is in place,
- the user registration flow includes both service member and mental health professional paths,
- the administrator remains direct-access and not public-facing.

## 10. Work still remaining

The remaining work will continue through the project phases and will include:

- completing the full service-member assessment flow,
- integrating prediction results with the trained model,
- adding clinician dashboard features and notes,
- finalising the admin management pages,
- expanding the audit trail and role enforcement,
- adding final validation and tests,
- polishing the README and ethics documentation,
- verifying the project is stable and defendable for final review.

## 11. Final project goal

The final goal is to deliver a complete, working PTSD risk assessment system that is secure, explainable, low-resource, and suitable for final-year project review. The design will remain simple enough to explain clearly while still covering the required functionality, security, and ethical considerations.
