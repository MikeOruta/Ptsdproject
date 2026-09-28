"""Generate a SYNTHETIC PTSD dataset for model development.

!!! THIS DATA IS SYNTHETIC (computer-generated). It describes no real people. !!!

Why synthetic: no public dataset contains these exact features for military
personnel, and confidential military health records cannot be accessed
(Proposal sections 1.8 and 3.4). This is a documented limitation: the model's
metrics show the METHOD works, not how accurate it would be on real personnel.

How each synthetic person is created:
  1. Background and exposure: age, gender, deployment length, combat exposure,
     prior trauma. Longer deployments bring more combat exposure.
  2. Symptoms: a hidden "distress" level, raised by combat exposure and prior
     trauma, pushes sleep problems, anxiety, depression, alcohol use and social
     isolation up together, so symptoms co-occur as they do in real people.
  3. Outcome: the chance of probable PTSD comes from a logistic formula using
     the odds ratios in TRUE_ODDS_RATIOS, then a random draw decides 0 or 1.
     The same inputs can therefore give different outcomes, as in real life.
  4. Mess: a few missing values, out-of-range typos, inconsistent gender
     spellings and duplicate rows are added on purpose, so the preprocessing
     steps (cleaning, imputation, encoding) have real work to do.

Run from the project root:  python -m ml.generate_synthetic_data
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import TARGET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "synthetic_ptsd_dataset.csv"

N_PEOPLE = 2000
RANDOM_SEED = 42           # fixed seed -> the same dataset every run (reproducible)
TARGET_PREVALENCE = 0.18   # about 18% positive, within the 10-20% range reported
                           # for deployed military populations; creates the class
                           # imbalance the training script must handle

# Odds ratio = how much the odds of PTSD multiply for a 1-unit increase.
# Directions follow the literature cited in the proposal (combat exposure,
# prior trauma, sleep, anxiety, depression, alcohol, isolation raise risk;
# younger age raises risk). The exact sizes are ILLUSTRATIVE, chosen to be
# plausible, not taken from any single study.
TRUE_ODDS_RATIOS = {
    "combat_exposure":            1.25,  # per point on the 0-10 scale
    "deployment_duration_months": 1.03,  # per month
    "prior_trauma":               2.00,  # having prior trauma vs not
    "sleep_score":                1.20,  # per point (0-10)
    "anxiety_score":              1.10,  # per point (0-21)
    "depression_score":           1.10,  # per point (0-27)
    "alcohol_use":                1.04,  # per point (0-40)
    "social_isolation":           1.15,  # per point (0-10)
    "age":                        0.98,  # per year (older -> slightly lower risk)
    "gender_female":              1.30,  # female vs male
    "gender_other":               1.30,  # other vs male
}


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def make_people(rng, n):
    """Steps 1 and 2: background, exposure and symptoms (all within valid ranges)."""
    def clip_round(values, low, high):
        return np.clip(np.round(values), low, high).astype(int)

    age = clip_round(rng.normal(31, 7, n), 19, 55)
    gender = rng.choice(["male", "female", "other"], size=n, p=[0.84, 0.14, 0.02])
    deployment = clip_round(rng.gamma(shape=3, scale=3.5, size=n), 1, 36)   # mean ~10 months
    combat = clip_round(rng.normal(3 + 0.12 * deployment, 2.2), 0, 10)
    prior_trauma = rng.binomial(1, 0.28, n)

    # Hidden distress level: higher with more combat and with prior trauma.
    combat_std = (combat - combat.mean()) / combat.std()
    distress = 0.35 * combat_std + 0.30 * prior_trauma + rng.normal(0, 1, n)

    return pd.DataFrame({
        "age": age,
        "gender": gender,
        "deployment_duration_months": deployment,
        "combat_exposure": combat,
        "prior_trauma": prior_trauma,
        "social_isolation": clip_round(rng.normal(3.0 + 1.0 * distress, 2.0), 0, 10),
        "sleep_score": clip_round(rng.normal(3.5 + 1.2 * distress, 2.0), 0, 10),
        "anxiety_score": clip_round(rng.normal(6.0 + 2.5 * distress, 3.5), 0, 21),
        "depression_score": clip_round(rng.normal(6.0 + 3.0 * distress, 4.0), 0, 27),
        "alcohol_use": clip_round(rng.gamma(2, 3, n) + 1.5 * distress, 0, 40),
    })


def linear_score(df):
    """Sum of log(odds ratio) x feature value, before adding the intercept."""
    score = np.zeros(len(df))
    for name, odds_ratio in TRUE_ODDS_RATIOS.items():
        if name.startswith("gender_"):
            values = (df["gender"] == name.removeprefix("gender_")).astype(int)
        else:
            values = df[name]
        score += np.log(odds_ratio) * values
    return score


def find_intercept(score, prevalence):
    """Pick the intercept so the average PTSD probability equals `prevalence`.
    Bisection: keep halving the search interval until it is tiny."""
    low, high = -30.0, 30.0
    for _ in range(100):
        mid = (low + high) / 2
        if sigmoid(mid + score).mean() < prevalence:
            low = mid
        else:
            high = mid
    return mid


def add_mess(rng, df):
    """Step 4: realistic data-quality problems for the preprocessing to fix."""
    df = df.astype({col: "float" for col in df.columns if col not in ("gender", TARGET)})
    n = len(df)

    # ~3% missing answers in four questions.
    for col in ["deployment_duration_months", "sleep_score", "social_isolation", "alcohol_use"]:
        df.loc[rng.random(n) < 0.03, col] = np.nan

    # Out-of-range typos (impossible values).
    df.loc[rng.choice(n, 8, replace=False), "age"] = 999
    df.loc[rng.choice(n, 5, replace=False), "anxiety_score"] = 35

    # Inconsistent gender spelling.
    messy = rng.random(n) < 0.05
    df.loc[messy, "gender"] = df.loc[messy, "gender"].map(
        {"male": "Male", "female": " FEMALE ", "other": "Other"})
    df.loc[(df["gender"] == "Male") & (rng.random(n) < 0.5), "gender"] = "M"

    # 30 duplicate rows (e.g. a form submitted twice).
    return pd.concat([df, df.sample(30, random_state=RANDOM_SEED)], ignore_index=True)


def main():
    rng = np.random.default_rng(RANDOM_SEED)
    df = make_people(rng, N_PEOPLE)

    # Step 3: outcome from the logistic formula plus a random draw.
    score = linear_score(df)
    intercept = find_intercept(score, TARGET_PREVALENCE)
    df[TARGET] = rng.binomial(1, sigmoid(intercept + score))

    df = add_mess(rng, df)
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print("SYNTHETIC dataset written to", OUTPUT_FILE)
    print(f"  rows: {len(df)} (including 30 deliberate duplicates)")
    print(f"  probable PTSD: {df[TARGET].mean():.1%} positive")
    print(f"  intercept used: {intercept:.3f}")


if __name__ == "__main__":
    main()
