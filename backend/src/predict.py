"""
Load saved models and score transactions without starting training. Shared features, frozen
thresholds and model metadata keep live decisions reproducible.
"""

from __future__ import annotations
import json
import importlib.metadata
from functools import lru_cache
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.features import build_features, describe_context
from src.profiles import get_profile
from src.utils import FEATURE_VERSION, MODELS_DIR, REPORTS_DIR, risk_from_probability


class ModelUnavailable(RuntimeError):
    """
    Signal a missing or incompatible serving dependency so the HTTP layer can return a clear 503
    response.
    """

    pass


def current_pointer(profile):
    """Read a serving manifest, translating absent or broken files to a clear 503."""
    get_profile(profile)
    try:
        pointer = json.loads((MODELS_DIR / f"{profile}.current.json").read_text())
        if not isinstance(pointer, dict):
            raise ValueError("Current manifest must be a JSON object.")
        return pointer
    except (OSError, ValueError) as error:
        raise ModelUnavailable(
            f"No verified {profile} serving manifest: {error}"
        ) from error


@lru_cache(maxsize=16)
def load_model_artifact(profile="credit_card", model_choice="champion"):
    """
    Load and cache one allowlisted saved artifact; check its profile, version, features and
    dependency versions.
    """
    get_profile(profile)
    pointer_path = MODELS_DIR / f"{profile}.current.json"
    if not pointer_path.exists():
        raise ModelUnavailable(
            f"No verified {profile} model. Run python -m src.train --profile {profile}."
        )
    try:
        pointer = json.loads(pointer_path.read_text())
        if model_choice == "champion":
            model_path = pointer["model"]
        elif model_choice == "router" and "router" in pointer:
            model_path = pointer["router"]
        elif model_choice in pointer.get("candidates", {}):
            model_path = pointer["candidates"][model_choice]
        else:
            raise ValueError(
                f"Candidate {model_choice!r} is unavailable for this model version."
            )
        artifact = joblib.load(MODELS_DIR / model_path)
        if (
            artifact["profile"] != profile
            or artifact["model_version"] != pointer["model_version"]
            or artifact["feature_version"] != FEATURE_VERSION
        ):
            raise ValueError("Artifact lineage mismatch; retrain the model.")
        # Reject an environment that differs from training rather than risking incompatible deserialization.
        for package, version in artifact["dependencies"].items():
            if package != "python" and importlib.metadata.version(package) != version:
                raise ValueError(
                    f"{package} differs from training version {version}; use the recorded environment."
                )
        # Concurrency is provided by API workers. Avoid nested per-request CPU pools.
        for calibrated in getattr(artifact["model"], "calibrated_classifiers_", []):
            pipeline = calibrated.estimator
            if "model__n_jobs" in pipeline.get_params():
                pipeline.set_params(model__n_jobs=1)
        return artifact
    except Exception as error:
        raise ModelUnavailable(f"Cannot load {profile} model: {error}") from error


def model_choices(profile):
    """Describe scoring choices without confusing them with report inspection."""
    pointer = current_pointer(profile)
    auto = pointer.get(
        "auto_policy",
        {"available": False, "reason": "This older run has no trained router."},
    )
    auto_files = [pointer.get("router", "")] + list(
        pointer.get("candidates", {}).values()
    )
    files_ready = bool(auto_files) and all(
        (MODELS_DIR / path).is_file() for path in auto_files
    )
    choices = [
        {"id": "champion", "label": "Current champion", "available": True},
        {
            "id": "auto",
            "label": "Auto — let the system choose",
            "available": bool(auto.get("available") and files_ready),
            "reason": auto["reason"]
            if files_ready
            else "Router or candidate artifacts are missing.",
        },
    ]
    labels = {
        "logistic_regression": "Logistic Regression",
        "random_forest": "Random Forest",
        "xgboost": "XGBoost · SMOTE/SMOTENC",
        "xgboost_without_resampling": "XGBoost · without resampling",
    }
    # Offer only candidates listed by the trusted current-run manifest and present on disk.
    for name, path in pointer.get("candidates", {}).items():
        choices.append(
            {
                "id": name,
                "label": labels.get(name, name),
                "available": (MODELS_DIR / path).is_file(),
            }
        )
    return choices


def model_report(profile):
    """Read the evaluation report and require its version to match the model currently being served."""
    artifact = load_model_artifact(profile)
    pointer = json.loads((MODELS_DIR / f"{profile}.current.json").read_text())
    try:
        report = json.loads((REPORTS_DIR / pointer["report"]).read_text())
        if report["model_version"] != artifact["model_version"]:
            raise ValueError("Report does not match the served model.")
        return report
    except (OSError, ValueError) as error:
        raise ModelUnavailable(f"Matching evaluation unavailable: {error}") from error


