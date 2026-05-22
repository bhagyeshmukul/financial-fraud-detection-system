"""Service layer that coordinates prediction and persistence logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import FraudPredictionLog
from src.predict import predict_transaction


def run_prediction_and_log(payload: dict, db: Session) -> dict:
    """Predict fraud likelihood for payload and save a log row in the database."""
    prediction = predict_transaction(payload)
    log = FraudPredictionLog(
        transaction_amount=payload["Amount"],
        fraud_probability=prediction["fraud_probability"],
        prediction_label=prediction["prediction_label"],
        risk_level=prediction["risk_level"],
        model_version=prediction["model_version"],
        request_payload=payload,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return prediction


def get_prediction_logs(db: Session, limit: int = 50):
    """Fetch most recent prediction log entries for dashboard display."""
    return (
        db.query(FraudPredictionLog)
        .order_by(FraudPredictionLog.created_at.desc())
        .limit(limit)
        .all()
    )
