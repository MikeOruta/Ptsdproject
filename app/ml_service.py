"""Loads the active Logistic Regression model and makes predictions.

The model is loaded ONCE when the app starts (and again only when an
administrator activates a different model), not on every request. This keeps
predictions fast and memory use low, in line with the low-resource goal.
"""
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features import FEATURE_LABELS, FEATURES

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelService:
    def __init__(self):
        self.pipeline = None
        self.model_id = None
        self.version = None
        self.error = None

    def load_active(self, db_path):
        """Load whichever model is marked is_active = 1 in ml_models."""
        self.pipeline = self.model_id = self.version = None
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT model_id, version, file_path FROM ml_models WHERE is_active = 1"
            ).fetchone()
            conn.close()
        except sqlite3.Error as e:
            self.error = f"Database not ready: {e}"
            return
        if row is None:
            self.error = "No active model. Run: python -m ml.train_model"
            return
        model_id, version, file_path = row
        try:
            self.pipeline = joblib.load(PROJECT_ROOT / file_path)
        except Exception as e:  # missing file, or built with another scikit-learn version
            self.error = f"Could not load model file {file_path}: {e}"
            return
        self.model_id, self.version, self.error = model_id, version, None

    @property
    def ready(self):
        return self.pipeline is not None

    def _frame(self, values):
        """One-row table with the columns in the order the model expects."""
        return pd.DataFrame([{f: values.get(f) for f in FEATURES}])

    def predict_probability(self, values):
        return float(self.pipeline.predict_proba(self._frame(values))[0, 1])

    def explain(self, values, top=4):
        """Which answers pushed THIS person's risk up or down.

        Logistic Regression adds up (coefficient x scaled value) for each
        feature. Each term is that feature's contribution, measured against an
        average person in the training data (a contribution of 0 = average).
        """
        X = self.pipeline[:-1].transform(self._frame(values))   # preprocess + select
        X = X.toarray() if hasattr(X, "toarray") else np.asarray(X)
        coefs = self.pipeline.named_steps["model"].coef_[0]
        names = self.pipeline[:-1].get_feature_names_out()
        items = []
        for name, contribution in zip(names, X[0] * coefs):
            feature = name.split("__", 1)[1]
            items.append({"feature": feature,
                          "label": FEATURE_LABELS.get(feature, feature),
                          "contribution": float(contribution)})
        items.sort(key=lambda i: i["contribution"], reverse=True)
        raising = [i for i in items if i["contribution"] > 0.05][:top]
        lowering = [i for i in reversed(items) if i["contribution"] < -0.05][:2]
        return raising, lowering


model_service = ModelService()
