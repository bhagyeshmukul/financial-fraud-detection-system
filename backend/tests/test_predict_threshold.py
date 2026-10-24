"""
Check that inference applies the saved threshold, including exact equality. Simple controlled
scores make this independent of real-model prediction quality.
"""

import numpy as np
import pandas as pd
import pytest
from src.predict import predict_rows


class Model:
    """Provide a constant-score stand-in so saved-threshold behavior can be tested exactly."""

    def __init__(self, score):
        """Save the controlled values needed by this small test helper."""
        self.score = score

    def predict_proba(self, features):
        """Return a two-column legitimate/fraud probability array for controlled test assertions."""
        return np.tile([1 - self.score, self.score], (len(features), 1))


@pytest.mark.parametrize(
    "score,threshold,label,risk",
    [
        (0.8, 0.9, "Not Fraud", "Medium"),
        (0.8, 0.8, "Fraud", "High"),
        (0.2, 0.8, "Not Fraud", "Low"),
    ],
)
def test_served_threshold_and_equality(
    monkeypatch, card_payload, score, threshold, label, risk
):
    """Verify served threshold and equality."""
    monkeypatch.setattr(
        "src.predict.load_model_artifact",
        lambda profile: {
            "model": Model(score),
            "decision_threshold": threshold,
            "model_version": "test",
        },
    )
    result = predict_rows(pd.DataFrame([card_payload]), "credit_card")[0]
    assert result["prediction_label"] == label
    assert result["risk_level"] == risk
    assert result["decision_threshold"] == threshold
