"""Public pages: home, about the model, privacy notice."""
import json

from flask import Blueprint, g, redirect, render_template, url_for

from app.db import get_db
from app.ml_service import model_service
from app.security import ROLE_HOME

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if g.user is not None:
        return redirect(url_for(ROLE_HOME[g.user["role"]]))
    return render_template("index.html")


@bp.route("/about")
def about():
    """How the model works and how well it performs - transparency for users."""
    metrics = None
    if model_service.ready:
        row = get_db().execute(
            "SELECT metrics_json FROM ml_models WHERE model_id = ?", (model_service.model_id,)
        ).fetchone()
        metrics = json.loads(row["metrics_json"]) if row and row["metrics_json"] else None
    return render_template("about.html", metrics=metrics, version=model_service.version)


@bp.route("/privacy")
def privacy():
    return render_template("privacy.html")