@lru_cache(maxsize=2)
def sample_transactions(profile):
    """
    Load selected validation examples belonging to the current run for demonstration, not a new
    accuracy test.
    """
    load_model_artifact(profile)
    pointer = json.loads((MODELS_DIR / f"{profile}.current.json").read_text())
    return json.loads((MODELS_DIR / pointer["samples"]).read_text())


@lru_cache(maxsize=2)
def reference_history(profile):
    """
    Load BankSim input-only reference observations; credit-card scoring does not need customer
    history.
    """
    if profile != "banksim":
        return pd.DataFrame()
    artifact = load_model_artifact(profile)
    path = MODELS_DIR / artifact["model_version"] / "history.pkl"
    return pd.read_pickle(path)


def prediction_features(frame, profile, history=None, seed_before=None):
    """
    Combine permitted seed/session observations, then call the same feature builder used in
    training.
    """
    if profile == "banksim":
        pieces = []
        if seed_before is not None:
            reference = reference_history(profile)
            pieces.append(
                reference[
                    (reference["customer"].isin(frame["customer"].unique()))
                    & (reference["step"] < seed_before)
                ]
            )
        if history is not None and len(history):
            pieces.append(history)
        history = pd.concat(pieces, ignore_index=True) if pieces else None
    return build_features(frame, profile, history)


def predict_rows(
    frame, profile, history=None, seed_before=None, model_choice="champion"
):
    """Build features once, select a policy, and score with its frozen threshold."""
    features = prediction_features(frame, profile, history, seed_before)
    selected_choice, router_version, estimated_losses = model_choice, None, None
    routing_status, reason = (
        "manual",
        "The requested individual candidate scored this transaction.",
    )
    if model_choice == "auto":
        pointer = current_pointer(profile)
        policy = pointer.get("auto_policy", {})
        if not policy.get("available"):
            raise ModelUnavailable(
                policy.get("reason", "Auto is unavailable for this older run.")
            )
        selected_choice, reason = policy["policy"], policy["reason"]
        routing_status = "routed" if selected_choice == "router" else "fallback"
    if selected_choice == "router":
        artifact = load_model_artifact(profile, "router")
        selected, estimated_losses = artifact["model"].choose(features)
        router_version = artifact["model_version"]
        probabilities = np.empty(len(features), dtype=float)
        # Score only rows routed to this candidate; other candidates are not queried for these rows.
        for name in artifact["model"].candidate_names:
            positions = np.flatnonzero(selected == name)
            if len(positions):
                expert = load_model_artifact(profile, name)
                probabilities[positions] = expert["model"].predict_proba(
                    features.iloc[positions]
                )[:, 1]
    else:
        artifact = (
            load_model_artifact(profile)
            if selected_choice == "champion"
            else load_model_artifact(profile, selected_choice)
        )
        selected = np.repeat(
            artifact.get("model_name", "legacy_champion"), len(features)
        )
        probabilities = artifact["model"].predict_proba(features)[:, 1]
    threshold = float(artifact["decision_threshold"])
    results = []
    # Turn each ordered score into its label, risk and recorded model/routing explanation.
    for index, (probability, row) in enumerate(
        zip(probabilities, features.to_dict("records"))
    ):
        probability = float(probability)
        row_reason = reason
        if estimated_losses is not None:
            error = float(np.min(estimated_losses[index]))
            row_reason = f"Router chose {selected[index]} for these transaction patterns (estimated class-balanced squared error {error:.4f}; this is not a fraud probability)."
        results.append(
            {
                "prediction_label": "Fraud"
                if probability >= threshold
                else "Not Fraud",
                "fraud_probability": probability,
                "risk_level": risk_from_probability(probability, threshold),
                "profile": profile,
                "model_version": artifact["model_version"],
                "decision_threshold": threshold,
                "review_threshold": threshold / 2,
                "context": describe_context(row, profile),
                "derived_features": row,
                "requested_model": model_choice,
                "used_model": str(selected[index]),
                "router_version": router_version,
                "routing_status": routing_status,
                "routing_reason": row_reason,
            }
        )
    return results


def predict_transaction(payload):
    """
    Keep the original single-credit-card Python entry point working through the shared scoring
    path.
    """
    return predict_rows(pd.DataFrame([payload]), "credit_card")[0]
