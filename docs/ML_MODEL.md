# Machine Learning Model

Covers Proposal Objectives 2, 3 and 6 and sections 3.4–3.7 and 3.11.

## 1. Data (and the main limitation)

The proposal (§3.4) planned to use publicly available PTSD datasets. No public
dataset contains these exact ten features for military personnel, and
confidential military health records cannot be accessed (§1.8). An earlier
sample dataset was rejected because of **data leakage**: its PTSD label was
computed by summing the same PCL-5 items used as inputs, so a model would only
re-learn that sum and report meaningless near-perfect accuracy.

The model was therefore trained on a **synthetic dataset**
(`ml/generate_synthetic_data.py`, 2,000 people + 30 duplicates):

1. Background and exposure are generated first (longer deployments bring more combat exposure).
2. A hidden "distress" level, raised by combat exposure and prior trauma, pushes
   sleep problems, anxiety, depression, alcohol use and isolation up together,
   because symptoms co-occur in real people.
3. The PTSD outcome is drawn from a logistic formula using documented odds
   ratios whose directions follow the literature cited in the proposal. A random
   draw decides each outcome, so identical answers can have different outcomes.
4. Realistic data problems are injected: ~3% missing answers, impossible
   values (age 999, anxiety 35), inconsistent gender spelling and duplicate rows.

Prevalence is set to ~18–19%, within the range reported for deployed
populations, which creates the class imbalance handled in training.

**Limitation (to state in the report):** the metrics show the method works on
data with known relationships. They are **not** evidence of accuracy on real
personnel. Before operational use the model must be retrained on approved real
data: `python -m ml.train_model path/to/real.csv` accepts any CSV with the same
columns, with no code changes.

## 2. Features (Objective 2): `ml/features.py`

| Feature | Range | Notes |
|---|---|---|
| age | 18–70 | years |
| gender | male / female / other | one-hot encoded, male = baseline |
| deployment_duration_months | 0–120 | most recent deployment |
| combat_exposure | 0–10 | frequency |
| prior_trauma | 0/1 | before deployment |
| social_isolation | 0–10 | |
| sleep_score | 0–10 | higher = worse |
| anxiety_score | 0–21 | GAD-7 |
| depression_score | 0–27 | PHQ-9 |
| alcohol_use | 0–40 | AUDIT |

PCL-5 is stored for clinicians but is **not** an input (leakage, Known Issue B).

## 3. Preprocessing (§3.6): `ml/train_model.py`

| Step | How |
|---|---|
| Cleaning | Remove 30 duplicates; standardise spellings (" FEMALE " → female); impossible values → missing |
| Missing values | Median imputation (numbers), most-frequent (gender) |
| Normalisation | StandardScaler (mean 0, standard deviation 1) |
| Encoding | One-hot encoding of gender |
| Feature selection | ANOVA F-test, keep p < 0.05 (`SelectFpr`) |

All steps live in one scikit-learn **Pipeline** saved as `ml/model_v1.pkl`, so
the web app applies *exactly* the same preprocessing to each new assessment.
The scaler is inside the pipeline rather than a separate file, which makes it
impossible to pair the model with the wrong scaler.

## 4. Training (§3.7)

- 80% training / 20% test split, **stratified** (same PTSD rate in both)
- 5-fold stratified cross-validation on the training set
- `LogisticRegression(class_weight="balanced")` gives a missed PTSD case more weight than a false alarm (class imbalance, Known Issue C)

## 5. Results (§3.11): `ml/metrics_v1.json`

5-fold cross-validation: accuracy 0.75, precision 0.42, recall 0.75, F1 0.54, ROC-AUC 0.82.

Held-out test set (400 people):

| Metric | Value | Meaning |
|---|---|---|
| Recall | 0.714 | 55 of 77 PTSD cases caught |
| Precision | 0.359 | about 1 in 3 flags is a true case |
| F1-score | 0.478 | balance of the two |
| Accuracy | 0.700 | |
| ROC-AUC | 0.786 | good separation of the two groups |

|  | Predicted no PTSD | Predicted PTSD |
|---|---|---|
| **Actual no PTSD** | 225 | 98 |
| **Actual PTSD** | 22 | 55 |

The model favours **recall**: in screening, missing a case is worse than an
extra clinical review. Accuracy alone would mislead: predicting "no PTSD" for
everyone scores 81% accuracy while catching nobody.

**Risk categories work as intended.** Of test cases, the actual PTSD rate was
6.7% in *Low*, 22.7% in *Moderate* and 47.5% in *High*.

**Interpretability check.** The learned odds ratios closely match those used to
generate the data (e.g. combat exposure 1.249 learned vs 1.25 true; sleep
1.216 vs 1.20; alcohol 1.040 vs 1.04), showing the pipeline recovers real
relationships. Feature selection dropped `gender_female` (not significant).

## 6. In the web app

`app/ml_service.py` loads the active model **once** at startup. For each
assessment it returns a probability, mapped to Low (< 0.40), Moderate
(0.40–0.70) or High (≥ 0.70). The thresholds are configurable in `.env`. It
also lists which answers raised or lowered that person's risk
(coefficient × scaled value), which makes Logistic Regression explainable to
clinicians.
