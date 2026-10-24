# Financial Fraud Detection System

A working portfolio application for **fraud analysis, transaction scoring, analyst review, and demonstrations**. It retains Python, Pandas, Scikit-Learn, Logistic Regression, Random Forest, XGBoost and SMOTE, alongside FastAPI, PostgreSQL, SQLAlchemy, Alembic, React, Vite, Recharts and Docker.

The system estimates risk and records decisions. It does not move money or connect to a bank. Its two dataset profiles have independent models, reports and input meanings.

See [current router results](docs/ROUTER_RESULTS.md) and the [EC2/ECS AWS walkthrough](docs/AWS_DEPLOYMENT.md).

Auto evaluates a learned candidate router, then uses the stronger eligible individual when routing does not improve validation recall.

## Workspaces

- **Analysis:** real held-out metrics, all algorithm comparisons, confusion matrix, ROC/PR/calibration curves, distributions, validation feature importance, and labelled CSV scoring.
- **Live demo:** readable BankSim payments, original validation examples, adjustable replay, and an advanced credit-card input form.
- **Analyst review:** persistent history, risk/review filters, pagination, notes, append-only review events and CSV export.
- **Service health:** database/model/report readiness, request counters and measured prediction latency.

No dashboard metric is a placeholder. Missing reports are displayed as unavailable.

## Datasets and honest results

