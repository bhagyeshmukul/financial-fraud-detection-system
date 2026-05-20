import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from app.db.models import Base
from app.db.session import get_db
from app.main import app
import app.services.fraud_service as fraud_service

engine = create_engine("sqlite:///./test_api.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


fraud_service.predict_transaction = lambda payload: {
    "prediction_label": "Not Fraud",
    "fraud_probability": 0.12,
    "risk_level": "Low",
    "model_version": "test_v1",
}


def _payload():
    data = {"Time": 12.0, "Amount": 43.2}
    for i in range(1, 29):
        data[f"V{i}"] = 0.0
    return data


def test_predict_fraud_endpoint():
    response = client.post("/predict-fraud", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert "prediction_label" in body
    assert "fraud_probability" in body
    assert "risk_level" in body


def test_prediction_logs_endpoint():
    response = client.get("/prediction-logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
