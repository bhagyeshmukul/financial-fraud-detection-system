"""HTTP routes for fraud prediction and prediction-log retrieval."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.fraud_schema import (
    FraudPredictionLogOut,
    FraudPredictionRequest,
    FraudPredictionResponse,
    SampleTransactionResponse,
)
from app.services.fraud_service import get_prediction_logs, run_prediction_and_log
from app.services.sample_payloads import get_sample_transactions

router = APIRouter(tags=["Fraud"])


@router.post("/predict-fraud", response_model=FraudPredictionResponse)
def predict_fraud(payload: FraudPredictionRequest, db: Session = Depends(get_db)):
    """Run fraud prediction for one transaction and persist audit log details."""
    return run_prediction_and_log(payload.model_dump(), db)


@router.get("/prediction-logs", response_model=list[FraudPredictionLogOut])
def prediction_logs(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    """Return recent prediction logs with a bounded limit for dashboard usage."""
    return get_prediction_logs(db, limit)


@router.get("/sample-transactions", response_model=SampleTransactionResponse)
def sample_transactions():
    """Return curated threat-level transaction payloads for demo and API testing."""
    return {"samples": get_sample_transactions()}
