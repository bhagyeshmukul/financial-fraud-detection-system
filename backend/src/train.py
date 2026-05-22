"""Training pipeline to fit, compare, and persist the best fraud model."""

from __future__ import annotations

from datetime import UTC, datetime

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from src.data_loader import load_transaction_data
from src.evaluate import best_f1_threshold, evaluate_model, ranking_score
from src.preprocessing import preprocess_data
from src.utils import MODELS_DIR, REPORTS_DIR, ensure_dirs, write_json


def train_and_select_best_model() -> dict:
    """Train candidate models, rank them, and write model/report artifacts."""
    ensure_dirs()

    df = load_transaction_data()
    artifacts = preprocess_data(df)

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=42),
    }

    try:
        from xgboost import XGBClassifier

        candidates["xgboost"] = XGBClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42,
        )
    except Exception:
        pass

    metrics_by_model = {}
    best_name = None
    best_score = -1.0
    best_model = None

    for name, model in candidates.items():
        model.fit(artifacts.X_train_resampled, artifacts.y_train_resampled)
        metrics = evaluate_model(model, artifacts.X_test_scaled, artifacts.y_test)
        metrics_by_model[name] = metrics

        score = ranking_score(metrics)
        if score > best_score:
            best_score = score
            best_name = name
            best_model = model

    version = f"{best_name}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    decision_threshold = best_f1_threshold(best_model, artifacts.X_test_scaled, artifacts.y_test)
    model_artifact = {
        "model": best_model,
        "scaler": artifacts.scaler,
        "model_name": best_name,
        "model_version": version,
        "decision_threshold": decision_threshold,
    }

    joblib.dump(model_artifact, MODELS_DIR / "best_model.joblib")

    report_payload = {
        "selected_model": best_name,
        "model_version": version,
        "decision_threshold": decision_threshold,
        "selection_score": best_score,
        "metrics": metrics_by_model,
    }
    write_json(REPORTS_DIR / "metrics_report.json", report_payload)
    write_json(REPORTS_DIR / "evaluation_report.json", report_payload)

    return report_payload


if __name__ == "__main__":
    result = train_and_select_best_model()
    print(result["selected_model"])
