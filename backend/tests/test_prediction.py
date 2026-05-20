import numpy as np

import src.predict as predict_module
from src.predict import predict_transaction


class DummyModel:
    def predict_proba(self, X):
        return np.array([[0.2, 0.8]])


class DummyScaler:
    def transform(self, X):
        return X


def test_prediction_output_contains_required_fields():
    predict_module.load_model_artifact = lambda: {
        "model": DummyModel(),
        "scaler": DummyScaler(),
        "model_version": "test_v1",
    }

    payload = {"Time": 1000.0, "Amount": 120.5}
    for i in range(1, 29):
        payload[f"V{i}"] = 0.1

    result = predict_transaction(payload)

    assert "prediction_label" in result
    assert "fraud_probability" in result
    assert "risk_level" in result
    assert 0.0 <= result["fraud_probability"] <= 1.0
