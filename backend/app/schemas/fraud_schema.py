from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FraudPredictionRequest(BaseModel):
    Time: float
    Amount: float = Field(..., ge=0)
    V1: float
    V2: float
    V3: float
    V4: float
    V5: float
    V6: float
    V7: float
    V8: float
    V9: float
    V10: float
    V11: float
    V12: float
    V13: float
    V14: float
    V15: float
    V16: float
    V17: float
    V18: float
    V19: float
    V20: float
    V21: float
    V22: float
    V23: float
    V24: float
    V25: float
    V26: float
    V27: float
    V28: float


class FraudPredictionResponse(BaseModel):
    prediction_label: str
    fraud_probability: float
    risk_level: str


class FraudPredictionLogOut(BaseModel):
    id: int
    transaction_amount: float
    fraud_probability: float
    prediction_label: str
    risk_level: str
    model_version: str
    request_payload: Any
    created_at: datetime

    class Config:
        from_attributes = True
