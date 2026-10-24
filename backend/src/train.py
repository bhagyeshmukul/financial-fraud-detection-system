"""
Run the complete reproducible fraud-model experiment. Fit experts, calibrate, train routing,
select on validation, evaluate on testing, then publish matching saved artifacts.
"""

from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
import platform
import uuid
from datetime import UTC, datetime
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from src.data_loader import load_transaction_data
from src.evaluate import constrained_threshold, evaluate_model, evaluate_probabilities
from src.features import build_features
from src.preprocessing import chronological_split, model_pipeline
from src.profiles import PROFILES, get_profile
from src.routing import ModelRouter, choose_auto_policy, routed_probabilities
from src.utils import (
    DATA_DIR,
    FEATURE_VERSION,
    MODELS_DIR,
    REPORTS_DIR,
    ensure_dirs,
    write_json,
)


def estimators(quick=False):
    """
    Create all three CV algorithms with fixed settings; quick mode reduces tree counts only for
    tests.
    """
    return {
        "logistic_regression": LogisticRegression(
            max_iter=1500, random_state=42, C=0.1
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=12 if quick else 120,
            max_depth=14,
            min_samples_leaf=2,
            n_jobs=2,
            random_state=42,
        ),
        "xgboost": XGBClassifier(
            n_estimators=12 if quick else 250,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            tree_method="hist",
            n_jobs=2,
            random_state=42,
            eval_metric="logloss",
        ),
    }


def dataset_summary(frame, profile):
    """Summarize missing values, class balance and numeric distributions for the analysis dashboard."""
    specification = get_profile(profile)
    numeric = [
        column
        for column in specification.inputs
        if pd.api.types.is_numeric_dtype(frame[column])
    ]
    distributions = {}
    # Prepare histogram bins for each numeric input so the UI displays real dataset distributions.
    for column in numeric:
        values = frame[column].dropna().to_numpy()
        counts, edges = np.histogram(values, bins=20)
        distributions[column] = [
            {"bin": f"{edges[i]:.2f}–{edges[i + 1]:.2f}", "count": int(count)}
            for i, count in enumerate(counts)
        ]
    return {
        "rows": len(frame),
        "frauds": int(frame[specification.target].sum()),
        "fraud_rate": float(frame[specification.target].mean()),
        "missing_values": {
            column: int(count) for column, count in frame.isna().sum().items()
        },
        "numeric_summary": frame[numeric].describe().round(4).to_dict(),
        "distributions": distributions,
        "categories": frame["category"].value_counts().to_dict()
        if profile == "banksim"
        else {},
    }


