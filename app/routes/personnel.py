"""Pages for service members: dashboard, assessment form, result, history."""
from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)

from app.db import get_db
from app.ml_service import model_service
from app.security import log_action, role_required
from app.validation import validate_assessment
from ml.features import NUMERIC_FEATURES

bp = Blueprint("personnel", __name__, url_prefix="/personnel")
member_only = role_required("military_personnel")


def risk_category(probability):
    """Low / Moderate / High using the thresholds configured for this deployment."""
    if probability >= current_app.config["RISK_HIGH"]:
        return "High"
    if probability >= current_app.config["RISK_MODERATE"]:
        return "Moderate"
    return "Low"


def my_history(user_id):
    return get_db().execute(
        """SELECT a.assessment_id, a.created_at, r.probability, r.risk_category
           FROM assessments a JOIN prediction_results r USING (assessment_id)
           WHERE a.user_id = ? ORDER BY a.created_at, a.assessment_id""",
        (user_id,),
    ).fetchall()


def trend_points(history, width=600, height=160, pad=20):
    """x,y points for a simple SVG line chart of risk over time (drawn in the template)."""
    if not history:
        return []
    step = (width - 2 * pad) / max(len(history) - 1, 1)
    return [{"x": round(pad + i * step, 1),
             "y": round(height - pad - row["probability"] * (height - 2 * pad), 1),
             "row": row} for i, row in enumerate(history)]


@bp.route("/")
@member_only
def dashboard():
    history = my_history(g.user["user_id"])
    return render_template("personnel/dashboard.html", history=history,
                           latest=history[-1] if history else None,
                           points=trend_points(history))


@bp.route("/assessment", methods=["GET", "POST"])
@member_only
def assessment():
    questions = get_db().execute(
        "SELECT * FROM assessment_questions ORDER BY display_order").fetchall()
    values, errors = {}, {}

    if request.method == "POST":
        values, errors = validate_assessment(request.form)
        if errors:
            flash("Please correct the highlighted answers.", "error")
        elif not model_service.ready:
            current_app.logger.error("Prediction attempted without a model: %s", model_service.error)
            flash("The prediction service is temporarily unavailable. Please try later.", "error")
            return render_template("personnel/assessment.html", questions=questions,
                                   values=values, errors=errors, ranges=NUMERIC_FEATURES), 503
        else:
            probability = model_service.predict_probability(values)
            category = risk_category(probability)
            db = get_db()
            with db:  # the assessment and its result are saved together, or not at all
                cur = db.execute(
                    """INSERT INTO assessments (user_id, age, gender, deployment_duration_months,
                         combat_exposure, prior_trauma, social_isolation, sleep_score,
                         anxiety_score, depression_score, alcohol_use, pcl5_score,
                         other_factors, consent_given)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (g.user["user_id"], values["age"], values["gender"],
                     values["deployment_duration_months"], values["combat_exposure"],
                     values["prior_trauma"], values["social_isolation"], values["sleep_score"],
                     values["anxiety_score"], values["depression_score"], values["alcohol_use"],
                     values["pcl5_score"], values["other_factors"]))
                assessment_id = cur.lastrowid
                db.execute(
                    """INSERT INTO prediction_results (assessment_id, model_id, probability, risk_category)
                       VALUES (?, ?, ?, ?)""",
                    (assessment_id, model_service.model_id, probability, category))
            log_action("assessment_submitted", f"assessment_id={assessment_id} risk={category}")
            return redirect(url_for("personnel.result", assessment_id=assessment_id))

    return render_template("personnel/assessment.html", questions=questions, values=values,
                           errors=errors, ranges=NUMERIC_FEATURES), 400 if errors else 200


@bp.route("/result/<int:assessment_id>")
@member_only
def result(assessment_id):
    row = get_db().execute(
        """SELECT a.*, r.probability, r.risk_category, r.model_id
           FROM assessments a JOIN prediction_results r USING (assessment_id)
           WHERE a.assessment_id = ?""", (assessment_id,)).fetchone()
    # Members may only see their own results. 404 (not 403) so the ID's existence isn't revealed.
    if row is None or row["user_id"] != g.user["user_id"]:
        abort(404)
    raising, lowering = [], []
    if model_service.ready and row["model_id"] == model_service.model_id:
        raising, lowering = model_service.explain(dict(row))
    return render_template("personnel/result.html", a=row, raising=raising, lowering=lowering)


@bp.route("/history")
@member_only
def history():
    rows = my_history(g.user["user_id"])
    return render_template("personnel/history.html", history=list(reversed(rows)),
                           points=trend_points(rows))
