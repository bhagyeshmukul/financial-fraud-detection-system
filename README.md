### Financial Fraud Detection System

- End-to-end production-style ML + full-stack project for detecting fraudulent financial transactions.
- Stack: `FastAPI`, `scikit-learn`, `XGBoost`, `SMOTE`, `PostgreSQL`, `Alembic`, `React`, `Vite`, `Docker Compose`.

### Project Overview

- This project predicts whether a transaction is fraudulent and returns probability + risk level.
- It also stores every prediction request/response trace in PostgreSQL for auditability.

### Business Problem

- Fraud losses are significant; delayed detection increases financial and reputational risk.
- The system provides near real-time fraud scoring to support analyst workflows.

### Why Imbalanced Classification Matters

- Fraud events are rare relative to normal transactions.
- A model can achieve high accuracy by predicting only non-fraud, which is not useful.

### Why Accuracy Alone Is Misleading

- Accuracy ignores false negatives/false positives balance on skewed datasets.
- This project prioritizes `recall`, `precision`, `F1-score`, and `ROC-AUC` for model selection.

### Dataset

- Primary target: Kaggle Credit Card Fraud dataset (`creditcard.csv`).
- Fallback: synthetic realistic imbalanced data generation inside `backend/src/data_loader.py`.

### Architecture

- `backend/src/`: ML data pipeline, training, evaluation, and prediction utilities.
- `backend/app/`: FastAPI API, service layer, SQLAlchemy models, DB session wiring.
- `backend/alembic/`: migration setup with versioned schema creation.
- `frontend/src/`: React dashboard + API integration.

### ML Workflow

- Load data → clean + fill missing values → scale features.
- Stratified split and apply `SMOTE` on training set.
- Train: Logistic Regression, Random Forest, XGBoost.
- Evaluate: Accuracy, Precision, Recall, F1, ROC-AUC, Confusion Matrix, PR curve.
- Select best model by weighted ranking favoring recall/precision/F1/ROC-AUC.
- Persist model via `joblib` and save reports to `backend/reports/`.

### Database and Migration Design

- Schema managed by Alembic migration, not by runtime `create_all` as primary method.
- Main table: `fraud_prediction_logs` with payload, score, label, risk level, and timestamp.

### Alembic Migration

- Migration file: `backend/alembic/versions/001_create_fraud_prediction_logs_table.py`.
- Startup sequence in backend container runs `alembic upgrade head` before API launch.

### API Endpoints

- `POST /predict-fraud`
  - Input: transaction features JSON (`Time`, `V1..V28`, `Amount`)
  - Output: `prediction_label`, `fraud_probability`, `risk_level`
  - Side effect: inserts log row into PostgreSQL.
- `GET /prediction-logs`
  - Returns latest prediction logs.

### Frontend Screenshots (Placeholder)

- Add screenshots under `docs/screenshots/` and reference here for portfolio presentation.

### Run Backend (Local)

- `cd backend`
- `pip install -r requirements.txt`
- `alembic upgrade head`
- `uvicorn app.main:app --reload`

### Run Frontend (Local)

- `cd frontend`
- `npm install`
- `npm run dev`

### Run with Docker Compose

- From project root: `docker compose up --build`
- Services:
  - Backend: `http://localhost:8000`
  - Frontend: `http://localhost:5173`
  - PostgreSQL: `localhost:5432`

### Run Alembic Migrations Manually

- `cd backend`
- `alembic upgrade head`
- `alembic downgrade -1`

### Run Tests

- `cd backend`
- `pytest -q`

### Resume Bullet Points

- Built a production-style fraud detection platform with model training, serving, and audit logging.
- Implemented robust model selection for imbalanced classification using recall/F1/ROC-AUC priorities.
- Designed migration-driven PostgreSQL schema lifecycle with Alembic in Dockerized deployment.

### Interview Explanation

- Explain end-to-end flow: data prep, SMOTE, model comparison, API serving, and DB observability.
- Highlight why imbalanced metrics and threshold/risk mapping matter in fraud systems.

### Interview Q&A (Examples)

- Q: Why not select by accuracy?
  - A: In highly imbalanced fraud detection, accuracy can hide poor fraud recall.
- Q: Why use SMOTE?
  - A: To improve minority-class learning signal during training without altering test distribution.
- Q: Why Alembic over `create_all`?
  - A: Versioned, auditable, repeatable schema evolution across environments.
