"""Administrator console: users, assessment questions, ML models, audit logs.

Least privilege: administrators manage the SYSTEM but cannot open anyone's
assessment answers - only clinicians can.
"""
import json
import re
import sqlite3
from pathlib import Path

import joblib
from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)
from werkzeug.security import generate_password_hash

from app.db import get_db
from app.ml_service import PROJECT_ROOT, model_service
from app.security import ROLES, log_action, role_required
from app.validation import clean_text, validate_email, validate_password
from ml.features import FEATURES

bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_only = role_required("administrator")

UPLOAD_DIR = PROJECT_ROOT / "ml" / "uploads"
VERSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,30}$")
# A valid made-up answer set used to test an uploaded model before accepting it.
SAMPLE_INPUT = {"age": 30, "gender": "male", "deployment_duration_months": 9,
                "combat_exposure": 5, "prior_trauma": 0, "social_isolation": 4,
                "sleep_score": 5, "anxiety_score": 8, "depression_score": 8, "alcohol_use": 6}


@bp.route("/")
@admin_only
def dashboard():
    db = get_db()
    users_by_role = {r["role"]: r["n"] for r in db.execute(
        "SELECT role, COUNT(*) AS n FROM users GROUP BY role")}
    stats = {
        "assessments": db.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
        "today": db.execute(
            "SELECT COUNT(*) FROM assessments WHERE date(created_at) = date('now')").fetchone()[0],
        "failed_logins": db.execute(
            """SELECT COUNT(*) FROM system_logs WHERE action = 'login_failed'
               AND created_at >= datetime('now', '-1 day')""").fetchone()[0],
    }
    model = db.execute("SELECT * FROM ml_models WHERE is_active = 1").fetchone()
    metrics = json.loads(model["metrics_json"]) if model and model["metrics_json"] else None
    recent = db.execute(
        """SELECT l.*, u.email FROM system_logs l LEFT JOIN users u USING (user_id)
           ORDER BY l.log_id DESC LIMIT 8""").fetchall()
    return render_template("admin/dashboard.html", users_by_role=users_by_role, stats=stats,
                           model=model, metrics=metrics, model_loaded=model_service.ready,
                           model_error=model_service.error, recent=recent)


