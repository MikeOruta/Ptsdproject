"""Train and evaluate the Logistic Regression PTSD risk model.

Run from the project root:  python -m ml.train_model
(Optional: python -m ml.train_model path/to/other.csv to train on another
dataset with the same columns, e.g. a real public dataset.)

Steps (Proposal sections 3.6, 3.7 and 3.11):
  1. Load the dataset
  2. Clean it: duplicates, spelling, impossible values
  3. Split 80% train / 20% test, stratified to keep the PTSD ratio equal
  4. Build the pipeline: impute -> scale -> encode -> select features -> Logistic Regression
  5. Cross-validate on the training set (5 folds)
  6. Train on the full training set, evaluate once on the untouched test set
  7. Interpret: odds ratio for every feature the model kept
  8. Save the model and metrics; register the model in the database

NOTE: the default dataset is SYNTHETIC. The metrics show the method works on
data with known relationships; they are NOT evidence of real-world accuracy.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.feature_selection import SelectFpr, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features import (CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES,
                         RISK_THRESHOLDS, TARGET, risk_category)
from ml.generate_synthetic_data import TRUE_ODDS_RATIOS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = PROJECT_ROOT / "data" / "synthetic_ptsd_dataset.csv"
MODEL_VERSION = "v1"
MODEL_FILE = PROJECT_ROOT / "ml" / f"model_{MODEL_VERSION}.pkl"
METRICS_FILE = PROJECT_ROOT / "ml" / f"metrics_{MODEL_VERSION}.json"
RANDOM_SEED = 42
METRIC_NAMES = ["accuracy", "precision", "recall", "f1", "roc_auc"]


# ---------------------------------------------------------------- Step 2
def clean(df):
    """Data cleaning. Returns the cleaned data and a report of what changed."""
    report = {"rows_loaded": len(df)}

    # a) Remove exact duplicate rows (e.g. a form submitted twice).
    df = df.drop_duplicates().copy()
    report["duplicates_removed"] = report["rows_loaded"] - len(df)

    # b) Standardise category spelling: " FEMALE " -> "female", "M" -> "male".
    df["gender"] = (df["gender"].astype(str).str.strip().str.lower()
                    .replace({"m": "male", "f": "female", "nan": np.nan}))
    unknown = df["gender"].notna() & ~df["gender"].isin(CATEGORICAL_FEATURES["gender"])
    df.loc[unknown, "gender"] = np.nan  # unknown category -> treated as missing

    # c) Impossible values (e.g. age 999) become missing, to be imputed later.
    #    The row is kept: its other answers are still useful.
    invalid = {}
    for col, (low, high) in NUMERIC_FEATURES.items():
        bad = df[col].notna() & ~df[col].between(low, high)
        if bad.any():
            invalid[col] = int(bad.sum())
        df.loc[bad, col] = np.nan
    report["invalid_values_set_to_missing"] = invalid

    # d) Rows with no outcome label cannot be used for training.
    before = len(df)
    df = df.dropna(subset=[TARGET])
    report["rows_without_label_removed"] = before - len(df)

    report["missing_values_to_impute"] = {
        col: int(n) for col, n in df[FEATURES].isna().sum().items() if n}
    report["rows_after_cleaning"] = len(df)
    return df, report


# ---------------------------------------------------------------- Step 4
def build_pipeline():
    """All preprocessing + the model in one object, so the web app applies the
    exact same steps to a new assessment as were used in training."""
    numeric_steps = Pipeline([
        ("impute", SimpleImputer(strategy="median")),   # missing -> column median
        ("scale", StandardScaler()),                    # normalise: mean 0, std 1
    ])
    categorical_steps = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        # One-hot encoding: gender -> gender_female, gender_other (male = baseline).
        ("encode", OneHotEncoder(categories=[CATEGORICAL_FEATURES["gender"]],
                                 drop="first", handle_unknown="ignore")),
    ])
    preprocess = ColumnTransformer([
        ("num", numeric_steps, list(NUMERIC_FEATURES)),
        ("cat", categorical_steps, list(CATEGORICAL_FEATURES)),
    ])
    return Pipeline([
        ("preprocess", preprocess),
        # Feature selection: keep features whose link with PTSD is statistically
        # significant (ANOVA F-test, p < 0.05); drop the rest.
        ("select", SelectFpr(f_classif, alpha=0.05)),
        # class_weight="balanced": a missed PTSD case counts more than a false
        # alarm, compensating for there being fewer PTSD cases (class imbalance).
        ("model", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])


def evaluate(y_true, y_prob):
    y_pred = (y_prob >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred),
        "roc_auc": roc_auc_score(y_true, y_prob),
        "confusion_matrix": {"true_negative": int(tn), "false_positive": int(fp),
                             "false_negative": int(fn), "true_positive": int(tp)},
    }


# ---------------------------------------------------------------- Step 7
def odds_ratios(pipeline):
    """Coefficients as odds ratios per ORIGINAL unit (e.g. per month of
    deployment), which is how a clinician would read them."""
    names = pipeline[:-1].get_feature_names_out()          # features that survived selection
    coefs = pipeline.named_steps["model"].coef_[0]
    scaler = pipeline.named_steps["preprocess"].named_transformers_["num"].named_steps["scale"]
    numeric = list(NUMERIC_FEATURES)

    rows = []
    for name, coef in zip(names, coefs):
        group, feature = name.split("__", 1)
        if group == "num":
            # The model saw scaled values, so divide by the scale to get per-unit.
            coef = coef / scaler.scale_[numeric.index(feature)]
        rows.append({"feature": feature,
                     "odds_ratio": round(float(np.exp(coef)), 3),
                     "true_odds_ratio": TRUE_ODDS_RATIOS.get(feature)})
    return sorted(rows, key=lambda r: abs(np.log(r["odds_ratio"])), reverse=True)


def register_model(metrics):
    """Store the model in the ml_models table and make it the only active one."""
    load_dotenv(PROJECT_ROOT / ".env")
    db_path = PROJECT_ROOT / os.getenv("DB_PATH", "db/ptsd_system.db")
    conn = sqlite3.connect(db_path)
    try:
        with conn:  # one transaction: both statements succeed or neither does
            conn.execute("UPDATE ml_models SET is_active = 0")
            conn.execute(
                """INSERT INTO ml_models (version, algorithm, file_path, metrics_json, is_active)
                   VALUES (?, 'LogisticRegression', ?, ?, 1)
                   ON CONFLICT(version) DO UPDATE SET file_path = excluded.file_path,
                     metrics_json = excluded.metrics_json, is_active = 1""",
                (MODEL_VERSION, MODEL_FILE.relative_to(PROJECT_ROOT).as_posix(),
                 json.dumps(metrics)),
            )
        print(f"        Registered model {MODEL_VERSION} in ml_models (is_active = 1)")
    except sqlite3.OperationalError as e:
        print(f"        Could not register model ({e}). Run: python db/init_db.py")
    finally:
        conn.close()


def main():
    data_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    synthetic = data_file.resolve() == DEFAULT_DATA.resolve()

    print(f"Step 1  Load {data_file.name}" + ("  [SYNTHETIC DATA]" if synthetic else ""))
    df, cleaning = clean(pd.read_csv(data_file))
    print(f"Step 2  Cleaning report: {json.dumps(cleaning)}")

    X, y = df[FEATURES], df[TARGET].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED)
    print(f"Step 3  Split: {len(X_train)} train / {len(X_test)} test "
          f"(PTSD rate {y_train.mean():.1%} / {y_test.mean():.1%})")

    pipeline = build_pipeline()
    print("Step 4  Pipeline: impute -> scale -> one-hot -> SelectFpr(p<0.05) -> LogisticRegression")

    cv = cross_validate(pipeline, X_train, y_train, scoring=METRIC_NAMES,
                        cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_SEED))
    cv_summary = {m: {"mean": float(cv[f"test_{m}"].mean()),
                      "std": float(cv[f"test_{m}"].std())} for m in METRIC_NAMES}
    print("Step 5  5-fold cross-validation (mean +/- std):")
    for m, s in cv_summary.items():
        print(f"          {m:<9} {s['mean']:.3f} +/- {s['std']:.3f}")

    pipeline.fit(X_train, y_train)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    test = evaluate(y_test, y_prob)
    cm = test["confusion_matrix"]
    print("Step 6  Held-out test set:")
    for m in METRIC_NAMES:
        print(f"          {m:<9} {test[m]:.3f}")
    print("          Confusion matrix     predicted: no PTSD   PTSD")
    print(f"            actual no PTSD              {cm['true_negative']:>5}  {cm['false_positive']:>5}")
    print(f"            actual PTSD                 {cm['false_negative']:>5}  {cm['true_positive']:>5}")

    # Do higher risk categories really contain more actual PTSD cases?
    cats = pd.Series([risk_category(p) for p in y_prob], index=y_test.index)
    by_cat = {c: {"count": int((cats == c).sum()),
                  "actual_ptsd_rate": round(float(y_test[cats == c].mean()), 3)
                  if (cats == c).any() else None} for c in ["Low", "Moderate", "High"]}
    print(f"          Risk categories: {json.dumps(by_cat)}")

    ors = odds_ratios(pipeline)
    kept = {r["feature"] for r in ors}
    dropped = [n.split("__", 1)[1] for n in pipeline[:-2].get_feature_names_out()
               if n.split("__", 1)[1] not in kept]
    print("Step 7  Odds ratios per unit          learned   true (used to generate)")
    for r in ors:
        print(f"          {r['feature']:<28} {r['odds_ratio']:>6.3f}   {r['true_odds_ratio'] or '-'}")
    print(f"          Dropped by feature selection: {', '.join(dropped) or 'none'}")

    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_file": data_file.name,
        "data_is_synthetic": synthetic,
        "warning": ("Trained on SYNTHETIC data: metrics demonstrate the method, not "
                    "real-world accuracy. Decision-support only, not a medical diagnosis."
                    if synthetic else "Decision-support only, not a medical diagnosis."),
        "scikit_learn_version": sklearn.__version__,
        "cleaning": cleaning,
        "train_size": len(X_train), "test_size": len(X_test),
        "cross_validation": cv_summary,
        "test": test,
        "risk_thresholds": RISK_THRESHOLDS,
        "risk_categories_on_test_set": by_cat,
        "odds_ratios": ors,
        "features_dropped_by_selection": dropped,
    }
    joblib.dump(pipeline, MODEL_FILE)
    METRICS_FILE.write_text(json.dumps(metrics, indent=2))
    print(f"Step 8  Saved {MODEL_FILE.name} and {METRICS_FILE.name}")
    register_model(metrics)


if __name__ == "__main__":
    main()
