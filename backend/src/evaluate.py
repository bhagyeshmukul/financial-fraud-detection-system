"""
Turn known labels and fraud scores into thresholds, metrics and chart points. Validation selects
operating policies; frozen testing reports their later performance.
"""

from __future__ import annotations
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def threshold_for_f1(labels, probabilities) -> float:
    """
    Choose the threshold with the largest F1 score; this is the explicitly ineligible fallback
    when quality constraints cannot be met.
    """
    precision, recall, thresholds = precision_recall_curve(labels, probabilities)
    if not len(thresholds):
        return 0.5
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1],
        precision[:-1] + recall[:-1],
        out=np.zeros_like(precision[:-1]),
        where=(precision[:-1] + recall[:-1]) > 0,
    )
    return float(max(thresholds[int(np.argmax(f1))], np.finfo(float).eps))


def constrained_threshold(
    labels, probabilities, minimum_precision=0.8, minimum_accuracy=0.94
):
    """Maximize validation recall under the alert-quality requirements.

    Score each complete group of equal probabilities, so equality follows the
    same >= rule as live predictions. Return an explicitly ineligible F1
    threshold when no operating point qualifies; manual experiments still work.
    """
    labels, probabilities = (
        np.asarray(labels, dtype=int),
        np.asarray(probabilities, dtype=float),
    )
    order = np.argsort(-probabilities, kind="stable")
    sorted_scores = probabilities[order]
    ends = np.flatnonzero(np.r_[sorted_scores[:-1] != sorted_scores[1:], True])
    true_positives = np.cumsum(labels[order])[ends]
    false_positives = ends + 1 - true_positives
    precision = true_positives / (ends + 1)
    recall = true_positives / max(1, labels.sum())
    accuracy = (true_positives + len(labels) - labels.sum() - false_positives) / len(
        labels
    )
    eligible = np.flatnonzero(
        (precision >= minimum_precision) & (accuracy >= minimum_accuracy)
    )
    if not len(eligible):
        return threshold_for_f1(labels, probabilities), False
    # lexsort's last key is primary: recall, then precision, then threshold.
    winner = eligible[
        np.lexsort(
            (sorted_scores[ends][eligible], precision[eligible], recall[eligible])
        )[-1]
    ]
    return float(sorted_scores[ends][winner]), True


def _points(x, y, limit=350):
    """
    Reduce long curve arrays to evenly spaced JSON points while retaining their endpoints for
    browser charts.
    """
    indices = np.unique(np.linspace(0, len(x) - 1, min(limit, len(x)), dtype=int))
    return [{"x": float(x[i]), "y": float(y[i])} for i in indices]


def evaluate_probabilities(labels, probabilities, threshold=0.5):
    """
    Compare thresholded probabilities against known labels and return metrics, confusion counts
    and curves.
    """
    labels, probabilities = (
        np.asarray(labels, dtype=int),
        np.asarray(probabilities, dtype=float),
    )
    predicted = probabilities >= threshold
    both = len(np.unique(labels)) == 2
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    fpr, tpr, _ = roc_curve(labels, probabilities) if both else ([], [], [])
    observed, predicted_bins = calibration_curve(
        labels, probabilities, n_bins=10, strategy="quantile"
    )
    return {
        "samples": int(len(labels)),
        "frauds": int(labels.sum()),
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1_score": float(f1_score(labels, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)) if both else None,
        "average_precision": float(average_precision_score(labels, probabilities))
        if labels.sum()
        else None,
        "pr_auc": float(auc(recall, precision)) if both else None,
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1]).tolist(),
        "pr_curve": _points(recall, precision),
        "roc_curve": _points(fpr, tpr) if both else [],
        "calibration_curve": _points(predicted_bins, observed),
    }


def evaluate_model(model, features, labels, threshold=0.5):
    """
    Obtain a classifier’s fraud probabilities and evaluate them with the exact supplied decision
    threshold.
    """
    return evaluate_probabilities(
        labels, model.predict_proba(features)[:, 1], threshold
    )


def best_f1_threshold(model, features, labels):
    """
    Keep the earlier model-based threshold helper available by delegating to probability-based
    F1 selection.
    """
    return threshold_for_f1(labels, model.predict_proba(features)[:, 1])


def ranking_score(metrics):
    """
    Expose average precision as the historical ranking helper; the new Auto policy uses
    constrained validation recall.
    """
    return metrics["average_precision"]
