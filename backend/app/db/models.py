from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class FraudPredictionLog(Base):
    __tablename__ = "fraud_prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_amount = Column(Float, nullable=False)
    fraud_probability = Column(Float, nullable=False)
    prediction_label = Column(String(32), nullable=False)
    risk_level = Column(String(32), nullable=False)
    model_version = Column(String(64), nullable=False)
    request_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
