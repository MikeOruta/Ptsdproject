"""Pages for mental health professionals: caseload dashboard, assessment
review with notes, and an anonymous summary report.

Every time a professional opens someone's assessment it is written to the
audit log, so access to sensitive mental health data is traceable.
"""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.db import get_db
from app.ml_service import model_service
from app.security import log_action, role_required
from app.validation import clean_text

bp = Blueprint("therapist", __name__, url_prefix="/clinician")
clinician_only = role_required("therapist")

CATEGORIES = ("High", "Moderate", "Low")


@bp.route("/")
@clinician_only
def dashboard():
    """Each service member's MOST RECENT assessment, highest risk first."""
    risk = request.args.get("risk", "")
    search = request.args.get("q", "").strip()[:100]

    sql = """
        SELECT u.full_name, m.service_number, m.military_rank, m.branch,
               a.assessment_id, a.created_at, r.probability, r.risk_category,
               (SELECT COUNT(*) FROM assessments x WHERE x.user_id = u.user_id) AS n_assessments,
               (SELECT COUNT(*) FROM therapist_notes n WHERE n.assessment_id = a.assessment_id) AS n_notes
        FROM users u
        JOIN military_personnel m ON m.user_id = u.user_id
        JOIN assessments a ON a.assessment_id = (
             SELECT assessment_id FROM assessments WHERE user_id = u.user_id
             ORDER BY created_at DESC, assessment_id DESC LIMIT 1)
        JOIN prediction_results r ON r.assessment_id = a.assessment_id
        WHERE 1 = 1"""
    params = []
    if risk in CATEGORIES:
        sql += " AND r.risk_category = ?"
        params.append(risk)
    if search:
        sql += " AND (u.full_name LIKE ? OR m.service_number LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY r.probability DESC"
    caseload = get_db().execute(sql, params).fetchall()

    counts = {c: 0 for c in CATEGORIES}
    for row in get_db().execute(
            """SELECT r.risk_category, COUNT(*) AS n FROM prediction_results r
               JOIN assessments a USING (assessment_id)
               WHERE a.assessment_id IN (SELECT MAX(assessment_id) FROM assessments GROUP BY user_id)
               GROUP BY r.risk_category"""):
        counts[row["risk_category"]] = row["n"]
    return render_template("therapist/dashboard.html", caseload=caseload, counts=counts,
                           risk=risk, search=search)


@bp.route("/assessment/<int:assessment_id>", methods=["GET", "POST"])
@clinician_only
def assessment(assessment_id):
    db = get_db()
    a = db.execute(
        """SELECT a.*, r.probability, r.risk_category, r.model_id,
                  u.full_name, u.email, m.service_number, m.military_rank, m.branch
           FROM assessments a
           JOIN prediction_results r USING (assessment_id)
           JOIN users u ON u.user_id = a.user_id
           JOIN military_personnel m ON m.user_id = a.user_id
           WHERE a.assessment_id = ?""", (assessment_id,)).fetchone()
    if a is None:
        abort(404)
    therapist = db.execute("SELECT therapist_id FROM therapists WHERE user_id = ?",
                           (g.user["user_id"],)).fetchone()

    if request.method == "POST":
        note = clean_text(request.form.get("note"), 5000)
        if not note:
            flash("The note cannot be empty.", "error")
        elif therapist is None:
            flash("Your account has no clinician profile. Contact an administrator.", "error")
        else:
            db.execute("INSERT INTO therapist_notes (assessment_id, therapist_id, note) VALUES (?, ?, ?)",
                       (assessment_id, therapist["therapist_id"], note))
            db.commit()
            log_action("note_added", f"assessment_id={assessment_id}")
            flash("Note saved.", "success")
            return redirect(url_for("therapist.assessment", assessment_id=assessment_id))
    else:
        log_action("assessment_viewed", f"assessment_id={assessment_id}")

    notes = db.execute(
        """SELECT n.note, n.created_at, u.full_name FROM therapist_notes n
           JOIN therapists t USING (therapist_id) JOIN users u ON u.user_id = t.user_id
           WHERE n.assessment_id = ? ORDER BY n.created_at DESC""", (assessment_id,)).fetchall()
    history = db.execute(
        """SELECT a.assessment_id, a.created_at, r.probability, r.risk_category
           FROM assessments a JOIN prediction_results r USING (assessment_id)
           WHERE a.user_id = ? ORDER BY a.created_at DESC, a.assessment_id DESC""",
        (a["user_id"],)).fetchall()
    raising, lowering = [], []
    if model_service.ready and a["model_id"] == model_service.model_id:
        raising, lowering = model_service.explain(dict(a))
    return render_template("therapist/assessment.html", a=a, notes=notes, history=history,
                           raising=raising, lowering=lowering)


@bp.route("/report")
@clinician_only
def report():
    """Aggregate statistics only - no names - suitable for sharing with management."""
    db = get_db()
    by_month = db.execute(
        """SELECT strftime('%Y-%m', a.created_at) AS month, COUNT(*) AS total,
                  SUM(r.risk_category = 'High') AS high,
                  SUM(r.risk_category = 'Moderate') AS moderate,
                  SUM(r.risk_category = 'Low') AS low
           FROM assessments a JOIN prediction_results r USING (assessment_id)
           GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
    totals = db.execute(
        """SELECT COUNT(*) AS assessments, COUNT(DISTINCT user_id) AS people,
                  AVG(r.probability) AS avg_probability
           FROM assessments a JOIN prediction_results r USING (assessment_id)""").fetchone()
    log_action("report_viewed")
    return render_template("therapist/report.html", by_month=by_month, totals=totals)
