from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.fraud_schema import (
    FraudPredictionLogOut,
    FraudPredictionRequest,
    FraudPredictionResponse,
)
from app.services.fraud_service import get_prediction_logs, run_prediction_and_log

router = APIRouter(tags=["Fraud"])


@router.post("/predict-fraud", response_model=FraudPredictionResponse)
def predict_fraud(payload: FraudPredictionRequest, db: Session = Depends(get_db)):
    return run_prediction_and_log(payload.model_dump(), db)


@router.get("/prediction-logs", response_model=list[FraudPredictionLogOut])
def prediction_logs(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    return get_prediction_logs(db, limit)
