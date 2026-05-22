### Financial Fraud Detection System

A full-stack fraud detection platform that scores card transactions in near real time, classifies risk (`Low`, `Medium`, `High`), and stores prediction logs for audit and analyst review.

### Business Logic and Value

- Financial fraud is a low-frequency, high-impact problem.
- The system helps triage suspicious activity quickly by combining:
  - ML-based probability scoring
  - Business-friendly risk-level mapping
  - Persistent prediction logging in PostgreSQL
- It is designed for demo-to-production style workflows: model training, API serving, UI consumption, and historical observability.

### Tech Stack

- Backend/API: `FastAPI`, `Uvicorn`, `Pydantic`
- ML: `pandas`, `numpy`, `scikit-learn`, `xgboost`, `imbalanced-learn (SMOTE)`, `joblib`
- Database: `PostgreSQL`, `SQLAlchemy`, `Alembic`
- Frontend: `React`, `Vite`, `Recharts`
- Containerization: `Docker`, `Docker Compose`

### Core Features

- `POST /predict-fraud` returns:
  - `prediction_label` (`Fraud` or `Not Fraud`)
  - `fraud_probability`
  - `risk_level` (`Low`/`Medium`/`High`)
- `GET /prediction-logs` returns recent persisted predictions.
- `GET /sample-transactions` provides low/medium/high scenario payloads for easy testing.
- Automatic schema migration in container startup (`alembic upgrade head`).

### What the Model Input Means

The API accepts exactly `30` numeric inputs:

- `Time`
- `V1` to `V28`
- `Amount`

`V1..V28` are anonymized PCA-derived signals from the dataset. They do not map to named business fields directly, but the model learns useful fraud/non-fraud behavior patterns from combinations of these variables.

### Project Structure (Quick View)

- `backend/app/` → API routes, schemas, DB integration, service layer
- `backend/src/` → ML pipeline (load/preprocess/train/evaluate/predict)
- `backend/alembic/` → schema migration scripts
- `backend/data/` → datasets used for model training experiments
- `frontend/src/` → React UI and API integrations

For a full architecture and flow explanation, see `PROJECT_ARCHITECTURE.md`.

### Prerequisites

- Python `3.11+` recommended
- Node.js `18+` and `npm`
- PostgreSQL `16+` (for local non-Docker setup)
- Docker Desktop (if using Docker flow)

### Environment Variables

The backend reads database configuration from `DATABASE_URL`.

#### Local backend example

```bash
export DATABASE_URL="postgresql+psycopg2://fraud_user:fraud_password@localhost:5432/fraud_db"
```

#### Docker Compose variables (`.env` in project root)

```env
POSTGRES_USER=fraud_user
POSTGRES_PASSWORD=fraud_password
POSTGRES_DB=fraud_db
```

`docker-compose.yml` uses these values to construct backend `DATABASE_URL` automatically.

### Run Locally (without Docker)

#### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`

#### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

### Run with Docker Compose

From project root:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

### API Usage Examples

#### Health check

```bash
curl -X GET "http://localhost:8000/"
```

#### Get sample scenarios

```bash
curl -X GET "http://localhost:8000/sample-transactions"
```

#### Predict fraud

```bash
curl -X POST "http://localhost:8000/predict-fraud" \
  -H "Content-Type: application/json" \
  -d '{
    "Time": 865,
    "V1": -0.5374802762,
    "V2": 8.5411202134,
    "V3": 1.7172749111,
    "V4": -1.142444037,
    "V5": 0.8710858686,
    "V6": -2.379534301,
    "V7": 3.6324085605,
    "V8": 1.4689942064,
    "V9": 2.3140508421,
    "V10": 0.6080150786,
    "V11": 3.7338869247,
    "V12": -0.2240221028,
    "V13": -1.2259402182,
    "V14": -0.1872434624,
    "V15": 0.6574995181,
    "V16": -1.1501334386,
    "V17": -1.0286127611,
    "V18": -0.0294838246,
    "V19": -1.4228495895,
    "V20": -0.8863804803,
    "V21": -1.4464451487,
    "V22": -1.3059306083,
    "V23": -2.8105028234,
    "V24": -1.5235354845,
    "V25": 1.5057483529,
    "V26": -1.7950689266,
    "V27": -0.5417854048,
    "V28": -2.0273416245,
    "Amount": 4.4646831979
  }'
```

### Training and Model Lifecycle

- Training entrypoint: `backend/src/train.py`
- Default dataset: `backend/data/creditcard.csv`
- Pipeline summary:
  1. Load + clean data
  2. Split train/test
  3. Apply `SMOTE` on training set
  4. Train candidate models (`LogisticRegression`, `RandomForestClassifier`, `XGBClassifier`)
  5. Evaluate and select best model by weighted ranking (recall/F1/ROC-AUC oriented)
  6. Save artifact to `backend/models/best_model.joblib`
- Inference uses stored scaler/model and a learned decision threshold for classification.

### Testing

```bash
cd backend
pytest -q
```

### Troubleshooting

- `npm: command not found`
  - Install Node.js and ensure `npm` is on your `PATH`.
- `No module named pytest` or dependency import errors
  - Activate your backend virtual environment and run `pip install -r requirements.txt`.
- DB connection failures
  - Verify `DATABASE_URL` (local) or `POSTGRES_*` values in `.env` (Docker).
- Migration issues
  - Run `alembic upgrade head` from `backend/` and verify DB credentials.

### Interview-Ready Highlights

- Built an imbalanced-fraud pipeline using metrics beyond accuracy (`Recall`, `F1`, `ROC-AUC`).
- Combined model serving with auditable persistence for operational traceability.
- Used migration-driven schema management (`Alembic`) for repeatable environments.
