# Router experiment: measured results

Recorded on 23 October 2026. This is the new five-window experiment, separate from the [earlier four-window baseline](VERIFIED_RESULTS.md). The test periods have previously been inspected; these are retrospective research comparisons, not a fresh independent deployment validation.

## What Auto actually uses

| Dataset | Auto/champion candidate | Test accuracy | Test precision | Test fraud recall | Learned router activated? |
|---|---|---:|---:|---:|---|
| credit_card | random_forest | 99.96% | 91.94% | 75.00% | No |
| banksim | xgboost_without_resampling | 99.52% | 80.99% | 72.78% | No |

**The controller was implemented and evaluated, but it did not earn activation on either dataset.** Auto honestly falls back to the strongest eligible individual. Do not claim that routing caused the measured recall change versus the earlier baseline: fitting/calibration windows and the selection objective also changed.

Both current Auto policies exceed 94% accuracy and 80% precision on these test periods. Neither reaches the 80% fraud-recall goal. The dashboard retains those goal misses.

## Fixed experimental protocol

- Same verified publisher imports and feature version 2.0; duplicate removal and stable time ordering precede splitting.
- Distinct time groups: 40% fitting, 10% calibration, 10% router training, 20% validation, 20% testing.
- All three CV algorithms train with SMOTE/SMOTENC on fitting rows only; XGBoost without resampling is retained.
- Sigmoid calibration uses separate original-prevalence examples. The router sees labels only while learning its class-balanced squared candidate-error targets.
- Router: multi-output decision tree, maximum depth 3, seed 42, minimum leaf size max(200, ceil(5% of router-training rows)). Candidate insertion order breaks competence ties.
- Thresholds maximize validation recall with precision >=80% and accuracy >=94%; ties prefer higher precision, then higher threshold. Ineligible manual candidates use an explicitly documented F1 fallback.
- Auto promotion requires a strict validation recall gain over the strongest eligible individual. Individual ties prefer precision, then AP and a stable candidate name. No final-test result chooses thresholds or the Auto policy.
- Earlier model artifacts/reports remain on disk. Current pointers identify these complete new runs. Restart existing API workers after publishing pointers because loaded artifacts are cached.

## Candidate comparisons

### credit_card

Run: `credit_card_20261023T134833_f6b9b2`. Champion threshold: `0.0944749419934`.

| Candidate | Validation precision | Validation recall | Test precision | Test recall | Test AP |
|---|---:|---:|---:|---:|---:|
| logistic_regression | 80.95% | 57.63% | 90.00% | 59.21% | 0.7000 |
| random_forest | 90.00% | 76.27% | 91.94% | 75.00% | 0.8006 |
| xgboost | 84.91% | 76.27% | 82.81% | 69.74% | 0.7715 |
| xgboost_without_resampling | 85.42% | 69.49% | 90.00% | 71.05% | 0.7912 |
| router | 80.00% | 61.02% | 83.64% | 60.53% | 0.6871 |

Auto test counts: **57 frauds detected, 19 missed, 5 false alerts, 59,807 legitimate transactions correctly allowed**.

Validation routing choices (the evaluated controller, not the deployed fallback): `logistic_regression`: 42,011, `random_forest`: 5,772, `xgboost`: 13,682, `xgboost_without_resampling`: 0.

| Window | Rows | Frauds | First time | Last time |
|---|---:|---:|---:|---:|
| fit | 110,813 | 234 | 0 | 72157 |
| calibration | 33,061 | 37 | 72158 | 86113 |
| router_training | 18,499 | 67 | 86115 | 115551 |
| validation | 61,465 | 59 | 115553 | 143907 |
| test | 59,888 | 76 | 143908 | 172792 |

### banksim

Run: `banksim_20261023T135402_086215`. Champion threshold: `0.0581122527571`.

| Candidate | Validation precision | Validation recall | Test precision | Test recall | Test AP |
|---|---:|---:|---:|---:|---:|
| logistic_regression | 80.15% | 67.01% | 83.72% | 65.00% | 0.7798 |
| random_forest | 80.33% | 70.35% | 82.68% | 66.32% | 0.8011 |
| xgboost | 80.15% | 72.64% | 82.47% | 69.58% | 0.8263 |
| xgboost_without_resampling | 80.04% | 75.49% | 80.99% | 72.78% | 0.8386 |
| router | 80.14% | 70.90% | 82.01% | 66.81% | 0.8077 |

Auto test counts: **1,048 frauds detected, 392 missed, 246 false alerts, 131,545 legitimate transactions correctly allowed**.

Validation routing choices (the evaluated controller, not the deployed fallback): `logistic_regression`: 102,551, `random_forest`: 6,276, `xgboost`: 19,993, `xgboost_without_resampling`: 0.

| Window | Rows | Frauds | First time | Last time |
|---|---:|---:|---:|---:|
| fit | 210,430 | 2,880 | 0 | 71 |
| calibration | 60,058 | 720 | 72 | 89 |
| router_training | 62,104 | 720 | 90 | 107 |
| validation | 128,820 | 1,440 | 108 | 143 |
| test | 133,231 | 1,440 | 144 | 179 |

## Evidence and limits

[Compact recorded evidence](router-benchmark-summary.json) contains source checksums/licenses, dependency versions, boundaries and every candidate's frozen metrics. Full curves and serialized objects are in the ignored current model/report directories. The historical benchmark-summary.json and older run directories remain preserved.

The router learns candidate competence for observed feature patterns, not fraud subtype truth. BankSim is simulated; card variables are anonymized and historical. Manual comparisons/replay do not establish fresh accuracy. Analyst notes are not verified labels.

## Verification

- 51 backend tests passed against the isolated local PostgreSQL instance, including real saved-artifact routing, unavailable controller handling, threshold constraints, manual/Auto audit and retry conflicts.
- Eight real-browser Chromium workflows passed against the compiled frontend and actual API/models, including explicit manual/Auto selection and CSV model choice.
- Four private Sites proxy tests passed. Both profile notebooks executed successfully; executed copies are saved under ignored artifacts/.
- Production frontend build passed. Both Compose configurations and shell syntax validated; git whitespace checks passed.
- Annotation-only Python and JavaScript/JSX edits were checked against executable syntax baselines, excluding comments/docstrings and formatting.
- The first browser attempt encountered unexpected reloads with concurrent local Vite instances; an initial isolated-preview invocation also used the wrong directory. The final complete eight-test run used the correct compiled frontend and passed. No benchmark model was retuned in response.
- A Docker engine is unavailable locally: Compose parsing is verified, actual image build/run is not. No AWS/Sites resources were provisioned or published.
- The older traffic-results.json remains historical evidence for its earlier models; it is not a current-router-run capacity claim.

## Interview wording

> Evaluated Logistic Regression, Random Forest and XGBoost with training-only SMOTE/SMOTENC, chronological holdouts and calibrated probabilities. Implemented dynamic candidate selection with a validation-based individual fallback; routing did not outperform the strongest eligible individual in the recorded experiments. Built manual/automatic scoring, batch analysis and persisted model-choice audit records.

Use a metric row from this run with its dataset and split when adding measured results to the CV. Do not say the router improved predictions when it was not promoted.
