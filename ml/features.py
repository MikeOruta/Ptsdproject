"""Single source of truth for the model's input features (Proposal Objective 2).

The data generator, the training script and (later) the web form's input
validation all import from here, so the definitions can never drift apart.
"""

# Numeric features and their valid ranges (min, max). Values outside these
# ranges are treated as data-entry errors during cleaning.
NUMERIC_FEATURES = {
    "age":                        (18, 70),   # years
    "deployment_duration_months": (0, 120),   # length of most recent deployment
    "combat_exposure":            (0, 10),    # frequency of combat exposure, 0 = none, 10 = constant
    "prior_trauma":               (0, 1),     # 1 = trauma before deployment, 0 = none
    "social_isolation":           (0, 10),    # 0 = well supported, 10 = fully isolated
    "sleep_score":                (0, 10),    # sleep disturbance, higher = worse sleep
    "anxiety_score":              (0, 21),    # GAD-7 questionnaire range
    "depression_score":           (0, 27),    # PHQ-9 questionnaire range
    "alcohol_use":                (0, 40),    # AUDIT questionnaire range
}

# Categorical features and their allowed values. The first value is the
# reference (baseline) category when the feature is one-hot encoded.
CATEGORICAL_FEATURES = {
    "gender": ["male", "female", "other"],
}

FEATURES = list(NUMERIC_FEATURES) + list(CATEGORICAL_FEATURES)

# Plain-English names shown to users when explaining a prediction.
FEATURE_LABELS = {
    "age": "Age",
    "deployment_duration_months": "Deployment length",
    "combat_exposure": "Combat exposure",
    "prior_trauma": "Prior trauma",
    "social_isolation": "Social isolation",
    "sleep_score": "Sleep disturbance",
    "anxiety_score": "Anxiety (GAD-7)",
    "depression_score": "Depression (PHQ-9)",
    "alcohol_use": "Alcohol use (AUDIT)",
    "gender_female": "Gender (female)",
    "gender_other": "Gender (other)",
}
TARGET = "probable_ptsd"  # 1 = probable PTSD, 0 = not

# Probability cut-offs that turn the model's output into a risk category.
# Below "moderate" -> Low; from "moderate" up to "high" -> Moderate; at or above "high" -> High.
RISK_THRESHOLDS = {"moderate": 0.40, "high": 0.70}


def risk_category(probability):
    """Map a predicted probability (0-1) to Low / Moderate / High."""
    if probability >= RISK_THRESHOLDS["high"]:
        return "High"
    if probability >= RISK_THRESHOLDS["moderate"]:
        return "Moderate"
    return "Low"
