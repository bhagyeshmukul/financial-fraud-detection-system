"""Model evaluation helpers and weighted ranking logic for model selection."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_model(model, X_test, y_test) -> dict[str, Any]:
    """Compute classification metrics used by model-comparison workflow."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    precision_vals, recall_vals, _ = precision_recall_curve(y_test, y_proba)

    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "precision_recall_curve": {
            "precision": np.asarray(precision_vals).tolist(),
            "recall": np.asarray(recall_vals).tolist(),
            "pr_auc": float(auc(recall_vals, precision_vals)),
        },
    }


def ranking_score(metrics: dict[str, float]) -> float:
    """Compute weighted score prioritizing fraud-detection usefulness metrics."""
    return (
        0.35 * metrics["recall"]
        + 0.25 * metrics["precision"]
        + 0.25 * metrics["f1_score"]
        + 0.15 * metrics["roc_auc"]
    )


def best_f1_threshold(model, X_test, y_test) -> float:
    """Find probability threshold that maximizes F1 on validation data."""
    y_proba = model.predict_proba(X_test)[:, 1]
    precision_vals, recall_vals, thresholds = precision_recall_curve(y_test, y_proba)

    if len(thresholds) == 0:
        return 0.5

    precision_core = np.asarray(precision_vals[:-1])
    recall_core = np.asarray(recall_vals[:-1])
    f1_scores = np.divide(
        2 * precision_core * recall_core,
        precision_core + recall_core,
        out=np.zeros_like(precision_core),
        where=(precision_core + recall_core) > 0,
    )
    best_index = int(np.argmax(f1_scores))
    return float(thresholds[best_index])
