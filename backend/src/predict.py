from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.train import train_and_select_best_model
from src.utils import FEATURE_COLUMNS, MODELS_DIR, risk_from_probability


def load_model_artifact() -> dict[str, Any]:
    model_path = MODELS_DIR / "best_model.joblib"
    if not Path(model_path).exists():
        train_and_select_best_model()
    return joblib.load(model_path)


def predict_transaction(payload: dict[str, float]) -> dict[str, Any]:
    artifact = load_model_artifact()
    model = artifact["model"]
    scaler = artifact["scaler"]

    ordered_data = {col: payload[col] for col in FEATURE_COLUMNS}
    features = pd.DataFrame([ordered_data])
    scaled = scaler.transform(features)
    fraud_probability = float(model.predict_proba(scaled)[0][1])
    label = "Fraud" if fraud_probability >= 0.5 else "Not Fraud"

    return {
        "prediction_label": label,
        "fraud_probability": fraud_probability,
        "risk_level": risk_from_probability(fraud_probability),
        "model_version": artifact["model_version"],
    }
