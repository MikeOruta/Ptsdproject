"""Server-side input validation. The browser also checks forms, but browser
checks can be bypassed, so the server always checks again."""
import re

from ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def validate_password(password):
    """Return an error message, or None if the password is acceptable."""
    if len(password) < 10:
        return "Password must be at least 10 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain both letters and numbers."
    return None


def validate_email(email):
    return None if EMAIL_RE.match(email) and len(email) <= 255 else "Enter a valid email address."


def clean_text(value, max_len):
    """Trim whitespace and cap the length of free-text input."""
    return (value or "").strip()[:max_len]


def validate_assessment(form):
    """Check every model feature. Returns (values, errors)."""
    values, errors = {}, {}

    for field, (low, high) in NUMERIC_FEATURES.items():
        raw = (form.get(field) or "").strip()
        try:
            number = int(raw)
        except ValueError:
            errors[field] = "Please enter a whole number."
            continue
        if not low <= number <= high:
            errors[field] = f"Must be between {low} and {high}."
        else:
            values[field] = number

    for field, allowed in CATEGORICAL_FEATURES.items():
        choice = (form.get(field) or "").strip().lower()
        if choice not in allowed:
            errors[field] = "Please choose an option."
        else:
            values[field] = choice

    pcl5 = (form.get("pcl5_score") or "").strip()
    if pcl5:
        if pcl5.isdigit() and 0 <= int(pcl5) <= 80:
            values["pcl5_score"] = int(pcl5)
        else:
            errors["pcl5_score"] = "PCL-5 must be between 0 and 80, or left blank."
    else:
        values["pcl5_score"] = None

    values["other_factors"] = clean_text(form.get("other_factors"), 1000) or None

    if form.get("consent") != "yes":
        errors["consent"] = "You must give consent before submitting."
    return values, errors
