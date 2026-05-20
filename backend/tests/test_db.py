from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, FraudPredictionLog


def test_db_logging_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    record = FraudPredictionLog(
        transaction_amount=123.4,
        fraud_probability=0.77,
        prediction_label="Fraud",
        risk_level="High",
        model_version="test_v1",
        request_payload={"Amount": 123.4},
    )
    session.add(record)
    session.commit()

    fetched = session.query(FraudPredictionLog).first()
    assert fetched is not None
    assert fetched.prediction_label == "Fraud"