| Profile | Original publisher | Raw rows / frauds | Meaning |
|---|---|---|---|
| credit_card | [ULB / Worldline](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) | 284,807 / 492 | Real anonymized card transactions from 2013; V1–V28 are supplied PCA components |
| banksim | [BankSim](https://www.kaggle.com/datasets/ealaxi/banksim1) | 594,643 / 7,200 | Simulated bank payments; customer, merchant, category, amount and day |

Imports retain source/version/license, SHA-256 checksum and class counts. Original source data is downloaded into ignored backend/data/raw, without altering the old CSV/iCloud files in the worktree. Count/schema checks catch accidental sample files; they do not constitute cryptographic publisher attestation. BankSim is CC BY-NC-SA 4.0; retain its attribution and use the publisher's applicable terms.

A previous UI displayed 98% accuracy without using its report; the old report recorded 64.6%. Those values are not used by v2. Generated reports in backend/reports/v2 and the dashboard are the source of current results. See [current router results](docs/ROUTER_RESULTS.md); [the earlier baseline](docs/VERIFIED_RESULTS.md) is preserved separately.

**94% accuracy is a target, not a hardcoded result.** An always-legitimate classifier can exceed 99% accuracy on these datasets while catching no fraud. Report precision, recall, PR-AUC, average precision and the confusion matrix alongside accuracy. Initial precision/recall goals are 80%; report misses transparently.

## Laptop setup

Use Python 3.11, Node 24 and PostgreSQL 16+ (or Docker). The original .venv is left untouched. In PyCharm, select .venv311/bin/python as the project interpreter; the previous SDK points to Python 3.14. Generated data, environments and runtime artifacts are excluded from project indexing.

```sh
uv venv --python 3.11 .venv311
uv pip install --python .venv311/bin/python -r backend/requirements-dev.txt
npm --prefix frontend ci
chmod +x scripts/python scripts/local-db.sh scripts/run-local.sh
```

scripts/python uses this environment, sets the backend import path, and exposes the OpenMP runtime shipped with the macOS Scikit-Learn wheel to XGBoost. Linux containers install libgomp1. If using a separately activated Mac interpreter, install libomp or configure its library path; do not silently omit XGBoost.

Start an isolated local PostgreSQL instance:

```sh
./scripts/local-db.sh
cp .env.example .env
```

The helper defaults to the PostgreSQL installation at /Library/PostgreSQL/17/bin and port 55432, with its data under ignored .runtime/postgres. Set POSTGRES_BIN / LOCAL_POSTGRES_PORT when needed. This is a loopback-only development instance using local trust authentication. It never changes an existing server. Stop it with `./scripts/local-db.sh stop`.

For another PostgreSQL installation, create fraud_db and fraud_test and set DATABASE_URL / TEST_DATABASE_URL accordingly.

## Import and train

Run profiles sequentially on an 8 GB laptop:

```sh
./scripts/python -m src.data_loader --profile credit_card
./scripts/python -m src.data_loader --profile banksim
./scripts/python -m src.train --profile all
```

If direct download is unavailable, download the original CSV from its publisher and run:
```sh
./scripts/python -m src.data_loader --profile banksim --source /absolute/path/to/bs140513_032310.csv
```

Training is explicit and can take several minutes. Serving never downloads data, trains a model, or falls back to synthetic data.

The pipeline:
1. Validate labels and time, normalize columns and remove duplicate rows.
2. Build features using exactly the same functions as inference. BankSim history uses strictly earlier days; no labels or same-day/future observations enter a feature.
3. Split by chronological time groups: 40% fitting, 10% calibration, 10% router training, 20% validation and 20% final testing. Time-group boundaries mean row percentages can differ.
4. Fit imputation/scaling only on fitting rows. Apply SMOTE there for credit-card data, or SMOTENC before categorical one-hot encoding for BankSim.
5. Train Logistic Regression, Random Forest and XGBoost sequentially. Calibrate probability estimates with sigmoid calibration at original class prevalence.
6. Retain non-resampled XGBoost as a comparison. Train a shallow multi-output decision-tree router on the separate router-training window, estimating squared candidate error with equal total fraud/legitimate training weight. It selects a candidate for transaction patterns, not a named fraud subtype.
7. Maximize validation recall with precision >=80% and accuracy >=94%. Auto uses routing only for a strict recall improvement over the strongest eligible individual; otherwise it records that individual as its fallback. If no individual qualifies, Auto is unavailable and the manual champion uses an explicitly ineligible F1 fallback.
8. Evaluate frozen candidates on the historical test period and save every candidate/controller, matching reports, validation examples and label-free reference history before atomically publishing the current pointer. This previously inspected test period is a retrospective comparison, not a fresh independent test.

Scoring offers Auto, champion and individual candidates separately from report inspection. Learned routing consults one candidate per transaction and groups batch rows efficiently. All CV algorithms remain actual trained experiments even when they do not win. Test results are inspected for reporting, not used for another tuning round.

## Run

```sh
./scripts/run-local.sh
```

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs. The script migrates the database once, then starts the API and Vite. Ctrl-C stops those application processes; the development database remains available.

The demo seeds a fixed earlier-day BankSim history at the first prediction and then adds that session's observations. It is an interactive simulation, not an exact replay benchmark. New sessions isolate customer histories. CSV uploads each get a separate unseeded history, so their behavioural features depend only on earlier rows/days in that upload.

## API

Existing endpoints remain: POST /predict-fraud, GET /prediction-logs, GET /sample-transactions.

New versioned interfaces:

| Method | Path | Purpose |
|---|---|---|
| GET | /api/v1/profiles | Contracts and model availability |
| GET | /api/v1/profiles/{profile}/evaluation | Matching frozen report |
| GET | /api/v1/profiles/{profile}/samples | Original validation examples |
| POST | /api/v1/sessions | Create profile-specific, optionally seeded session |
| POST | /api/v1/profiles/{profile}/predictions | Validate, score and atomically log |
| POST | /api/v1/profiles/{profile}/batch-predictions | Multipart CSV with session_id and request_id |
| GET | /api/v1/predictions | Profile/session/risk/review filters and before_id pagination |
| GET | /api/v1/predictions/export | Up to 5,000 filtered audit rows |
| PATCH | /api/v1/predictions/{id}/review | Review state and notes |
| GET | /api/v1/predictions/{id}/reviews | Append-only review events |
| GET | /api/v1/operations | Measured operational counters and latency |
| GET | /health/live, /health/ready | Liveness and dependency readiness |

Single prediction envelope:
```json
{
  "session_id": "UUID returned by session creation",
  "request_id": "a fresh UUID, reused only for retrying this same request",
  "model_choice": "auto",
  "transaction": {"step": 120, "customer": "C1", "merchant": "M1", "category": "es_travel", "amount": 150}
}
```

Optional `model_choice` accepts `champion` (default), `auto`, `logistic_regression`, `random_forest`, `xgboost`, or `xgboost_without_resampling`; CSV accepts the same multipart form field. Responses/history/exports retain requested and used candidates, router version, routing status/reason and applied threshold. A changed choice with the same request ID is a conflict.

The response includes the persisted ID, profile, model version, applied thresholds, estimated probability, label, risk, context and processing time. At p >= threshold the result is Fraud/High; p >= threshold/2 is Medium; otherwise Low. Context describes input/history facts, not causal model explanations.

CSV headers must contain the profile inputs, optionally Class or fraud. Known BankSim source fields age/gender/ZIP may also be supplied; they are ignored as predictors. Publisher single-quoted strings are normalized consistently with training. Labels are separated before feature building. Limits: 5 MB / 5,000 rows. Invalid uploads fail atomically. Retries with the same UUID return the stored response; reuse with different data returns 409. Profiles never share sessions or models.

## Tests and traffic

```sh
# Real PostgreSQL integration tests; fallback SQLite unit tests work without this variable.
TEST_DATABASE_URL=postgresql+psycopg2://fraud_local@127.0.0.1:55432/fraud_test ./scripts/python -m pytest backend/tests -q

# Start the application first:
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

From the project root:
```sh
node --test deploy/sites/worker.test.mjs
./scripts/python scripts/traffic.py --profile credit_card --rps 10 --seconds 60 --pid YOUR_API_PID
```

Traffic results are written to ignored artifacts/traffic.json, including actual throughput, errors and latency percentiles. Supply the server PID to measure its process-tree RSS. HTTP counters are per-worker; persisted prediction counts and latency samples span workers. Batch timings are amortized per row.

## Containers and later hosting

Development:
```sh
docker compose up --build
```

Train on the host first; Compose mounts the completed model/report directories read-only. PostgreSQL readiness gates a one-shot migration service. Development services bind to loopback.

Production:
```sh
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
```

See [deployment instructions](deploy/README.md) for the complete private container stack and the Sites + Python server path. Production uses a private gateway and server-held API token, never a secret in browser JavaScript. Sites packaging stages locally with `node deploy/sites/build.mjs`; publication is a later action.

## Analysis and architecture

Open [the analysis notebook](notebooks/fraud_analysis.ipynb) using the .venv311 interpreter. It walks through source verification, EDA, behavioural features, resampling, model comparison and error analysis. See [the architecture guide](PROJECT_ARCHITECTURE.md) for design and implementation details.

Current limitations: research datasets are old or simulated; BankSim day granularity cannot support minute-level velocity; PCA variables cannot be interpreted as location/device fields; analyst notes are not verified labels; production applicability requires validation on the intended institution's data.
