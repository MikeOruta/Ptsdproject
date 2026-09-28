# PTSD Risk Assessment Portal

A web-based PTSD risk prediction system for post-deployment military personnel,
using **Logistic Regression**. Final-year project, BBIT, Strathmore University
(Omwansu Mike Oruta, 165162).

> **Decision-support only, not a medical diagnosis.** The included model is
> trained on **synthetic** data (see [docs/ML_MODEL.md](docs/ML_MODEL.md)).

## Features

| Role | Can do |
|---|---|
| **Service member** | Register, give consent, complete the 10-question assessment, see Low / Moderate / High risk with the factors behind it, track risk over time |
| **Mental health professional** | Prioritised caseload (highest risk first), review assessments and history, write clinical notes, anonymous summary report |
| **Administrator** | Create staff accounts, activate/deactivate users, edit question wording, upload/activate model versions, view the audit log |

Security: hashed passwords, server-side role checks (RBAC), CSRF protection,
30-minute session timeout, lockout after 5 failed sign-ins, security headers,
parameterised SQL, and an audit log of every sign-in and record view.

## Stack

Python 3 · Flask · scikit-learn · SQLite · HTML/CSS/JS (Jinja2). No front-end
frameworks or external services, for low-resource environments.

## Run it on your computer (Windows PowerShell)

```powershell
cd $HOME\OneDrive\Desktop\ptsd-system
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # then set SECRET_KEY (and DEMO_PASSWORD for demo data)
.\venv\Scripts\python.exe db\init_db.py                  # create the 10 tables
.\venv\Scripts\python.exe -m ml.generate_synthetic_data  # create the synthetic dataset
.\venv\Scripts\python.exe -m ml.train_model              # train + register the model
.\venv\Scripts\python.exe -m db.seed_demo                # optional: fictional demo accounts
.\venv\Scripts\python.exe run.py                         # open http://127.0.0.1:5000
```

Create a real administrator (password typed privately):

```powershell
.\venv\Scripts\python.exe -m db.create_user --role administrator --email you@example.org --name "Your Name"
```

Run the tests (37 tests: authentication, RBAC, prediction):

```powershell
.\venv\Scripts\python.exe -m pytest
```

## Project structure

```
app/            Flask application
  routes/       auth, personnel, therapist (clinician), admin, main
  templates/    Jinja2 pages          static/  CSS, JS, SVG images
  security.py   RBAC decorators, CSRF, audit log, headers
  ml_service.py loads the model once; predicts and explains
ml/             features.py, generate_synthetic_data.py, train_model.py, metrics_v1.json
db/             schema.sql, init_db.py, create_user.py, seed_demo.py
data/           synthetic_ptsd_dataset.csv
tests/          pytest suite
docs/           DEVELOPMENT_LOG, ML_MODEL, ETHICS, DEPLOYMENT
```

## Documentation

- [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md): step-by-step build record
- [docs/ML_MODEL.md](docs/ML_MODEL.md): data, preprocessing, training and results
- [docs/ETHICS.md](docs/ETHICS.md): ethics, privacy and limitations
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): hosting on PythonAnywhere