def train_and_select_best_model(
    profile="credit_card",
    *,
    frame=None,
    manifest=None,
    output_models=None,
    output_reports=None,
    quick=False,
):
    """
    Train and compare experts and a router, then save a complete versioned run before switching
    the current pointer.
    """
    ensure_dirs()
    specification = get_profile(profile)
    if frame is None:
        frame = load_transaction_data(profile=profile)
        manifest = json.loads((DATA_DIR / f"{profile}.manifest.json").read_text())
    elif manifest is None:
        raise ValueError(
            "In-memory data requires an explicit manifest; fixtures must be labelled synthetic."
        )
    frame = (
        frame.drop_duplicates()
        .sort_values(specification.time, kind="stable")
        .reset_index(drop=True)
    )
    partitions = chronological_split(frame, profile)
    # This feature builder reads inputs/history only; labels enter fitting/evaluation separately.
    features = build_features(frame, profile)
    labels = frame[specification.target].astype(int)
    models_dir = Path(output_models) if output_models else MODELS_DIR
    reports_dir = Path(output_reports) if output_reports else REPORTS_DIR
    version = f"{profile}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    run_dir = models_dir / version
    run_dir.mkdir(parents=True)
    candidates, validation, thresholds, base_estimators = (
        {},
        {},
        {},
        estimators(quick),
    )
    minority_count = int(labels.iloc[partitions.fit].sum())

    def fit_candidate(name, estimator, resample):
        """
        Fit one expert on fitting rows, calibrate on later rows, and choose its alert threshold
        using validation only.
        """
        print(
            f"{profile}: fitting {name} ({len(partitions.fit)} earlier transactions)",
            flush=True,
        )
        pipeline = model_pipeline(
            profile, features.columns, clone(estimator), resample, minority_count
        )
        pipeline.fit(features.iloc[partitions.fit], labels.iloc[partitions.fit])
        # Freeze the fitted pipeline, then adjust its probabilities on later real-prevalence rows.
        calibrated = CalibratedClassifierCV(pipeline, method="sigmoid", cv="prefit")
        calibrated.fit(
            features.iloc[partitions.calibration], labels.iloc[partitions.calibration]
        )
        validation_probabilities = calibrated.predict_proba(
            features.iloc[partitions.validation]
        )[:, 1]
        threshold, eligible = constrained_threshold(
            labels.iloc[partitions.validation], validation_probabilities
        )
        candidates[name] = calibrated
        thresholds[name] = threshold
        validation[name] = evaluate_model(
            calibrated,
            features.iloc[partitions.validation],
            labels.iloc[partitions.validation],
            threshold,
        )
        validation[name]["eligible"] = eligible

    # Train every CV algorithm explicitly; no dependency failure may silently remove a candidate.
    for name, estimator in base_estimators.items():
        fit_candidate(name, estimator, True)
    # Fix this comparison before looking at validation; it remains an XGBoost variant.
    fit_candidate("xgboost_without_resampling", base_estimators["xgboost"], False)
    router_features = features.iloc[partitions.router_training]
    # Every expert's scores here are out of its fitting AND calibration windows.
    router = ModelRouter().fit(
        router_features,
        labels.iloc[partitions.router_training],
        {
            name: candidate.predict_proba(router_features)[:, 1]
            for name, candidate in candidates.items()
        },
    )
    router_validation, selected_experts, _ = routed_probabilities(
        router, candidates, features.iloc[partitions.validation]
    )
    # Freeze the operating threshold and Auto decision before computing any final test metrics.
    thresholds["router"], eligible = constrained_threshold(
        labels.iloc[partitions.validation], router_validation
    )
    validation["router"] = evaluate_probabilities(
        labels.iloc[partitions.validation], router_validation, thresholds["router"]
    )
    validation["router"]["eligible"] = eligible
    auto_policy = choose_auto_policy(validation)
    # The champion remains an individual for old clients; Auto is an explicit policy.
    selected = auto_policy.get("baseline") or max(
        candidates, key=lambda name: validation[name]["average_precision"]
    )
    dependencies = {
        # Exact versions make serialized model compatibility inspectable and enforceable.
        name: importlib.metadata.version(name)
        for name in (
            "numpy",
            "pandas",
            "scikit-learn",
            "xgboost",
            "imbalanced-learn",
            "joblib",
        )
    }
    dependencies["python"] = platform.python_version()
    metrics = {}
    # Persist every calibrated candidate with its own threshold and frozen evaluation.
    for name, candidate in candidates.items():
        artifact = {
            "model": candidate,
            "profile": profile,
            "model_name": name,
            "model_version": version,
            "decision_threshold": thresholds[name],
            "review_threshold": thresholds[name] / 2,
            "feature_version": FEATURE_VERSION,
            "feature_columns": list(features.columns),
            "dataset": manifest,
            "dependencies": dependencies,
        }
        joblib.dump(artifact, run_dir / f"{name}.joblib", compress=3)
        metrics[name] = {
            "validation": validation[name],
            "test": evaluate_model(
                candidate,
                features.iloc[partitions.test],
                labels.iloc[partitions.test],
                thresholds[name],
            ),
            "resampling": "none"
            if name.endswith("_without_resampling")
            else ("SMOTE" if profile == "credit_card" else "SMOTENC"),
        }
    # Save the controller separately; its output is estimated expert error, not fraud.
    router_artifact = {
        "model": router,
        "model_name": "router",
        "profile": profile,
        "model_version": version,
        "feature_version": FEATURE_VERSION,
        "decision_threshold": thresholds["router"],
        "dependencies": dependencies,
        "feature_columns": list(features.columns),
        "dataset": manifest,
    }
    joblib.dump(router_artifact, run_dir / "router.joblib", compress=3)
    router_test, test_experts, _ = routed_probabilities(
        router, candidates, features.iloc[partitions.test]
    )
    metrics["router"] = {
        "validation": validation["router"],
        "test": evaluate_probabilities(
            labels.iloc[partitions.test], router_test, thresholds["router"]
        ),
        "resampling": "routes separately calibrated candidates",
    }
    auto_policy["test"] = (
        metrics[auto_policy["policy"]]["test"] if auto_policy["available"] else None
    )
    auto_policy["validation"] = (
        validation[auto_policy["policy"]] if auto_policy["available"] else None
    )
    test_labels = labels.iloc[partitions.test].to_numpy()
    baseline = evaluate_probabilities(test_labels, np.zeros(len(test_labels)), 0.5)
    baseline["average_precision"] = float(test_labels.mean())
    baseline["pr_auc"] = None
    report = {
        "profile": profile,
        "model_version": version,
        "selected_model": selected,
        "decision_threshold": thresholds[selected],
        "feature_version": FEATURE_VERSION,
        "selection_rule": "Maximum validation recall subject to precision >=80% and accuracy >=94%; routing must strictly beat the best eligible individual. Threshold ties prefer precision, then higher threshold. If no individual qualifies, champion uses highest validation AP with an explicitly ineligible F1 threshold.",
        "calibration": "Sigmoid on the separate 40–50% time-group window at original prevalence.",
        "evaluation_note": "Historical benchmark comparison: this test period was inspected in the earlier project. No test labels choose router structure, thresholds or Auto policy; this is not a fresh independent test.",
        "auto_policy": auto_policy,
        "router": {
            "algorithm": "Multi-output decision tree estimating class-balanced squared expert error",
            "max_depth": 3,
            "min_samples_leaf": router.pipeline.named_steps["tree"].min_samples_leaf,
            "candidate_order": list(router.candidate_names),
            "tie_break": "First candidate in recorded order",
            "validation_routes": {
                name: int((selected_experts == name).sum()) for name in candidates
            },
            "test_routes": {
                name: int((test_experts == name).sum()) for name in candidates
            },
            "note": "Transaction patterns select a candidate. No named fraud subtype is predicted.",
        },
        "dataset": manifest,
        "dependencies": dependencies,
        "partitions": {
            name: {
                "rows": len(indices),
                "frauds": int(labels.iloc[indices].sum()),
                "start": float(frame.iloc[indices][specification.time].min()),
                "end": float(frame.iloc[indices][specification.time].max()),
            }
            for name, indices in vars(partitions).items()
        },
        "summary": dataset_summary(frame, profile),
        "features": list(features.columns),
        "models": metrics,
        "always_legitimate_baseline": baseline,
        "quality_goals": {"accuracy": 0.94, "precision": 0.80, "recall": 0.80},
    }
    selected_metrics = metrics[selected]["test"]
    report["quality_goals_met"] = {
        key: selected_metrics[key] >= goal
        for key, goal in report["quality_goals"].items()
    }
    # Model-agnostic importance on validation only; never uses the test partition.
    from sklearn.inspection import permutation_importance

    sample = features.iloc[partitions.validation].sample(
        n=min(2000, len(partitions.validation)), random_state=42
    )
    importance = permutation_importance(
        candidates[selected],
        sample,
        labels.loc[sample.index],
        scoring="average_precision",
        n_repeats=2,
        random_state=42,
        n_jobs=1,
    )
    report["feature_importance"] = sorted(
        [
            {"feature": column, "importance": float(value)}
            for column, value in zip(features.columns, importance.importances_mean)
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )
    report_path = reports_dir / f"{version}.json"
    write_json(report_path, report)

    # Demo examples come from validation. They are not another test benchmark.
    demo = frame.iloc[partitions.validation].copy()
    probabilities = candidates[selected].predict_proba(
        features.iloc[partitions.validation]
    )[:, 1]
    demo["demo_probability"] = probabilities
    chosen = set()
    # Select examples across the validation score range; this is not representative sampling.
    for position in np.argsort(probabilities)[
        np.linspace(0, len(demo) - 1, 30, dtype=int)
    ]:
        chosen.add(int(position))
    fraud_positions = np.flatnonzero(demo[specification.target].to_numpy() == 1)
    chosen.update(int(i) for i in fraud_positions[:20])
    samples = []
    # Preserve original validation inputs and labels in a stable demonstration order.
    for position in sorted(chosen):
        row = demo.iloc[position]
        samples.append(
            {
                "id": f"{profile}_validation_{int(row.name)}",
                "payload": {key: row[key] for key in specification.inputs},
                "actual_label": int(row[specification.target]),
                "source": "validation replay, selected for demonstration; not representative prevalence",
            }
        )
    sample_path = run_dir / "samples.json"
    write_json(sample_path, samples)
    if profile == "banksim":
        # Store only input observations, never labels; filter to relevant customers at prediction time.
        frame.loc[
            frame[specification.time] < report["partitions"]["test"]["start"],
            list(specification.inputs),
        ].to_pickle(run_dir / "history.pkl")
    pointer = {
        # This pointer is published last: every referenced model, report and sample already exists.
        "model_version": version,
        "model": str((run_dir / f"{selected}.joblib").relative_to(models_dir)),
        "report": report_path.name,
        "samples": str(sample_path.relative_to(models_dir)),
        "candidates": {
            name: str((run_dir / f"{name}.joblib").relative_to(models_dir))
            for name in candidates
        },
        "router": str((run_dir / "router.joblib").relative_to(models_dir)),
        "auto_policy": {
            key: value
            for key, value in auto_policy.items()
            if key not in ("test", "validation")
        },
    }
    write_json(models_dir / f"{profile}.current.json", pointer)
    print(
        json.dumps(
            {
                "profile": profile,
                "selected": selected,
                "test": {
                    k: selected_metrics[k]
                    for k in ("accuracy", "precision", "recall", "average_precision")
                },
                "goals_met": report["quality_goals_met"],
            }
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=[*PROFILES, "all"], default="all")
    arguments = parser.parse_args()
    # Train profiles sequentially to keep CPU and memory use reasonable on the laptop.
    for profile in PROFILES if arguments.profile == "all" else [arguments.profile]:
        train_and_select_best_model(profile)
