from src.predict import predict_transaction


class _MockModel:
    def predict_proba(self, _X):
        return [[0.2, 0.8]]


class _MockScaler:
    def transform(self, features):
        return features


def _payload():
    data = {"Time": 100.0, "Amount": 50.0}
    for i in range(1, 29):
        data[f"V{i}"] = 0.0
    return data


def test_predict_transaction_uses_artifact_threshold(monkeypatch):
    monkeypatch.setattr(
        "src.predict.load_model_artifact",
        lambda: {
            "model": _MockModel(),
            "scaler": _MockScaler(),
            "model_version": "test_model",
            "decision_threshold": 0.75,
        },
    )

    result = predict_transaction(_payload())

    assert result["prediction_label"] == "Fraud"
    assert result["fraud_probability"] == 0.8
