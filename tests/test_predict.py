"""The prediction flow: validation, saving, risk categories, disclaimer, model."""
import sqlite3

from app.ml_service import model_service
from tests.conftest import VALID_ASSESSMENT, login

LOW_RISK = {**VALID_ASSESSMENT, "age": "45", "deployment_duration_months": "2", "combat_exposure": "0",
            "prior_trauma": "0", "social_isolation": "0", "sleep_score": "0", "anxiety_score": "0",
            "depression_score": "0", "alcohol_use": "0"}


def member(client, make_user):
    make_user("m@example.org", "military_personnel")
    login(client, "m@example.org", "military_personnel")


def test_assessment_saves_assessment_and_result(client, app, make_user):
    member(client, make_user)
    r = client.post("/personnel/assessment", data=VALID_ASSESSMENT)
    assert r.status_code == 302 and "/personnel/result/" in r.headers["Location"]
    conn = sqlite3.connect(app.config["DB_PATH"])
    prob, cat = conn.execute("SELECT probability, risk_category FROM prediction_results").fetchone()
    assert 0 <= prob <= 1 and cat in ("Low", "Moderate", "High")
    assert conn.execute("SELECT COUNT(*) FROM system_logs WHERE action = 'assessment_submitted'").fetchone()[0] == 1


def test_result_page_shows_disclaimer(client, make_user):
    member(client, make_user)
    location = client.post("/personnel/assessment", data=VALID_ASSESSMENT).headers["Location"]
    assert b"Decision-support only, not a medical diagnosis." in client.get(location).data


def test_high_risk_answers_score_higher_than_low_risk(client, app, make_user):
    member(client, make_user)
    client.post("/personnel/assessment", data=VALID_ASSESSMENT)
    client.post("/personnel/assessment", data=LOW_RISK)
    rows = sqlite3.connect(app.config["DB_PATH"]).execute(
        "SELECT probability, risk_category FROM prediction_results ORDER BY result_id").fetchall()
    assert rows[0][0] > rows[1][0]
    assert rows[0][1] == "High" and rows[1][1] == "Low"


def test_out_of_range_value_is_rejected(client, app, make_user):
    member(client, make_user)
    r = client.post("/personnel/assessment", data={**VALID_ASSESSMENT, "anxiety_score": "35"})
    assert r.status_code == 400 and b"between 0 and 21" in r.data
    assert sqlite3.connect(app.config["DB_PATH"]).execute("SELECT COUNT(*) FROM assessments").fetchone()[0] == 0


def test_consent_is_required(client, make_user):
    member(client, make_user)
    data = {k: v for k, v in VALID_ASSESSMENT.items() if k != "consent"}
    assert client.post("/personnel/assessment", data=data).status_code == 400


def test_risk_thresholds_are_configurable(client, app, make_user):
    app.config["RISK_HIGH"] = 0.999          # make "High" almost impossible
    member(client, make_user)
    client.post("/personnel/assessment", data=VALID_ASSESSMENT)
    cat = sqlite3.connect(app.config["DB_PATH"]).execute("SELECT risk_category FROM prediction_results").fetchone()[0]
    assert cat == "Moderate"


def test_model_is_loaded_once_at_startup(app):
    assert model_service.ready and model_service.version == "test"


def test_explanation_lists_factors(app):
    values = {"age": 29, "gender": "male", "deployment_duration_months": 12, "combat_exposure": 8,
              "prior_trauma": 1, "social_isolation": 7, "sleep_score": 8, "anxiety_score": 15,
              "depression_score": 18, "alcohol_use": 14}
    raising, _ = model_service.explain(values)
    assert raising and all(f["contribution"] > 0 for f in raising)