# ------------------------------------------------------------ users
@bp.route("/users", methods=["GET", "POST"])
@admin_only
def users():
    db = get_db()
    if request.method == "POST":   # create a clinician or administrator account
        full_name = clean_text(request.form.get("full_name"), 150)
        email = clean_text(request.form.get("email"), 255).lower()
        role = request.form.get("role")
        password = request.form.get("password", "")
        errors = [e for e in (validate_email(email), validate_password(password)) if e]
        if len(full_name) < 3:
            errors.append("Enter the person's full name.")
        if role not in ("therapist", "administrator"):
            errors.append("Choose a staff role.")
        if not errors:
            try:
                with db:
                    cur = db.execute(
                        "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                        (email, generate_password_hash(password), full_name, role))
                    if role == "therapist":
                        db.execute(
                            "INSERT INTO therapists (user_id, license_number, specialization) VALUES (?, ?, ?)",
                            (cur.lastrowid, clean_text(request.form.get("license_number"), 100) or None,
                             clean_text(request.form.get("specialization"), 150) or None))
                    else:
                        db.execute("INSERT INTO admins (user_id) VALUES (?)", (cur.lastrowid,))
            except sqlite3.IntegrityError:
                errors.append("An account with this email already exists.")
            else:
                log_action("user_created", f"{email} role={role}")
                flash(f"Account created for {full_name}. Share the temporary password securely.", "success")
                return redirect(url_for("admin.users"))
        for e in errors:
            flash(e, "error")

    role = request.args.get("role", "")
    sql = "SELECT * FROM users"
    params = []
    if role in ROLES:
        sql += " WHERE role = ?"
        params.append(role)
    rows = db.execute(sql + " ORDER BY created_at DESC", params).fetchall()
    return render_template("admin/users.html", users=rows, role=role)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_only
def toggle_user(user_id):
    if user_id == g.user["user_id"]:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.users"))
    db = get_db()
    user = db.execute("SELECT email, is_active FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)
    db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (0 if user["is_active"] else 1, user_id))
    db.commit()
    action = "user_deactivated" if user["is_active"] else "user_activated"
    log_action(action, user["email"])
    flash(f"{user['email']} {'deactivated' if user['is_active'] else 'reactivated'}.", "success")
    return redirect(url_for("admin.users"))


# ------------------------------------------------------------ questions
@bp.route("/questions", methods=["GET", "POST"])
@admin_only
def questions():
    """Edit the wording and order of questions. Ranges are fixed because the
    model was trained on them; changing them would make predictions invalid."""
    db = get_db()
    if request.method == "POST":
        qid = request.form.get("question_id", type=int)
        text = clean_text(request.form.get("question_text"), 500)
        help_text = clean_text(request.form.get("help_text"), 500) or None
        order = request.form.get("display_order", type=int)
        if not text or order is None:
            flash("Question text and order are required.", "error")
        else:
            db.execute(
                """UPDATE assessment_questions SET question_text = ?, help_text = ?, display_order = ?
                   WHERE question_id = ?""", (text, help_text, order, qid))
            db.commit()
            log_action("question_updated", f"question_id={qid}")
            flash("Question updated.", "success")
        return redirect(url_for("admin.questions"))
    rows = db.execute("SELECT * FROM assessment_questions ORDER BY display_order").fetchall()
    return render_template("admin/questions.html", questions=rows)


# ------------------------------------------------------------ models
@bp.route("/models")
@admin_only
def models():
    rows = get_db().execute("SELECT * FROM ml_models ORDER BY created_at DESC").fetchall()
    parsed = [(m, json.loads(m["metrics_json"]) if m["metrics_json"] else None) for m in rows]
    return render_template("admin/models.html", models=parsed, model_error=model_service.error)


@bp.route("/models/upload", methods=["POST"])
@admin_only
def upload_model():
    """Upload a retrained model (.pkl). SECURITY: loading a .pkl file can run
    code, so only trusted administrators may upload, and only files produced by
    ml/train_model.py should ever be uploaded. The model is tested before it is
    accepted, and is stored INACTIVE until an administrator activates it."""
    version = clean_text(request.form.get("version"), 30)
    file = request.files.get("model_file")
    if not VERSION_RE.match(version):
        flash("Version may only use letters, numbers, dots, dashes and underscores.", "error")
        return redirect(url_for("admin.models"))
    if file is None or not file.filename.lower().endswith(".pkl"):
        flash("Choose a .pkl model file produced by ml/train_model.py.", "error")
        return redirect(url_for("admin.models"))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"model_{version}.pkl"
    file.save(path)
    try:
        pipeline = joblib.load(path)
        import pandas as pd
        probability = pipeline.predict_proba(pd.DataFrame([SAMPLE_INPUT])[FEATURES])[0, 1]
        assert 0.0 <= probability <= 1.0
    except Exception as e:
        path.unlink(missing_ok=True)
        current_app.logger.warning("Rejected model upload: %s", e)
        flash("That file is not a valid PTSD model for this system. It was rejected.", "error")
        return redirect(url_for("admin.models"))

    try:
        db = get_db()
        db.execute(
            "INSERT INTO ml_models (version, file_path, metrics_json, is_active, uploaded_by) VALUES (?, ?, ?, 0, ?)",
            (version, path.relative_to(PROJECT_ROOT).as_posix(),
             json.dumps({"note": "Uploaded by administrator; metrics not supplied."}),
             g.user["user_id"]))
        db.commit()
    except sqlite3.IntegrityError:
        path.unlink(missing_ok=True)
        flash("A model with that version already exists.", "error")
        return redirect(url_for("admin.models"))
    log_action("model_uploaded", f"version={version}")
    flash(f"Model {version} uploaded and tested. Activate it when ready.", "success")
    return redirect(url_for("admin.models"))


@bp.route("/models/<int:model_id>/activate", methods=["POST"])
@admin_only
def activate_model(model_id):
    db = get_db()
    model = db.execute("SELECT version, file_path FROM ml_models WHERE model_id = ?", (model_id,)).fetchone()
    if model is None:
        abort(404)
    if not (PROJECT_ROOT / model["file_path"]).exists():
        flash(f"Model file {model['file_path']} is missing on the server.", "error")
        return redirect(url_for("admin.models"))
    with db:
        db.execute("UPDATE ml_models SET is_active = 0")
        db.execute("UPDATE ml_models SET is_active = 1 WHERE model_id = ?", (model_id,))
    model_service.load_active(current_app.config["DB_PATH"])   # switch immediately
    log_action("model_activated", f"version={model['version']}")
    flash(f"Model {model['version']} is now active.", "success")
    return redirect(url_for("admin.models"))


# ------------------------------------------------------------ logs
@bp.route("/logs")
@admin_only
def logs():
    action = request.args.get("action", "")
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 50
    sql = "SELECT l.*, u.email, u.role FROM system_logs l LEFT JOIN users u USING (user_id)"
    params = []
    if action:
        sql += " WHERE l.action = ?"
        params.append(action)
    sql += " ORDER BY l.log_id DESC LIMIT ? OFFSET ?"
    params += [per_page + 1, (page - 1) * per_page]
    rows = get_db().execute(sql, params).fetchall()
    actions = [r["action"] for r in get_db().execute(
        "SELECT DISTINCT action FROM system_logs ORDER BY action")]
    return render_template("admin/logs.html", logs=rows[:per_page], has_next=len(rows) > per_page,
                           page=page, action=action, actions=actions)
